/**
 * @file    protocol_defs.h
 * @brief   Tiny framing protocol: header layout + helpers + command opcodes.
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- constants --- */
#define PROTO_MAGIC 0x5AA5u /* on the wire: A5 5A (LE) */
#define PROTO_VERSION 0u
#define PROTO_TYPE_STREAM 0u        /* device→host data stream */
#define PROTO_TYPE_CMD      1u      /* host→device command (payload = opcodes/args) */
#define PROTO_TYPE_ACK      2u      /* device→host reply (header-only, len=0) */
#define PROTO_TYPE_NACK     3u      /* device→host reply (header-only, len=0) */

/* --- 16-byte packed header --- */
typedef struct __attribute__((packed)) {
    uint16_t magic; /* PROTO_MAGIC */
    uint8_t type;   /* STREAM / CMD / ACK / NACK */
    uint8_t ver;    /* PROTO_VERSION */
    uint16_t len;   /* payload bytes (<= PROTO_MAX_PAYLOAD) */
    uint16_t rsv;   /* reserved (0 for now) */
    uint32_t seq;   /* sequence number (for stream) /correlation ID (echoed in ACK/NACK) */
    uint32_t ts_ms; /* device time (board_millis) */
} proto_hdr_t;

/* --- protocol sizes --- */

#define PROTO_FRAME_OVERHEAD ((uint16_t)sizeof(proto_hdr_t))
#define PROTO_MAX_PAYLOAD   46u
#define PROTO_CRC_LEN       2u

#define PROTO_FRAME_MAX_BYTES (PROTO_FRAME_OVERHEAD + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN)


/* --- commands (1-byte opcodes in CMD payload) --- */
typedef enum {
    PROTO_CMD_START = 0x01,
    PROTO_CMD_STOP = 0x02,
} proto_cmd_t;

/* --- helpers --- */

/**
 * @brief Parse and validate a complete protocol frame.
 *
 * Validation includes: MAGIC, VERSION, len <= PROTO_MAX_PAYLOAD,
 * and CRC-16/CCITT-FALSE over header+payload.
 *
 * @param buf          Pointer to bytes at a candidate frame boundary.
 * @param len          Number of available bytes from @p buf.
 * @param hdr_out      Optional out header; may be NULL.
 * @param payload      Optional out pointer to payload within @p buf; may be NULL.
 * @param payload_len  Optional out payload length; may be NULL.
 * @return size_t      Total frame bytes consumed on success;
 *                     0 if incomplete or invalid (caller may drop 1 byte to resync).
 */
size_t proto_parse_frame(const uint8_t* buf, size_t len,
                         proto_hdr_t* hdr_out,
                         const uint8_t** payload, uint16_t* payload_len);

/**
 * @brief Write a full frame (header + optional payload) into 'out'.
 * @param type       PROTO_TYPE_STREAM / CMD / ACK / NACK
 * @param payload   payload bytes (may be NULL when payload_len==0, e.g., ACK/NACK)
 * @param payload_len number of payload bytes (<= PROTO_MAX_PAYLOAD)
 * @param seq       sequence number (for stream) /correlation ID (host-chosen for CMD; echoed in ACK/NACK)
 * @param ts_ms     timestamp (board_millis)
 * @return total bytes written (header + payload), or 0 on insufficient space
 */
size_t proto_write_frame(uint8_t* out, size_t out_cap, uint8_t type,
                         const uint8_t* payload, uint16_t payload_len,
                         uint32_t seq, uint32_t ts_ms);

/**
 * @brief Wrapper for STREAM frames.
 */
size_t proto_write_stream_frame(uint8_t* out, size_t out_cap, const uint8_t* payload,
                                uint16_t payload_len, uint32_t seq, uint32_t ts_ms);

/**
 * @brief Apply a stream of 1-byte commands to a streaming flag.
 *        Unknown opcodes are ignored.
 * @param data   bytes received from host
 * @param len    number of bytes
 * @param io_streaming in/out: 1=on, 0=off; updated per commands
 */
void proto_apply_commands(const uint8_t* data, size_t len, uint8_t* io_streaming);

#ifdef __cplusplus
}
#endif
