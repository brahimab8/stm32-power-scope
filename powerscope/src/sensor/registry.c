/**
 * @file    registry.c
 * @brief   Sensor registry implementation for Power Scope.
 */

#include "sensor/registry.h"
#include "sensor/ina219/adapter.h"
#include "sensor/defs.h"

/* ---------- Static registry ---------- */
static const ps_sensor_registry_entry_t registry[] = {
    { PS_SENSOR_TYPE_INA219, ps_get_ina219_adapter },
    // Add more entries here as new sensor types are implemented
};

ps_sensor_adapter_t* ps_sensor_registry_get(uint8_t type_id) {
    for (uint8_t i = 0; i < sizeof(registry)/sizeof(registry[0]); ++i) {
        if (registry[i].type_id == type_id) {
            return registry[i].get_adapter();
        }
    }
    return NULL;
}

uint8_t ps_sensor_registry_count(void) {
    return sizeof(registry)/sizeof(registry[0]);
}

uint8_t ps_sensor_registry_get_type(uint8_t index) {
    if (index < sizeof(registry)/sizeof(registry[0])) {
        return registry[index].type_id;
    }
    return 0xFF; // invalid
}
