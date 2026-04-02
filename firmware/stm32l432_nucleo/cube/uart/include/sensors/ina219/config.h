/**
 * @file    sensors/ina219/config.h
 * @brief   Sensor-specific configuration for Power Scope.
 */
#pragma once
#include <stdint.h>

/* ---------- INA219 hardware configuration ---------- */
#define PS_INA219_ADDR 0x40U      /**< Default INA219 I²C address */
#define PS_INA219_SHUNT_mOHM 100U /**< Shunt resistor value in milliohms */
#define PS_INA219_CALIB 4096U     /**< Calibration value for 32V/2A range */