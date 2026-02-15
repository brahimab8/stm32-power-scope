/**
 * @file    ps_sensor_registry.h
 * @brief   Registry for all available sensor adapters in Power Scope.
 */

#pragma once
#include "sensor/adapter.h"
#include <stdint.h>

/* ---------- Registry entry ---------- */
typedef struct {
    uint8_t type_id;               /**< Protocol-level type ID */
    ps_sensor_adapter_t* (*get_adapter)(void); /**< Adapter getter for this sensor type */
} ps_sensor_registry_entry_t;

/* ---------- Registry API ---------- */

/**
 * @brief Get the adapter for a given type ID.
 * @param type_id Sensor type ID
 * @return Pointer to adapter, or NULL if not found
 */
ps_sensor_adapter_t* ps_sensor_registry_get(uint8_t type_id);

/**
 * @brief Number of registered sensor types
 */
uint8_t ps_sensor_registry_count(void);

/**
 * @brief Get type_id for a registered index
 */
uint8_t ps_sensor_registry_get_type(uint8_t index);
