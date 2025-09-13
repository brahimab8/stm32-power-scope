/**
 * @file    ina219.c
 * @brief   INA219 driver: init/config and measurements (mV, µV, µA, mW).
 */
#include "ina219.h"

#include <stddef.h>

/* ===== Bounds (datasheet) =====
 * - 7-bit I2C address: 0..0x7F (caller responsibility to provide valid address)
 * - Supported shunt range: 1 mΩ .. 1,000,000 mΩ
 * - Calibration register: 1 .. 65535
 * Violations return INA219_E_PARAM.
 */
#define INA219_ADDR_MAX (0x7Fu)
#define INA219_SHUNT_MIN_MOHM (1u)
#define INA219_SHUNT_MAX_MOHM (1000000u)
#define INA219_CAL_MIN (1u)
#define INA219_CAL_MAX (65535u)

/* ===== Local helpers (big-endian 16-bit) ===== */
static uint16_t be16_to_u16(const uint8_t* b) {
    return (uint16_t)((((uint16_t)b[0]) << 8) | (uint16_t)b[1]);
}

static void u16_to_be16(uint16_t v, uint8_t* b) {
    b[0] = (uint8_t)((v >> 8) & 0xFFu);
    b[1] = (uint8_t)(v & 0xFFu);
}

/* Current_LSB (A/LSB) = 0.04096 / (Cal * Rshunt_ohm)
 * Integer form (µA & mΩ): current_scale_uA = 40960000 / (cal * shunt_mΩ).
 * Returns µA per LSB, saturated to 0xFFFF on overflow; 0 if denom=0.
 */
static uint16_t compute_current_scale_uA(uint16_t cal, uint32_t shunt_mohm) {
    const uint32_t denom = ((uint32_t)cal) * shunt_mohm;
    uint32_t s;

    if (denom == 0u) {
        return 0u;
    }

    s = 40960000u / denom;
    if (s > 0xFFFFu) {
        s = 0xFFFFu;
    }
    return (uint16_t)s;
}

/* Power LSB = 20 * Current_LSB; convert µA to mW with /1000 */
static uint16_t compute_power_scale_mW(uint16_t current_scale_uA) {
    const uint32_t mul = ((uint32_t)current_scale_uA) * 20u;
    return (uint16_t)(mul / 1000u);
}

/* Low-level IO wrappers (internal) */
static INA219_Status_t read_u16(INA219_Ctx_t* c, uint8_t reg, uint16_t* out) {
    uint8_t buf[2];

    if ((c == NULL) || (out == NULL)) {
        return INA219_E_PARAM;
    }
    if ((!c->initialized) || (c->i2c_read == NULL)) {
        return INA219_E_STATE;
    }
    if (!c->i2c_read(c->i2c_user, c->addr, reg, &buf[0], 2u)) {
        return INA219_E_IO;
    }

    *out = be16_to_u16(&buf[0]);
    return INA219_OK;
}

static INA219_Status_t write_u16(INA219_Ctx_t* c, uint8_t reg, uint16_t val) {
    uint8_t buf[2];

    if (c == NULL) {
        return INA219_E_PARAM;
    }
    if ((!c->initialized) || (c->i2c_write == NULL)) {
        return INA219_E_STATE;
    }

    u16_to_be16(val, &buf[0]);
    return c->i2c_write(c->i2c_user, c->addr, reg, &buf[0], 2u) ? INA219_OK : INA219_E_IO;
}

/* ===== Public API ===== */
INA219_Status_t INA219_Init(INA219_Ctx_t* c, const INA219_Init_t* in) {
    INA219_Status_t st;

    if ((c == NULL) || (in == NULL)) {
        return INA219_E_PARAM;
    }
    if ((in->i2c_read == NULL) || (in->i2c_write == NULL)) {
        return INA219_E_PARAM;
    }
    if ((in->i2c_address > INA219_ADDR_MAX) || (in->shunt_milliohm < INA219_SHUNT_MIN_MOHM) ||
        (in->shunt_milliohm > INA219_SHUNT_MAX_MOHM) || (in->calibration < INA219_CAL_MIN) ||
        (in->calibration > INA219_CAL_MAX)) {
        return INA219_E_PARAM;
    }

    /* Persist runtime essentials */
    c->i2c_read = in->i2c_read;
    c->i2c_write = in->i2c_write;
    c->i2c_user = in->i2c_user;
    c->addr = in->i2c_address;
    c->shunt_milliohm = in->shunt_milliohm;
    c->calibration = in->calibration;
    c->initialized = true;

    /* Program CONFIG then CALIBRATION */
    st = write_u16(c, INA219_REG_CONFIG, in->config);
    if (st != INA219_OK) {
        c->initialized = false;
        return st;
    }
    st = write_u16(c, INA219_REG_CALIBRATION, c->calibration);
    if (st != INA219_OK) {
        c->initialized = false;
        return st;
    }

    /* Precompute integer scales */
    c->current_scale_uA = compute_current_scale_uA(c->calibration, c->shunt_milliohm);
    c->power_scale_mW = compute_power_scale_mW(c->current_scale_uA);
    if ((c->current_scale_uA == 0u) || (c->power_scale_mW == 0u)) {
        c->initialized = false;
        return INA219_E_PARAM;
    }

    return INA219_OK;
}

INA219_Status_t INA219_WriteConfig(INA219_Ctx_t* c, uint16_t config_value) {
    if (c == NULL) {
        return INA219_E_PARAM;
    }
    return write_u16(c, INA219_REG_CONFIG, config_value);
}

INA219_Status_t INA219_SetCalibration(INA219_Ctx_t* c, uint16_t cal) {
    INA219_Status_t st;

    if (c == NULL) {
        return INA219_E_PARAM;
    }
    if ((cal < INA219_CAL_MIN) || (cal > INA219_CAL_MAX)) {
        return INA219_E_PARAM;
    }

    st = write_u16(c, INA219_REG_CALIBRATION, cal);
    if (st != INA219_OK) {
        return st;
    }

    c->calibration = cal;
    c->current_scale_uA = compute_current_scale_uA(c->calibration, c->shunt_milliohm);
    c->power_scale_mW = compute_power_scale_mW(c->current_scale_uA);

    return ((c->current_scale_uA == 0u) || (c->power_scale_mW == 0u)) ? INA219_E_PARAM : INA219_OK;
}

/* ===== Measurements ===== */
INA219_Status_t INA219_ReadBusVoltage_mV(INA219_Ctx_t* c, uint16_t* bus_mV) {
    INA219_Status_t st;
    uint16_t reg;

    if ((c == NULL) || (bus_mV == NULL)) {
        return INA219_E_PARAM;
    }

    st = read_u16(c, INA219_REG_BUS_VOLT, &reg);
    if (st != INA219_OK) {
        return st;
    }

    /* Bus Voltage register:
     * - Bits 15..3 contain the measurement.
     * - LSB = 4 mV.
     * Output is saturated to 16-bit (mV).
     */
    reg = (uint16_t)((reg >> 3) & 0x1FFFu);
    {
        const uint32_t mv = ((uint32_t)reg) * 4u;
        *bus_mV = (mv > 0xFFFFu) ? 0xFFFFu : (uint16_t)mv;
    }
    return INA219_OK;
}

INA219_Status_t INA219_ReadShuntVoltage_uV(INA219_Ctx_t* c, int32_t* shunt_uV) {
    INA219_Status_t st;
    uint16_t raw;

    if ((c == NULL) || (shunt_uV == NULL)) {
        return INA219_E_PARAM;
    }

    st = read_u16(c, INA219_REG_SHUNT_VOLT, &raw);
    if (st != INA219_OK) {
        return st;
    }

    *shunt_uV = ((int32_t)((int16_t)raw)) * 10; /* 10 µV/LSB */
    return INA219_OK;
}

INA219_Status_t INA219_ReadCurrent_uA(INA219_Ctx_t* c, int32_t* current_uA) {
    INA219_Status_t st;
    uint16_t raw;

    if ((c == NULL) || (current_uA == NULL)) {
        return INA219_E_PARAM;
    }

    st = read_u16(c, INA219_REG_CURRENT, &raw);
    if (st != INA219_OK) {
        return st;
    }

    *current_uA = ((int32_t)((int16_t)raw)) * (int32_t)c->current_scale_uA;
    return INA219_OK;
}

INA219_Status_t INA219_ReadPower_mW(INA219_Ctx_t* c, uint32_t* power_mW) {
    INA219_Status_t st;
    uint16_t raw;

    if ((c == NULL) || (power_mW == NULL)) {
        return INA219_E_PARAM;
    }

    st = read_u16(c, INA219_REG_POWER, &raw);
    if (st != INA219_OK) {
        return st;
    }

    *power_mW = ((uint32_t)raw) * (uint32_t)c->power_scale_mW;
    return INA219_OK;
}
