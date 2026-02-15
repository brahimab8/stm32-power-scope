/**
 * @file    ps_core.c
 * @brief   Generic streaming core: transport- and sensor-agnostic logic.
 *
 * Owns TX/RX rings, frames payloads according to the protocol,
 * pumps the transport, and parses & applies incoming CMD frames.
 */

#include <byteio.h>
#include <protocol_defs.h>
#include <ps_buffer_if.h>
#include <ps_config.h>
#include <ps_core.h>
#include <sensor/adapter.h>
#include <ps_transport_adapter.h>
#include <ps_tx.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "ps_errors.h"

/* ---------- Init / RX ---------- */

void ps_core_init(ps_core_t* c) {
    if (!c) return;
    memset(c, 0, sizeof(*c));
}

void ps_core_attach_buffers(ps_core_t* c, ps_buffer_if_t* tx, ps_buffer_if_t* rx) {
    if (!c) return;
    c->tx.iface = tx;
    c->rx.iface = rx;
}

void ps_core_on_rx(ps_core_t* c, const uint8_t* d, uint32_t n) {
    if (!c || !d || n == 0U || !c->rx.iface || !c->rx.iface->append) return;

    uint16_t wlen = (n > UINT16_MAX) ? UINT16_MAX : (uint16_t)n;
    (void)c->rx.iface->append(c->rx.iface->ctx, d, wlen);
}

static void handle_cmd_frame(ps_core_t* c, const proto_hdr_t* hdr, const uint8_t* payload,
                             uint16_t len) {
    if (!c || !c->dispatcher || !c->tx.ctx) return;

    // --- Reject oversized payload immediately ---
    if (hdr->type == PROTO_TYPE_CMD && len > PROTO_MAX_PAYLOAD) {
        uint32_t now = (c->now_ms != NULL) ? c->now_ms() : 0U;
        uint8_t resp = PS_ERR_INVALID_LEN;
        ps_tx_send_nack(c->tx.ctx, hdr->cmd_id, hdr->seq, now, &resp, 1);
        return;
    }

    uint8_t resp[PROTO_MAX_PAYLOAD] = {0};
    uint16_t resp_len = PROTO_MAX_PAYLOAD;

    bool handled =
        c->dispatcher->dispatch(c->dispatcher, hdr->cmd_id, payload, len, resp, &resp_len);

    uint32_t now = (c->now_ms != NULL) ? c->now_ms() : 0U;

    if (handled) {
        ps_tx_send_ack(c->tx.ctx, hdr->cmd_id, hdr->seq, now, resp, resp_len);
    } else {
        if (resp_len == 0) {
            resp[0] = PS_ERR_INVALID_CMD;
            resp_len = 1;
        }
        ps_tx_send_nack(c->tx.ctx, hdr->cmd_id, hdr->seq, now, resp, resp_len);
    }
}

static void ps_core_process_rx(ps_core_t* c) {
    if (!c || !c->rx.iface || !c->tx.iface) return;

    const uint8_t* data = NULL;

    while (c->rx.iface->size(c->rx.iface->ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN)) {
        uint16_t contiguous = c->rx.iface->peek_contiguous(c->rx.iface->ctx, &data);
        if (contiguous < (PROTO_HDR_LEN + PROTO_CRC_LEN)) break;

        // Look for MAGIC to ensure frame alignment
        uint16_t magic = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
        if (magic != PROTO_MAGIC) {
            // Scan for next MAGIC in buffer
            size_t offset = 1;
            while (offset + 1 < contiguous) {
                uint16_t m = (uint16_t)data[offset] | ((uint16_t)data[offset + 1] << 8);
                if (m == PROTO_MAGIC) break;
                offset++;
            }
            c->rx.iface->pop(c->rx.iface->ctx, (uint16_t)offset);
            continue;
        }

        // Attempt to parse frame
        proto_hdr_t hdr;
        const uint8_t* payload = NULL;
        uint16_t payload_len = 0;

        size_t frame_len = proto_parse_frame(data, contiguous, &hdr, &payload, &payload_len);
        if (frame_len == 0) {
            break;  // incomplete or invalid frame
        }

        // Handle CMD frames
        if (hdr.type == PROTO_TYPE_CMD) {
            handle_cmd_frame(c, &hdr, payload, payload_len);
        }

        // Pop fully parsed frame
        c->rx.iface->pop(c->rx.iface->ctx, (uint16_t)frame_len);
    }
}

/* ---------- Per-sensor streaming state machine ---------- */
static void sm_handle_idle(ps_core_sensor_stream_t* s, uint32_t now) {
    if ((uint32_t)(now - s->last_emit_ms) >= s->period_ms) {
        s->sm = CORE_SM_SENSOR_START;
    }
}

static void sm_handle_sensor_start(ps_core_sensor_stream_t* s) {
    int res = (s->adapter->start) ? s->adapter->start(s->adapter->ctx) : CORE_SENSOR_READY;

    if (res == CORE_SENSOR_READY)
        s->sm = CORE_SM_READY;
    else if (res == CORE_SENSOR_BUSY)
        s->sm = CORE_SM_SENSOR_POLL;
    else
        s->sm = CORE_SM_ERROR;
}

static void sm_handle_sensor_poll(ps_core_sensor_stream_t* s) {
    int res = (s->adapter->poll) ? s->adapter->poll(s->adapter->ctx) : CORE_SENSOR_READY;

    if (res == CORE_SENSOR_READY)
        s->sm = CORE_SM_READY;
    else if (res == CORE_SENSOR_BUSY)
        ;  // stay in POLL
    else
        s->sm = CORE_SM_ERROR;
}

static void sm_handle_ready(ps_core_t* c, ps_core_sensor_stream_t* s, uint32_t now)
{
    if (!c || !s || !c->build_stream_payload || !c->tx.ctx) {
        s->sm = CORE_SM_IDLE;
        return;
    }

    uint8_t frame[PROTO_FRAME_MAX_BYTES];

    // --- Fill sample buffer ---
    uint8_t sample_buf[PROTO_MAX_PAYLOAD - 1]; // reserve 1 byte for runtime_id
    size_t sample_len = s->adapter->fill(s->adapter->ctx, sample_buf, sizeof(sample_buf));
    if (sample_len == 0) {
        // skip this cycle if sensor not ready
        s->sm = CORE_SM_IDLE;
        return;
    } 

    // --- Build payload ---
    size_t n = c->build_stream_payload(s->runtime_id, sample_buf, sample_len, frame, sizeof(frame));

    if (n > 0) {
        ps_tx_send_stream(c->tx.ctx, frame, (uint16_t)n, now, s->seq);
        s->seq++;
        s->last_emit_ms = now;
    }

    s->sm = CORE_SM_IDLE;
}

static void sm_handle_error(ps_core_sensor_stream_t* s) {
    if (!s) return;
    s->streaming = 0;
    s->sm = CORE_SM_IDLE;
}

/* ---------- Tick (main loop) ---------- */

void ps_core_tick(ps_core_t* c) {
    if (!c || !c->now_ms) return;

    ps_core_process_rx(c);

    const uint32_t now = c->now_ms();

    // Loop over all sensors
    for (uint8_t i = 0; i < c->num_sensors; ++i) {
        ps_core_sensor_stream_t* s = &c->sensors[i];

        if (!s->ready || !s->streaming) continue;

        switch (s->sm) {
            case CORE_SM_IDLE:
                sm_handle_idle(s, now);
                break;
            case CORE_SM_SENSOR_START:
                sm_handle_sensor_start(s);
                break;
            case CORE_SM_SENSOR_POLL:
                sm_handle_sensor_poll(s);
                break;
            case CORE_SM_READY:
                sm_handle_ready(c, s, now);
                break;
            case CORE_SM_ERROR:
                sm_handle_error(s);
                break;
        }
    }

    if (c->tx.ctx) {
        ps_tx_pump(c->tx.ctx);
    }
}
