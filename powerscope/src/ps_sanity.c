/**
 * @file ps_sanity.c
 * @brief Compile-time integration-checks.
 *
 * This file performs static assertions to ensure that configuration values
 * (from ps_config.h) and protocol definitions (from protocol/header.h) are
 * mutually consistent.
 */

#include <protocol/header.h>
#include <ps_assert.h>
#include <ps_config.h>

PS_STATIC_ASSERT(sizeof(proto_hdr_t) == PS_PROTOCOL_HDR_LEN,
                 "proto_hdr_t size mismatch with PS_PROTOCOL_HDR_LEN");

/* A full max-size frame must fit entirely in the TX/RX rings (usable = cap-1) */
PS_STATIC_ASSERT(PS_PROTOCOL_FRAME_MAX_BYTES <= (PS_TX_RING_CAP - 1),
                 "TX ring too small for max protocol frame");
PS_STATIC_ASSERT(PS_PROTOCOL_FRAME_MAX_BYTES <= (PS_RX_RING_CAP - 1),
                 "RX ring too small for max protocol frame");

/* A full max-size frame must fit in a single transport write */
PS_STATIC_ASSERT(PS_PROTOCOL_FRAME_MAX_BYTES <= PS_TRANSPORT_MAX_WRITE_SIZE,
                 "Protocol frame doesn't fit in one transport write");

/* Stream period sanity */
PS_STATIC_ASSERT(PS_STREAM_PERIOD_MS > 0, "Stream period must be > 0");
PS_STATIC_ASSERT(PS_STREAM_PERIOD_MS >= PS_STREAM_PERIOD_MIN_MS,
                 "PS_STREAM_PERIOD_MS smaller than PS_STREAM_PERIOD_MIN_MS");
PS_STATIC_ASSERT(PS_STREAM_PERIOD_MS <= PS_STREAM_PERIOD_MAX_MS,
                 "PS_STREAM_PERIOD_MS larger than PS_STREAM_PERIOD_MAX_MS");

/* Min/max sanity */
PS_STATIC_ASSERT(PS_STREAM_PERIOD_MIN_MS > 0, "PS_STREAM_PERIOD_MIN_MS must be > 0");
PS_STATIC_ASSERT(PS_STREAM_PERIOD_MAX_MS >= PS_STREAM_PERIOD_MIN_MS,
                 "PS_STREAM_PERIOD_MAX_MS must be >= PS_STREAM_PERIOD_MIN_MS");
