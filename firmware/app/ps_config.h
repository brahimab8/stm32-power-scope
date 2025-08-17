/**
 * @file    ps_config.h
 * @brief   Power Scope app configuration (ring sizes, dummy generator).
 */
#pragma once
#include <stdint.h>

// Ring sizes (power-of-two, ≤ 65536)
#define PS_TX_RING_CAP 8192u
#define PS_RX_RING_CAP 2048u

// Stream cadence and payload size for the current build
#define PS_STREAM_PERIOD_MS 5u
#define PS_STREAM_PAYLOAD_LEN 128u

// bytes to parse per tick (64–256 is typical)
#define PS_CMD_BUDGET_PER_TICK 256u

// compile-time sanity
#if ((PS_TX_RING_CAP & (PS_TX_RING_CAP - 1)) || PS_TX_RING_CAP > 65536)
#error "PS_TX_RING_CAP must be power-of-two and ≤ 65536"
#endif
#if ((PS_RX_RING_CAP & (PS_RX_RING_CAP - 1)) || PS_RX_RING_CAP > 65536)
#error "PS_RX_RING_CAP must be power-of-two and ≤ 65536"
#endif
