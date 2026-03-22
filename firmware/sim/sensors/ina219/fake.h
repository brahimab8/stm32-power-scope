/**
 * @file    sensors/ina219/fake.h
 * @brief   Fake INA219 I2C device emulation for simulation target.
 */

#pragma once
#include <stdbool.h>
#include <stdint.h>

/**
 * @brief Initialize all fake INA219 devices.
 */
void fake_ina219_init(void);

/**
 * @brief Update all active fake INA219 devices (pseudo-waveforms).
 *        Call periodically (e.g., every tick).
 */
void fake_ina219_tick(void);

/**
 * @brief I2C read handler for fake INA219 devices.
 * @param addr7 7-bit I2C address
 * @param reg   8-bit register address
 * @param buf   2-byte output buffer
 * @param len   Must be 2
 * @return true on success, false if address/reg/len invalid
 */
bool fake_ina219_i2c_read(uint8_t addr7, uint8_t reg, uint8_t* buf, uint8_t len);

/**
 * @brief I2C write handler for fake INA219 devices.
 * @param addr7 7-bit I2C address
 * @param reg   8-bit register address
 * @param buf   2-byte input buffer
 * @param len   Must be 2
 * @return true on success, false if address/reg/len invalid
 */
bool fake_ina219_i2c_write(uint8_t addr7, uint8_t reg, uint8_t* buf, uint8_t len);
