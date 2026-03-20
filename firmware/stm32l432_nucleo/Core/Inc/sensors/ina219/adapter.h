/**
 * @file    sensors/ina219/adapter.h
 * @brief   INA219 sensor adapter factory
 */

#pragma once
#include "sensor/adapter.h"

/**
 * @brief Get or create an INA219 adapter for the given configuration.
 * @param config Configuration (ps_ina219_config_t*), or NULL for default singleton
 * @return Adapter pointer, or NULL on failure
 */
ps_sensor_adapter_t* ps_get_ina219_adapter(const void* config);
