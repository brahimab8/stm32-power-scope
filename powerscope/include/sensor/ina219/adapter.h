/**
 * @file    sensor/ina219/adapter.h
 * @brief   INA219 sensor adapter singleton
 */

#pragma once
#include "sensor/adapter.h"

/**
 * @brief Returns the singleton INA219 sensor adapter instance.
 */
ps_sensor_adapter_t* ps_get_ina219_adapter(void);
