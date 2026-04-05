/**
 * @file    header.h
 * @brief   Protocol frame header layout and framing helpers.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include <ps_compiler.h>
#include "protocol/constants.h"

#ifdef __cplusplus
extern "C" {
#endif

/* --- 16-byte packed header --- */
PS_PACKED_BEGIN
typedef struct PS_PACKED {
    uint16_t magic; /* PS_PROTOCOL_MAGIC */
    uint8_t type;   /* STREAM / CMD / ACK / NACK */
    uint8_t ver;    /* PS_PROTOCOL_VERSION */
    uint16_t len;   /* payload bytes (<= PS_PROTOCOL_MAX_PAYLOAD) */
    uint8_t cmd_id; /* command opcode (valid if type==PS_PROTOCOL_TYPE_CMD) */
    uint8_t rsv;    /* reserved (0 for now) */
    uint32_t seq;   /* sequence number (for stream) /correlation ID (echoed in ACK/NACK) */
    uint32_t ts_ms; /* device time (board_millis) */
} proto_hdr_t;
PS_PACKED_END

/* Header field offsets in on-wire little-endian frame bytes. */
enum {
    PROTO_HDR_OFF_MAGIC = 0u,
    PROTO_HDR_OFF_TYPE = 2u,
    PROTO_HDR_OFF_VER = 3u,
    PROTO_HDR_OFF_LEN = 4u,
    PROTO_HDR_OFF_CMD_ID = 6u,
    PROTO_HDR_OFF_RSV = 7u,
    PROTO_HDR_OFF_SEQ = 8u,
    PROTO_HDR_OFF_TS_MS = 12u
};

#ifdef __cplusplus
}
#endif
