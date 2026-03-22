/**
 * @file    sensors/ina219/fake.c
 * @brief   Fake INA219 I2C device emulation - address-agnostic.
 */

#include "fake.h"

#include <string.h>

#include "board_sim_i2c.h"
#include "drivers/ina219/driver.h"

/* Max concurrent INA219 devices in simulation */
#define FAKE_INA219_MAX_DEVICES 8U

typedef struct {
    uint8_t addr;       /* I2C address (0xFF = unused slot) */
    uint16_t regs[6];   /* INA219 register file */
    uint32_t tick;      /* Timestamp for waveform generation */
} fake_ina219_dev_t;

static fake_ina219_dev_t s_devices[FAKE_INA219_MAX_DEVICES];

static uint16_t be16_read(const uint8_t* b) {
    return (uint16_t)(((uint16_t)b[0] << 8u) | (uint16_t)b[1]);
}

static void be16_write(uint16_t value, uint8_t* b) {
    b[0] = (uint8_t)(value >> 8u);
    b[1] = (uint8_t)(value & 0xFFu);
}

/**
 * @brief Find or create device entry for the given address.
 * @param addr7 7-bit I2C address
 * @return Device pointer, or NULL if max devices reached or invalid address
 */
static fake_ina219_dev_t* find_or_create_device(uint8_t addr7) {
    /* Validate I2C address range */
    if (addr7 > 0x7Fu) {
        return NULL;
    }

    /* Check if already exists */
    for (uint8_t i = 0; i < FAKE_INA219_MAX_DEVICES; ++i) {
        if (s_devices[i].addr == addr7) {
            return &s_devices[i];
        }
    }

    /* Find and initialize empty slot */
    for (uint8_t i = 0; i < FAKE_INA219_MAX_DEVICES; ++i) {
        if (s_devices[i].addr == 0xFFu) {
            s_devices[i].addr = addr7;
            memset(s_devices[i].regs, 0, sizeof(s_devices[i].regs));
            s_devices[i].regs[INA219_REG_CONFIG] = INA219_CONFIG_DEFAULT;
            s_devices[i].regs[INA219_REG_CALIBRATION] = 4096u;
            s_devices[i].tick = 0;
            return &s_devices[i];
        }
    }

    return NULL; /* No space */
}

void fake_ina219_init(void) {
    /* Mark all slots as unused */
    for (uint8_t i = 0; i < FAKE_INA219_MAX_DEVICES; ++i) {
        s_devices[i].addr = 0xFFu;
    }

    board_sim_set_i2c_backend(fake_ina219_i2c_read, fake_ina219_i2c_write);
}

void fake_ina219_tick(void) {
    /* Update all active devices */
    for (uint8_t i = 0; i < FAKE_INA219_MAX_DEVICES; ++i) {
        if (s_devices[i].addr == 0xFFu) {
            continue; /* Unused slot */
        }

        fake_ina219_dev_t* dev = &s_devices[i];
        int16_t current_raw = 0;
        int16_t shunt_raw = 0;
        uint16_t bus_raw_13 = 0;
        uint16_t power_raw = 0;

        dev->tick++;

        /* Pseudo-waveforms vary per address to distinguish sensors */
        uint8_t offset = dev->addr;
        current_raw = (int16_t)(220 + (int16_t)((dev->tick + offset) % 60u));
        shunt_raw = (int16_t)(80 + (int16_t)((dev->tick + offset / 2u) % 30u));
        bus_raw_13 = (uint16_t)(3000u + (uint16_t)((dev->tick + offset) % 120u));
        power_raw = (uint16_t)(350u + (uint16_t)((dev->tick + offset) % 80u));

        dev->regs[INA219_REG_CURRENT] = (uint16_t)current_raw;
        dev->regs[INA219_REG_SHUNT_VOLT] = (uint16_t)shunt_raw;
        dev->regs[INA219_REG_BUS_VOLT] = (uint16_t)(bus_raw_13 << 3u);
        dev->regs[INA219_REG_POWER] = power_raw;
    }
}

bool fake_ina219_i2c_read(uint8_t addr7, uint8_t reg, uint8_t* buf, uint8_t len) {
    if ((buf == NULL) || (len != 2u) || (reg > INA219_REG_CALIBRATION)) {
        return false;
    }

    fake_ina219_dev_t* dev = find_or_create_device(addr7);
    if (dev == NULL) {
        return false;
    }

    be16_write(dev->regs[reg], buf);
    return true;
}

bool fake_ina219_i2c_write(uint8_t addr7, uint8_t reg, uint8_t* buf, uint8_t len) {
    if ((buf == NULL) || (len != 2u) || (reg > INA219_REG_CALIBRATION)) {
        return false;
    }

    fake_ina219_dev_t* dev = find_or_create_device(addr7);
    if (dev == NULL) {
        return false;
    }

    dev->regs[reg] = be16_read(buf);
    return true;
}
