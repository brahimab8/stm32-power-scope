/**
 * @file    sensors/ina219/sample.h
 * @brief   ina219 sensor sample definition
 */

#pragma once
#include <stdint.h>
#include <ps_compiler.h>

typedef uint16_t INA219_bus_mV_t;
typedef int32_t INA219_current_uA_t;

PS_PACKED_BEGIN
typedef struct PS_PACKED {
    INA219_bus_mV_t bus_mV;
    INA219_current_uA_t current_uA;
} ps_sensor_sample_INA219_t;
PS_PACKED_END

#define INA219_SAMPLE_SIZE sizeof(ps_sensor_sample_INA219_t)
