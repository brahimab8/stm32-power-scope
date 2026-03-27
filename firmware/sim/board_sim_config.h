/**
 * @file    board_sim_config.h
 * @brief   Runtime configuration hooks for simulation board adapter.
 */

#pragma once

#include <stdint.h>

void board_sim_set_tcp_port(uint16_t port);
