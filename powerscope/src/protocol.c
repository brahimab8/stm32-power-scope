/**
 * @file    protocol.c
 * @brief   Framing helpers (STREAM/CMD/ACK/NACK) + CRC16.
 * @details proto_write_frame(): generic writer (len may be 0) + CRC trailer.
 *          proto_write_stream_frame(): STREAM wrapper.
 *          proto_parse_frame(): validate MAGIC/VER/LEN and CRC; expose payload.
 *          proto_apply_commands(): apply 1-byte START/STOP to a flag.
 *          No rings or hardware here.
 */
#include <string.h>

#include "app/protocol_defs.h"
#include "app/ps_crc16.h"

/* Parse and validate a complete frame at buf[0..len). */
size_t proto_parse_frame(const uint8_t* buf, size_t len, proto_hdr_t* hdr_out,
                         const uint8_t** payload, uint16_t* payload_len) {
    if (!buf || len < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) return 0;

    proto_hdr_t h;
    memcpy(&h, buf, sizeof h);

    if (h.magic != PROTO_MAGIC || h.ver != PROTO_VERSION) return 0;
    if (h.len > PROTO_MAX_PAYLOAD) return 0;

    const size_t span = PROTO_FRAME_OVERHEAD + (size_t)h.len; /* hdr+payload */
    const size_t need = span + PROTO_CRC_LEN;                 /* + CRC */
    if (len < need) return 0;                                 /* incomplete */

    /* CRC check (LE) */
    uint16_t got = (uint16_t)buf[need - 2] | ((uint16_t)buf[need - 1] << 8);
    uint16_t calc = ps_crc16_le(buf, span, PS_CRC16_INIT);
    if (got != calc) return 0;

    if (hdr_out) *hdr_out = h;
    if (payload) *payload = buf + PROTO_FRAME_OVERHEAD;
    if (payload_len) *payload_len = h.len;
    return need;
}

/* Generic writer: header + optional payload + CRC (LE). */
size_t proto_write_frame(uint8_t* out, size_t out_cap, uint8_t type, const uint8_t* payload,
                         uint16_t payload_len, uint32_t seq, uint32_t ts_ms) {
    if (!out) return 0;
    if (payload_len > PROTO_MAX_PAYLOAD) payload_len = PROTO_MAX_PAYLOAD;

    const size_t span = PROTO_FRAME_OVERHEAD + (size_t)payload_len; /* hdr+payload */
    const size_t need = span + PROTO_CRC_LEN;                       /* + CRC */
    if (out_cap < need) return 0;

    proto_hdr_t h;
    h.magic = PROTO_MAGIC;
    h.type = type;
    h.ver = PROTO_VERSION;
    h.len = payload_len;
    h.rsv = 0;
    h.seq = seq;
    h.ts_ms = ts_ms;

    memcpy(out, &h, sizeof h);
    if (payload_len && payload) memcpy(out + sizeof h, payload, payload_len);

    /* append CRC16/CCITT-FALSE (LE) over header+payload */
    uint16_t crc = ps_crc16_le(out, span, PS_CRC16_INIT);
    out[span + 0] = (uint8_t)(crc & 0xFF);
    out[span + 1] = (uint8_t)(crc >> 8);

    return need;
}

/* STREAM wrapper. */
size_t proto_write_stream_frame(uint8_t* out, size_t out_cap, const uint8_t* payload,
                                uint16_t payload_len, uint32_t seq, uint32_t ts_ms) {
    return proto_write_frame(out, out_cap, PROTO_TYPE_STREAM, payload, payload_len, seq, ts_ms);
}

/* Apply 1-byte START/STOP opcodes (payload of a CMD frame). */
void proto_apply_commands(const uint8_t* data, size_t len, uint8_t* io_streaming) {
    if (!data || !io_streaming) return;
    for (size_t i = 0; i < len; ++i) {
        switch (data[i]) {
            case PROTO_CMD_START:
                *io_streaming = 1;
                break;
            case PROTO_CMD_STOP:
                *io_streaming = 0;
                break;
            default:
                break;
        }
    }
}
