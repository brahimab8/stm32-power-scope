#include "ps_tx.h"

#include <stdint.h>
#include <string.h>

#include "ps_crc16.h" /* if proto_write_frame uses CRC helper (already used by protocol_defs) */

/* helper: drop one whole frame from tx_buf. Return 1 if dropped, 0 otherwise. */
int drop_one_frame_buf(ps_buffer_if_t* buf) {
    if (!buf) return 0;
    if (!buf->size || !buf->copy || !buf->pop) return 0;

    uint16_t used = buf->size(buf->ctx);
    if (used < PROTO_HDR_LEN + PROTO_CRC_LEN) return 0;

    /* Peek header (copy first bytes) */
    proto_hdr_t hdr;
    buf->copy(buf->ctx, &hdr, (uint16_t)sizeof hdr);

    if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
        /* garbage: pop one byte to resync */
        buf->pop(buf->ctx, 1);
        return 1;
    }

    uint16_t frame_len = (uint16_t)(PROTO_HDR_LEN + hdr.len + PROTO_CRC_LEN);
    if (used < frame_len) return 0; /* incomplete, don't drop */
    buf->pop(buf->ctx, frame_len);
    return 1;
}

bool ps_tx_init(ps_tx_ctx_t* ctx, ps_buffer_if_t* tx_buf, ps_tx_write_fn tx_write,
                ps_link_ready_fn link_ready, ps_best_chunk_fn best_chunk, uint32_t* seq_ptr,
                uint16_t max_payload) {
    if (!ctx || !tx_buf || !tx_write || !link_ready || !best_chunk) return false;
    ctx->tx_buf = tx_buf;
    ctx->tx_write = tx_write;
    ctx->link_ready = link_ready;
    ctx->best_chunk = best_chunk;
    ctx->seq_ptr = seq_ptr;
    ctx->max_payload = max_payload;
    return true;
}

void ps_tx_enqueue_frame(ps_tx_ctx_t* ctx, const uint8_t* frame, uint16_t len) {
    if (!ctx || !frame || len == 0) return;
    ps_buffer_if_t* buf = ctx->tx_buf;
    if (!buf || !buf->capacity || !buf->space || !buf->append || !buf->clear) return;

    uint16_t cap = buf->capacity(buf->ctx);
    if (cap == 0 || len > (cap - 1)) return;

    /* Make room by dropping whole frames until enough space */
    while (buf->space(buf->ctx) < len) {
        if (!drop_one_frame_buf(buf)) {
            buf->clear(buf->ctx);
            break;
        }
    }

    /* Attempt append (may fail if race) */
    (void)buf->append(buf->ctx, frame, len);
}

void ps_tx_send_hdr(ps_tx_ctx_t* ctx, uint8_t type, uint32_t req_seq, uint32_t ts) {
    if (!ctx) return;
    uint8_t tmp[PROTO_HDR_LEN + PROTO_CRC_LEN];
    size_t n = proto_write_frame(tmp, sizeof tmp, type, NULL, 0, req_seq, ts);
    if (n && n <= UINT16_MAX) {
        ps_tx_enqueue_frame(ctx, tmp, (uint16_t)n);
    }
}

void ps_tx_send_stream(ps_tx_ctx_t* ctx, const uint8_t* payload, uint16_t payload_len,
                       uint32_t ts) {
    if (!ctx || !payload) return;
    if (ctx->max_payload != 0 && payload_len > ctx->max_payload) return;

    uint8_t tmp[PROTO_FRAME_MAX_BYTES];
    uint32_t seq = ctx->seq_ptr ? *(ctx->seq_ptr) : 0;
    size_t n = proto_write_stream_frame(tmp, sizeof tmp, payload, payload_len, seq, ts);
    if (n && n <= UINT16_MAX) {
        ps_tx_enqueue_frame(ctx, tmp, (uint16_t)n);
        if (ctx->seq_ptr) {
            /* increment sequence (caller-provided location) */
            (*(ctx->seq_ptr))++;
        }
    }
}

void ps_tx_pump(ps_tx_ctx_t* ctx) {
    if (!ctx || !ctx->tx_buf || !ctx->tx_write || !ctx->link_ready || !ctx->best_chunk) return;
    ps_buffer_if_t* buf = ctx->tx_buf;
    if (!buf->size || !buf->copy || !buf->peek_contiguous || !buf->pop) return;

    if (!ctx->link_ready()) return;

    uint16_t used = buf->size(buf->ctx);
    if (used < PROTO_HDR_LEN + PROTO_CRC_LEN) return;

    proto_hdr_t hdr;
    buf->copy(buf->ctx, &hdr, (uint16_t)sizeof hdr);

    if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
        buf->pop(buf->ctx, 1); /* resync */
        return;
    }

    uint16_t frame_len = (uint16_t)(PROTO_HDR_LEN + hdr.len + PROTO_CRC_LEN);
    uint16_t chunk = ctx->best_chunk();
    if (used < frame_len || frame_len > chunk) return;

    const uint8_t* p = NULL;
    uint16_t linear = buf->peek_contiguous(buf->ctx, &p);

    if (linear >= frame_len && p != NULL) {
        int w = ctx->tx_write(p, frame_len);
        if (w > 0 && w == (int)frame_len) buf->pop(buf->ctx, frame_len);
    } else {
        uint8_t tmp[PROTO_FRAME_MAX_BYTES];
        buf->copy(buf->ctx, tmp, frame_len);
        int w = ctx->tx_write(tmp, frame_len);
        if (w > 0 && w == (int)frame_len) buf->pop(buf->ctx, frame_len);
    }
}
