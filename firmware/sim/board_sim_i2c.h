/**
 * @file    board_sim_i2c.h
 * @brief   Board-sim I2C backend registration hooks.
 */

#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef bool (*board_sim_i2c_read_cb_t)(uint8_t addr7, uint8_t reg, uint8_t* buf, uint8_t len);
typedef bool (*board_sim_i2c_write_cb_t)(uint8_t addr7, uint8_t reg, uint8_t* buf, uint8_t len);

/**
 * @brief Register the active simulated I2C backend handlers.
 *
 * Passing NULL handlers disables board-level I2C emulation.
 */
void board_sim_set_i2c_backend(board_sim_i2c_read_cb_t read_cb,
                               board_sim_i2c_write_cb_t write_cb);
