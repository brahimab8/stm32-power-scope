/**
 * @file    framing.c
 * @brief   Framing helpers (STREAM/CMD/ACK/NACK) + CRC16.
 * @details proto_write_frame(): generic writer (len may be 0) + CRC trailer.
 *          proto_write_stream_frame(): STREAM wrapper.
 *          proto_parse_frame(): validate MAGIC/VER/LEN and CRC; expose payload.
 */
#include <protocol/framing.h>
#include <protocol/commands.h>
#include <byteio.h>
#include <ps_crc16.h>
#include <string.h>

/* Parse and validate a complete frame at buf[0..len). */
size_t proto_parse_frame(const uint8_t* buf, size_t len, proto_hdr_t* hdr_out,
                         const uint8_t** payload, uint16_t* payload_len) {
    if (!buf || len < PS_PROTOCOL_HDR_LEN + PS_PROTOCOL_CRC_LEN) return 0;

    proto_hdr_t h = {0};
    h.magic = byteio_rd_u16le(buf + PROTO_HDR_OFF_MAGIC);
    h.type = buf[PROTO_HDR_OFF_TYPE];
    h.ver = buf[PROTO_HDR_OFF_VER];
    h.len = byteio_rd_u16le(buf + PROTO_HDR_OFF_LEN);
    h.cmd_id = buf[PROTO_HDR_OFF_CMD_ID];
    h.rsv = buf[PROTO_HDR_OFF_RSV];
    h.seq = byteio_rd_u32le(buf + PROTO_HDR_OFF_SEQ);
    h.ts_ms = byteio_rd_u32le(buf + PROTO_HDR_OFF_TS_MS);

    if (h.magic != PS_PROTOCOL_MAGIC || h.ver != PS_PROTOCOL_VERSION) return 0;
    if (h.len > PS_PROTOCOL_MAX_PAYLOAD) return 0;

    const size_t span = PS_PROTOCOL_HDR_LEN + (size_t)h.len; /* hdr+payload */
    const size_t need = span + PS_PROTOCOL_CRC_LEN;          /* + CRC */
    if (len < need) return 0;                          /* incomplete */

    /* CRC check (LE) */
    uint16_t got = byteio_rd_u16le(buf + span);
    uint16_t calc = ps_crc16_le(buf, span, PS_CRC16_INIT);
    if (got != calc) return 0;

    if (hdr_out) *hdr_out = h;
    if (payload) *payload = buf + PS_PROTOCOL_HDR_LEN;
    if (payload_len) *payload_len = h.len;
    return need;
}

/* Find the first candidate frame start (magic word) in a byte buffer. */
size_t proto_find_frame_start(const uint8_t* buf, size_t len) {
    if (!buf || len < 2u) return SIZE_MAX;

    for (size_t i = 0; i + 1u < len; ++i) {
        if (byteio_rd_u16le(buf + i) == PS_PROTOCOL_MAGIC) return i;
    }

    return SIZE_MAX;
}

/* Generic writer: header + cmd_id + optional payload + CRC (LE). */
size_t proto_write_frame(uint8_t* out, size_t out_cap, uint8_t type, uint8_t cmd_id,
                         const uint8_t* payload, uint16_t payload_len, uint32_t seq,
                         uint32_t ts_ms) {
    if (!out) return 0;
    if (payload_len > PS_PROTOCOL_MAX_PAYLOAD) payload_len = PS_PROTOCOL_MAX_PAYLOAD;

    const size_t span = PS_PROTOCOL_HDR_LEN + (size_t)payload_len;
    const size_t need = span + PS_PROTOCOL_CRC_LEN;
    if (out_cap < need) return 0;

    byteio_wr_u16le(out + PROTO_HDR_OFF_MAGIC, PS_PROTOCOL_MAGIC);
    out[PROTO_HDR_OFF_TYPE] = type;
    out[PROTO_HDR_OFF_VER] = PS_PROTOCOL_VERSION;
    byteio_wr_u16le(out + PROTO_HDR_OFF_LEN, payload_len);
    out[PROTO_HDR_OFF_CMD_ID] = cmd_id;
    out[PROTO_HDR_OFF_RSV] = 0u;
    byteio_wr_u32le(out + PROTO_HDR_OFF_SEQ, seq);
    byteio_wr_u32le(out + PROTO_HDR_OFF_TS_MS, ts_ms);

    if (payload_len && payload) memcpy(out + PS_PROTOCOL_HDR_LEN, payload, payload_len);

    uint16_t crc = ps_crc16_le(out, span, PS_CRC16_INIT);
    byteio_wr_u16le(out + span, crc);

    return need;
}

/* STREAM wrapper. */
size_t proto_write_stream_frame(uint8_t* out, size_t out_cap, const uint8_t* payload,
                                uint16_t payload_len, uint32_t seq, uint32_t ts_ms) {
    return proto_write_frame(out, out_cap, PS_PROTOCOL_TYPE_STREAM, CMD_NONE, payload,
                             payload_len, seq, ts_ms);
}
