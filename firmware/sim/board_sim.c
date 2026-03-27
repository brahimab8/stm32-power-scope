/**
 * @file    board_sim.c
 * @brief   Simulation board adapter (time, pluggable I2C backend, transport wiring).
 */

#include <board.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <time.h>
#endif

#include "board_sim_i2c.h"
#include "board_sim_config.h"
#include "comm_tcp.h"

typedef struct {
	uint8_t token;
} sim_i2c_bus_t;

/* Single synthetic bus handle used by the simulation target. */
static sim_i2c_bus_t s_i2c_bus = {.token = 0xA5u};
static uint16_t s_tcp_port = 9000u;

static board_sim_i2c_read_cb_t s_i2c_read_cb = NULL;
static board_sim_i2c_write_cb_t s_i2c_write_cb = NULL;

void board_sim_set_i2c_backend(board_sim_i2c_read_cb_t read_cb,
							   board_sim_i2c_write_cb_t write_cb) {
	s_i2c_read_cb = read_cb;
	s_i2c_write_cb = write_cb;
}

void board_sim_set_tcp_port(uint16_t port) {
	if (port == 0u) {
		return;
	}
	s_tcp_port = port;
}

uint32_t board_millis(void) {
#if defined(_WIN32)
	static ULONGLONG start_ms = 0;
	ULONGLONG now_ms = GetTickCount64();

	if (start_ms == 0) {
		start_ms = now_ms;
	}

	/* Expose relative uptime (ms since first call), not wall-clock time. */
	return (uint32_t)(now_ms - start_ms);
#else
	static uint64_t start_ms = 0;
	struct timespec ts = {0};
	uint64_t now_ms = 0;

	(void)clock_gettime(CLOCK_MONOTONIC, &ts);
	now_ms = (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;

	if (start_ms == 0ULL) {
		start_ms = now_ms;
	}

	/* Monotonic source avoids jumps from system time adjustments. */
	return (uint32_t)(now_ms - start_ms);
#endif
}

board_i2c_bus_t board_i2c_default_bus(void) {
	return (board_i2c_bus_t)&s_i2c_bus;
}

bool board_i2c_bus_read_reg(board_i2c_bus_t bus, uint8_t addr7, uint8_t reg, uint8_t* buf,
							uint8_t len) {
	if ((bus == NULL) || ((buf == NULL) && (len != 0u))) {
		return false;
	}
	if (s_i2c_read_cb == NULL) {
		return false;
	}

	/* Route board-level I2C traffic through registered simulation backend. */
	return s_i2c_read_cb(addr7, reg, buf, len);
}

bool board_i2c_bus_write_reg(board_i2c_bus_t bus, uint8_t addr7, uint8_t reg, uint8_t* buf,
							 uint8_t len) {
	if ((bus == NULL) || ((buf == NULL) && (len != 0u))) {
		return false;
	}
	if (s_i2c_write_cb == NULL) {
		return false;
	}

	/* Route board-level I2C traffic through registered simulation backend. */
	return s_i2c_write_cb(addr7, reg, buf, len);
}

void board_transport_init(ps_transport_adapter_t* adapter) {
	if (adapter == NULL) {
		return;
	}

	/* Fixed sim endpoint; host side uses matching TCP defaults/overrides. */
	(void)comm_tcp_init(s_tcp_port);

	/* Publish transport vtable consumed by ps_core. */
	adapter->tx_write = comm_tcp_try_write;
	adapter->link_ready = comm_tcp_link_ready;
	adapter->best_chunk = comm_tcp_best_chunk;
	adapter->set_rx_handler = comm_tcp_set_rx_handler;
}

void board_debug_led_on(void) {}

void board_debug_led_off(void) {}

void board_debug_led_toggle(void) {}
