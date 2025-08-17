/**
 * @file    protocol.c
 * @brief   Minimal framing + command helpers for USB-CDC streaming.
 * @details proto_write_stream_frame(): wraps payload with 16-byte header (MAGIC 0x5AA5, LE).
 *          proto_apply_commands(): applies 1-byte START/STOP to a streaming flag.
 *          Pure helpers; no global state or hardware access.
 */
#include "app/protocol_defs.h"
#include <string.h>

size_t proto_write_stream_frame(uint8_t* out, size_t out_cap,
                                const uint8_t* payload, uint16_t payload_len,
                                uint32_t seq, uint32_t ts_ms)
{
    if (!out || !payload || payload_len == 0) return 0;
    if (payload_len > PROTO_MAX_PAYLOAD)      payload_len = PROTO_MAX_PAYLOAD;

    const size_t need = sizeof(proto_stream_hdr_t) + (size_t)payload_len;
    if (out_cap < need) return 0;

    proto_stream_hdr_t h;
    h.magic = PROTO_MAGIC;
    h.type  = PROTO_TYPE_STREAM;
    h.ver   = PROTO_VERSION;
    h.len   = payload_len;
    h.rsv   = 0;
    h.seq   = seq;
    h.ts_ms = ts_ms;

    memcpy(out, &h, sizeof h);
    memcpy(out + sizeof h, payload, payload_len);
    return need;
}

void proto_apply_commands(const uint8_t* data, size_t len, uint8_t* io_streaming)
{
    if (!data || !io_streaming) return;
    for (size_t i = 0; i < len; ++i) {
        switch (data[i]) {
            case PROTO_CMD_START: *io_streaming = 1; break;
            case PROTO_CMD_STOP:  *io_streaming = 0; break;
            default: break;
        }
    }
}
