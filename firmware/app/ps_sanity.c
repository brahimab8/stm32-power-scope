/**
 * @file ps_sanity.c
 * @brief Compile-time integration-checks.
 *
 * This file performs static assertions to ensure that configuration values
 * (from ps_config.h) and protocol definitions (from protocol_defs.h) are
 * mutually consistent.
 */

#include "app/protocol_defs.h"
#include "app/ps_assert.h"
#include "app/ps_config.h"

/* Stream payload must not exceed protocol max */
PS_STATIC_ASSERT(PS_STREAM_PAYLOAD_LEN <= PROTO_MAX_PAYLOAD,
                 "PS_STREAM_PAYLOAD_LEN > PROTO_MAX_PAYLOAD");

/* A full max-size frame must fit entirely in the TX/RX rings (usable = cap-1) */
PS_STATIC_ASSERT(PROTO_FRAME_MAX_BYTES <= (PS_TX_RING_CAP - 1),
                 "TX ring too small for max protocol frame");

PS_STATIC_ASSERT(PROTO_FRAME_MAX_BYTES <= (PS_RX_RING_CAP - 1),
                 "RX ring too small for max protocol frame");

/* A full max-size frame must fit in a single transport write */
PS_STATIC_ASSERT(PROTO_FRAME_MAX_BYTES <= PS_TRANSPORT_MAX_WRITE_SIZE,
                 "Protocol frame doesn't fit in one transport write");