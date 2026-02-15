/**
 * @file    ina219/config.h
 * @brief   Sensor-specific configuration for Power Scope.
 */
#pragma once
#include <stdint.h>

/* ---------- INA219 hardware configuration ---------- */
#define PS_INA219_ADDR 0x40U      /**< Default INA219 I²C address */
#define PS_INA219_SHUNT_mOHM 100U /**< Shunt resistor value in milliohms */
#define PS_INA219_CALIB 4096U     /**< Calibration value for 32V/2A range */

/* ----- Field IDs for power sensor samples ----- */
#define PS_FIELD_BUS_MV 0
#define PS_FIELD_CURRENT_UA 1

/* ---------- Sensor sample types ---------- */
typedef uint16_t ps_sensor_bus_mV_t;
typedef int32_t ps_sensor_current_uA_t;

/**
 * @brief  Sensor payload layout for Power Scope.
 *
 * `__attribute__((packed))` used to avoid padding
 * and ensure consistent size for streaming.
 */
typedef struct __attribute__((packed)) {
    ps_sensor_bus_mV_t bus_mV;         /**< Bus voltage in mV */
    ps_sensor_current_uA_t current_uA; /**< Current in µA */
} ps_sensor_sample_t;

/** @brief Length of the buffer required for one sample */
#define PS_SENSOR_BUF_LEN sizeof(ps_sensor_sample_t)
