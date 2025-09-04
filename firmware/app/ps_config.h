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
#define PS_STREAM_PAYLOAD_LEN 4u /* int16 i_mA + uint16 v_mV */

/* Max bytes accepted in ONE write() call (FS-CDC safe default)*/
#ifndef PS_TRANSPORT_MAX_WRITE_SIZE
#define PS_TRANSPORT_MAX_WRITE_SIZE 64u
#endif

/* Compile-time sanity (power-of-two + range) */
#if ((PS_TX_RING_CAP & (PS_TX_RING_CAP - 1)) || PS_TX_RING_CAP > 65536)
#error "PS_TX_RING_CAP must be power-of-two and ≤ 65536"
#endif
#if ((PS_RX_RING_CAP & (PS_RX_RING_CAP - 1)) || PS_RX_RING_CAP > 65536)
#error "PS_RX_RING_CAP must be power-of-two and ≤ 65536"
#endif
