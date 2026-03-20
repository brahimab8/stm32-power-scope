/**
 * @file    ps_sensor_registry.h
 * @brief   Registry for all available sensor adapters in Power Scope.
 */

#pragma once
#include "sensor/adapter.h"
#include <stdint.h>

/* ---------- Registry entry ---------- */
typedef struct {
    uint8_t type_id;                                          /**< Protocol-level type ID */
    ps_sensor_adapter_t* (*get_adapter)(const void* config); /**< Adapter getter (config is sensor-type-specific) */
} ps_sensor_registry_entry_t;

/* ---------- Registry API ---------- */

/**
 * @brief Get the adapter for a given type ID and configuration.
 * @param type_id Sensor type ID
 * @param config Sensor-specific configuration (e.g., ps_ina219_config_t*), or NULL for defaults
 * @return Pointer to adapter, or NULL if not found
 */
ps_sensor_adapter_t* ps_sensor_registry_get(uint8_t type_id, const void* config);

/**
 * @brief Number of registered sensor types
 */
uint8_t ps_sensor_registry_count(void);

/**
 * @brief Get type_id for a registered index
 */
uint8_t ps_sensor_registry_get_type(uint8_t index);
