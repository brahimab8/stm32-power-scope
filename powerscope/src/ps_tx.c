#include "ps_tx.h"

#include <stdint.h>
#include <string.h>

/* helper: drop one whole frame from tx_buf. Return 1 if dropped, 0 otherwise. */
int drop_one_frame_buf(ps_buffer_if_t* buf) {
    if (!buf) return 0;
    if (!buf->size || !buf->copy || !buf->pop) return 0;

    uint16_t used = buf->size(buf->ctx);
    if (used < PROTO_HDR_LEN + PROTO_CRC_LEN) return 0;

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

/* --- initialize TX context --- */
bool ps_tx_init(ps_tx_ctx_t* ctx, ps_buffer_if_t* tx_buf, ps_tx_write_fn tx_write,
                ps_link_ready_fn link_ready, ps_best_chunk_fn best_chunk, uint16_t max_payload,
                uint8_t* response_slot_buf, uint16_t response_slot_cap) {
    if (!ctx || !tx_buf || !tx_write || !link_ready || !best_chunk || !response_slot_buf ||
        response_slot_cap < PROTO_FRAME_MAX_BYTES)
        return false;

    ctx->tx_buf = tx_buf;
    ctx->tx_write = tx_write;
    ctx->link_ready = link_ready;
    ctx->best_chunk = best_chunk;
    ctx->max_payload = max_payload;
    ctx->response_slot = response_slot_buf;
    ctx->response_slot_cap = response_slot_cap;
    ctx->response_len = 0;
    ctx->response_pending = false;

    return true;
}

/* --- enqueue any frame into TX ring --- */
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

    (void)buf->append(buf->ctx, frame, len);
}

void ps_tx_send_response(ps_tx_ctx_t* ctx, uint8_t type, uint8_t cmd_id, uint32_t req_seq,
                         uint32_t ts, const uint8_t* payload, uint16_t payload_len) {
    if (!ctx) return;

    if (payload_len > PROTO_MAX_PAYLOAD) payload_len = PROTO_MAX_PAYLOAD;

    size_t n = proto_write_frame(ctx->response_slot, ctx->response_slot_cap, type, cmd_id, payload,
                                 payload_len, req_seq, ts);
    if (n == 0 || n > ctx->response_slot_cap) return;

    ctx->response_len = (uint16_t)n;
    ctx->response_pending = true;
}

/* --- send stream: already using TX ring --- */
void ps_tx_send_stream(ps_tx_ctx_t* ctx, const uint8_t* payload, uint16_t payload_len, uint32_t ts,
                       uint32_t seq) {
    if (!ctx || !payload) return;
    if (ctx->max_payload != 0 && payload_len > ctx->max_payload) return;

    uint8_t tmp[PROTO_FRAME_MAX_BYTES];
    size_t n = proto_write_stream_frame(tmp, sizeof tmp, payload, payload_len, seq, ts);
    if (n && n <= UINT16_MAX) {
        ps_tx_enqueue_frame(ctx, tmp, (uint16_t)n);
    }
}

/* --- pump TX: send next whole frame if link ready --- */
void ps_tx_pump(ps_tx_ctx_t* ctx) {
    if (!ctx || !ctx->tx_write || !ctx->link_ready || !ctx->best_chunk) return;
    if (!ctx->link_ready()) return;

    // --- Send single-slot response if pending ---
    if (ctx->response_pending) {
        uint16_t chunk = ctx->best_chunk();
        if (ctx->response_len <= chunk) {
            int w = ctx->tx_write(ctx->response_slot, ctx->response_len);
            if (w > 0 && w == ctx->response_len) {
                ctx->response_pending = false;  // cleared
            }
        }
        return;  // send only one frame per pump
    }

    ps_buffer_if_t* buf = ctx->tx_buf;
    if (!buf || !buf->size || !buf->copy || !buf->peek_contiguous || !buf->pop) return;

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
