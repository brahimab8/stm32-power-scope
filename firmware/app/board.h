/**
 * @file    board.h
 * @brief   Minimal board abstraction used by the app (no HAL leaks).
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Millisecond monotonic tick (wrap OK). */
uint32_t board_millis(void);

/** Timebase in Hz for board_millis() (usually 1000). */
static inline uint32_t board_timebase_hz(void) {
    return 1000u;
}

/* -------- I2C -------- */

/** Opaque I2C bus token.  */
typedef void* board_i2c_bus_t;

/**
 * @brief Obtain the default I2C bus token to pass into the APIs.
 */
board_i2c_bus_t board_i2c_default_bus(void);

/** 
 * @brief Read from an 8-bit register on an I2C device (blocking).
 * @param bus    Bus handle (opaque). Must be non-NULL.
 * @param addr7  7-bit I2C address (0..127)
 * @param reg    8-bit register address
 * @param buf    Destination buffer (may be NULL iff len == 0)
 * @param len    number of bytes to read
 * @return true on success, false otherwise
 */
bool board_i2c_bus_read_reg(board_i2c_bus_t bus, 
                            uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t len);

/**
 * @brief Write to an 8-bit register on an I2C device (blocking).
 * @param bus    Bus handle (opaque). Must be non-NULL.
 * @param addr7  7-bit I2C address (0..127)
 * @param reg    8-bit register address
 * @param buf    Source buffer (may be NULL iff len == 0)
 * @param len    Number of bytes to write
 * @return true on success, false otherwise
 */
bool board_i2c_bus_write_reg(board_i2c_bus_t bus, 
                            uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t len);

#ifdef __cplusplus
}
#endif
