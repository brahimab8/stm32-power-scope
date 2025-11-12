/**
 * @file    ps_sensor_adapter.c
 * @brief   Power Scope sensor adapter wiring (INA219 + HW + sensor manager).
 */

#include "ps_sensor_adapter.h"

#include <board.h>
#include <ps_sensor_config.h>
#include <string.h>

#include "ina219.h"
#include "ps_config.h"
#include "ps_sensor_mgr.h"

/* ---------- Internal structure ---------- */
typedef struct {
    INA219_Ctx_t hw;
    ps_sensor_sample_t sample;
    sensor_mgr_ctx_t mgr;
    ps_sensor_adapter_t adapter;
    size_t sample_size;
} power_sensor_internal_t;

static power_sensor_internal_t g_power_sensor;

/* ---------- Hardware read for sensor_mgr ---------- */
static bool hw_read(void* user_ctx, void* out) {
    power_sensor_internal_t* s = (power_sensor_internal_t*)user_ctx;
    ps_sensor_sample_t* sample = (ps_sensor_sample_t*)out;
    ps_sensor_bus_mV_t bus;
    ps_sensor_current_uA_t current;

    if (INA219_ReadBusVoltage_mV(&s->hw, &bus) != INA219_OK) return false;
    if (INA219_ReadCurrent_uA(&s->hw, &current) != INA219_OK) return false;

    sample->bus_mV = bus;
    sample->current_uA = current;

    return true;
}

/* ---------- Singleton getter ---------- */
ps_sensor_adapter_t* ps_get_sensor_adapter(void) {
    static bool init_done = false;
    if (!init_done) {
        /* --- Initialize INA219 --- */
        const board_i2c_bus_t bus = board_i2c_default_bus();
        INA219_Init_t init = {.i2c_read = board_i2c_bus_read_reg,
                              .i2c_write = board_i2c_bus_write_reg,
                              .i2c_user = (void*)bus,
                              .i2c_address = PS_INA219_ADDR,
                              .shunt_milliohm = PS_INA219_SHUNT_mOHM,
                              .calibration = PS_INA219_CALIB,
                              .config = INA219_CONFIG_DEFAULT};
        INA219_Init(&g_power_sensor.hw, &init);

        /* --- Wrap into sensor_mgr --- */
        sensor_iface_t iface = {.hw_ctx = &g_power_sensor,
                                .read_sample = hw_read,
                                .sample_size = sizeof(ps_sensor_sample_t)};

        sensor_mgr_init(&g_power_sensor.mgr, iface, (uint8_t*)&g_power_sensor.sample, board_millis);

        /* --- Wrap into ps_sensor_adapter_t --- */
        g_power_sensor.adapter = sensor_mgr_as_adapter(&g_power_sensor.mgr);
        g_power_sensor.adapter.sample_size = sizeof(ps_sensor_sample_t);
        g_power_sensor.adapter.type_id = PS_SENSOR_TYPE_INA219;
        init_done = true;
    }

    return &g_power_sensor.adapter;
}
