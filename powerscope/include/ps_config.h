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
#define PS_STREAM_PERIOD_MIN_MS 1u
#define PS_STREAM_PERIOD_MAX_MS 1000u

/* Max bytes accepted in ONE write() call (FS-CDC safe default)*/
#ifndef PS_TRANSPORT_MAX_WRITE_SIZE
#define PS_TRANSPORT_MAX_WRITE_SIZE 64u
#endif
