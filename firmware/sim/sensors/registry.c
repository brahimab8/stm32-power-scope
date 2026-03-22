/**
 * @file    sensors/registry.c
 * @brief   Sensor registry mapping for simulation firmware target.
 */

#include "sensor/registry.h"
#include "sensors/ina219/adapter.h"
#include "drivers/defs.h"

static const ps_sensor_registry_entry_t registry[] = {
    {PS_SENSOR_TYPE_INA219, (ps_sensor_adapter_t* (*)(const void*))ps_get_ina219_adapter},
};

ps_sensor_adapter_t* ps_sensor_registry_get(uint8_t type_id, const void* config) {
    for (uint8_t i = 0; i < (uint8_t)(sizeof(registry) / sizeof(registry[0])); ++i) {
        if (registry[i].type_id == type_id) {
            return registry[i].get_adapter(config);
        }
    }

    return NULL;
}

uint8_t ps_sensor_registry_count(void) {
    return (uint8_t)(sizeof(registry) / sizeof(registry[0]));
}

uint8_t ps_sensor_registry_get_type(uint8_t index) {
    if (index < (uint8_t)(sizeof(registry) / sizeof(registry[0]))) {
        return registry[index].type_id;
    }

    return 0xFFu;
}
