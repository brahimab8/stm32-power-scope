/**
 * @file    sensors/ina219/adapter.c
 * @brief   Power Scope sensor adapter wiring (INA219 + HW + sensor manager).
 */

#include "sensor/adapter.h"
#include <board.h>
#include "sensors/ina219/config.h"
#include "sensors/ina219/sample.h"

#include <string.h>

#include "drivers/ina219/driver.h"

#include "ps_config.h"
#include "drivers/defs.h" /* for PS_SENSOR_TYPE_INA219 */

#include "sensor/manager.h"

/* Maximum number of concurrent INA219 instances */
#define INA219_ADAPTER_MAX_INSTANCES 8U

/* ---------- Internal structure ---------- */
typedef struct {
    INA219_Ctx_t hw;
    ps_sensor_sample_INA219_t sample;
    sensor_mgr_ctx_t mgr;
    ps_sensor_adapter_t adapter;
    bool used;
    uint8_t i2c_addr;
} power_sensor_internal_t;

static power_sensor_internal_t s_instances[INA219_ADAPTER_MAX_INSTANCES];

/* ---------- Hardware read for sensor_mgr ---------- */
static bool hw_read(void* user_ctx, void* out) {
    power_sensor_internal_t* s = (power_sensor_internal_t*)user_ctx;
    ps_sensor_sample_INA219_t* sample = (ps_sensor_sample_INA219_t*)out;
    INA219_bus_mV_t bus;
    INA219_current_uA_t current;

    if (INA219_ReadBusVoltage_mV(&s->hw, &bus) != INA219_OK) return false;
    if (INA219_ReadCurrent_uA(&s->hw, &current) != INA219_OK) return false;

    sample->bus_mV = bus;
    sample->current_uA = current;

    return true;
}

static power_sensor_internal_t* find_or_create_instance(const ps_ina219_config_t* cfg) {
    const uint8_t i2c_addr = cfg->i2c_addr;
    /* Check if already exists */
    for (uint8_t i = 0; i < INA219_ADAPTER_MAX_INSTANCES; ++i) {
        if (s_instances[i].used && s_instances[i].i2c_addr == i2c_addr) {
            return &s_instances[i];
        }
    }

    /* Find empty slot */
    for (uint8_t i = 0; i < INA219_ADAPTER_MAX_INSTANCES; ++i) {
        if (!s_instances[i].used) {
            power_sensor_internal_t* inst = &s_instances[i];
            const board_i2c_bus_t bus = board_i2c_default_bus();
            INA219_Init_t init = {.i2c_read = board_i2c_bus_read_reg,
                                  .i2c_write = board_i2c_bus_write_reg,
                                  .i2c_user = (void*)bus,
                                  .i2c_address = i2c_addr,
                                  .shunt_milliohm = cfg->shunt_milliohm,
                                  .calibration = cfg->calibration,
                                  .config = INA219_CONFIG_DEFAULT};
            if (INA219_Init(&inst->hw, &init) != INA219_OK) {
                return NULL;
            }

            /* --- Wrap into sensor_mgr --- */
            sensor_iface_t iface = {.hw_ctx = inst,
                                    .read_sample = hw_read,
                                    .sample_size = sizeof(ps_sensor_sample_INA219_t)};

            sensor_mgr_init(&inst->mgr, iface, (uint8_t*)&inst->sample, board_millis);

            /* --- Wrap into ps_sensor_adapter_t --- */
            inst->adapter = sensor_mgr_as_adapter(&inst->mgr);
            inst->adapter.sample_size = sizeof(ps_sensor_sample_INA219_t);
            inst->adapter.type_id = PS_SENSOR_TYPE_INA219;
            inst->used = true;
            inst->i2c_addr = i2c_addr;

            return inst;
        }
    }

    return NULL; /* No space */
}

/* ---------- Factory getter ---------- */
ps_sensor_adapter_t* ps_get_ina219_adapter(const void* config) {
    /* Handle NULL config (backward compat: use default address) */
    if (config == NULL) {
        config = (const void*)&(const ps_ina219_config_t){.i2c_addr = PS_INA219_ADDR};
    }

    const ps_ina219_config_t* cfg = (const ps_ina219_config_t*)config;
    power_sensor_internal_t* inst = find_or_create_instance(cfg);
    return inst ? &inst->adapter : NULL;
}
