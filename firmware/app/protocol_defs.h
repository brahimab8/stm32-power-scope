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
#define PROTO_TYPE_STREAM 0u   /* room for more types later */
#define PROTO_MAX_PAYLOAD 512u /* per-frame cap we use today */

/* --- 16-byte packed header --- */
typedef struct __attribute__((packed)) {
    uint16_t magic; /* PROTO_MAGIC */
    uint8_t type;   /* PROTO_TYPE_STREAM */
    uint8_t ver;    /* PROTO_VERSION */
    uint16_t len;   /* payload bytes (<= PROTO_MAX_PAYLOAD) */
    uint16_t rsv;   /* 0 for now */
    uint32_t seq;   /* host can spot gaps */
    uint32_t ts_ms; /* device time (board_millis) */
} proto_stream_hdr_t;

/* --- commands (1-byte opcodes) --- */
typedef enum {
    PROTO_CMD_START = 0x01,
    PROTO_CMD_STOP = 0x02,
} proto_cmd_t;

/* --- helpers --- */

/**
 * @brief Write a full stream frame (header+payload) into 'out'.
 * @param out       destination buffer
 * @param out_cap   capacity of 'out' in bytes
 * @param payload   payload bytes
 * @param payload_len number of payload bytes (<= PROTO_MAX_PAYLOAD)
 * @param seq       sequence number
 * @param ts_ms     timestamp (board_millis)
 * @return total bytes written (header + payload), or 0 on insufficient space
 *
 * Note: copies header via memcpy; 'out' can be any alignment.
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
