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
} board_sim_i2c_bus_t;

/* Single synthetic bus handle used by the simulation target. */
static board_sim_i2c_bus_t s_i2c_bus = {.token = 0xA5u};
static uint16_t s_tcp_port = 9000u;

static board_sim_i2c_read_cb_t s_i2c_read_cb = NULL;
static board_sim_i2c_write_cb_t s_i2c_write_cb = NULL;

/* FNV-1a hash: 16777619u is the 32-bit FNV prime used to mix each byte. */
static uint32_t board_sim_fnv1a32(const uint8_t* data, size_t len, uint32_t seed) {
	uint32_t h = seed;
	for (size_t i = 0; i < len; ++i) {
		h ^= (uint32_t)data[i];
		h *= 16777619u;
	}
	return h;
}

static void board_sim_wr_u32le(uint8_t* out, uint32_t v) {
	out[0] = (uint8_t)(v & 0xFFu);
	out[1] = (uint8_t)((v >> 8) & 0xFFu);
	out[2] = (uint8_t)((v >> 16) & 0xFFu);
	out[3] = (uint8_t)((v >> 24) & 0xFFu);
}

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

/*
 * board_get_uid_raw()
 * -------------------
 * Return a deterministic 12-byte synthetic UID for the simulator.
 *
 * The base value is a fixed ASCII seed; the active TCP port is mixed in so
 * that multiple simulator instances can produce different board identities.
 */
bool board_get_uid_raw(uint8_t out_uid12[12]) {
	static const uint8_t k_base_uid[12] = {
		0x50u, 0x53u, 0x53u, 0x49u, 0x4Du, 0x2Du, 0x42u, 0x41u, 0x53u, 0x45u, 0x2Du, 0x31u,
	};

	if (out_uid12 == NULL) {
		return false;
	}

	const uint32_t seed = 2166136261u ^ (uint32_t)s_tcp_port;
	const uint32_t w0 = board_sim_fnv1a32(k_base_uid, sizeof(k_base_uid), seed ^ 0x9E3779B9u);
	const uint32_t w1 = board_sim_fnv1a32(k_base_uid, sizeof(k_base_uid), seed ^ 0x85EBCA6Bu);
	const uint32_t w2 = board_sim_fnv1a32(k_base_uid, sizeof(k_base_uid), seed ^ 0xC2B2AE35u);

	board_sim_wr_u32le(out_uid12 + 0u, w0);
	board_sim_wr_u32le(out_uid12 + 4u, w1);
	board_sim_wr_u32le(out_uid12 + 8u, w2);
	return true;
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
