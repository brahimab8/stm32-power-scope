/**
 * @file    framing.h
 * @brief   Protocol frame parse/serialize helpers.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "protocol/header.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Parse and validate a complete protocol frame.
 *
 * Validation includes: MAGIC, VERSION, len <= PS_PROTOCOL_MAX_PAYLOAD,
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
size_t proto_parse_frame(const uint8_t* buf, size_t len, proto_hdr_t* hdr_out,
                         const uint8_t** payload, uint16_t* payload_len);

/**
 * @brief Find the first candidate frame start in a byte buffer.
 *
 * Scans for the protocol magic word and returns its byte offset within @p buf.
 *
 * @param buf  Buffer to scan.
 * @param len  Number of bytes available in @p buf.
 * @return Byte offset of the first candidate frame start, or SIZE_MAX if not found.
 */
size_t proto_find_frame_start(const uint8_t* buf, size_t len);

/**
 * @brief Write a full frame (header + optional payload) into 'out'.
 * @param type       PS_PROTOCOL_TYPE_STREAM / CMD / ACK / NACK
 * @param payload    payload bytes (may be NULL when payload_len==0, e.g., ACK/NACK)
 * @param payload_len number of payload bytes (<= PS_PROTOCOL_MAX_PAYLOAD)
 * @param seq        sequence number (for stream) /correlation ID (host-chosen for CMD; echoed in
 * ACK/NACK)
 * @param ts_ms      timestamp (board_millis)
 * @return total bytes written (header + payload), or 0 on insufficient space
 */
size_t proto_write_frame(uint8_t* out, size_t out_cap, uint8_t type, uint8_t cmd_id,
                         const uint8_t* payload, uint16_t payload_len, uint32_t seq,
                         uint32_t ts_ms);

/**
 * @brief Wrapper for STREAM frames.
 */
size_t proto_write_stream_frame(uint8_t* out, size_t out_cap, const uint8_t* payload,
                                uint16_t payload_len, uint32_t seq, uint32_t ts_ms);

#ifdef __cplusplus
}
#endif
