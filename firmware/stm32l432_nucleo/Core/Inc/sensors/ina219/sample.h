/**
 * @file    sensors/ina219/sample.h
 * @brief   ina219 sensor sample definition
 * 
 * Defines the data structure produced by the INA219 sensor adapter.
 * Each sample represents one instantaneous measurement of bus voltage
 * and current flowing through the shunt resistor.
 */

#pragma once
#include <stdint.h>

 /* ----------- Sensor sample types ----------- */
typedef uint16_t    INA219_bus_mV_t;
typedef int32_t     INA219_current_uA_t;

/* ---------- Sensor sample structure --------- */
 typedef struct __attribute__((packed)) {
    INA219_bus_mV_t bus_mV;
    INA219_current_uA_t current_uA;
} ps_sensor_sample_INA219_t;

/* -- Size of a single INA219 sample in bytes -- */
#define INA219_SAMPLE_SIZE sizeof(ps_sensor_sample_INA219_t)