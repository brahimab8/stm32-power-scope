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
#include <ps_sensor_adapter.h>
#include <ps_transport_adapter.h>
#include <ps_tx.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

/* ---------- Init / RX ---------- */

void ps_core_init(ps_core_t* c) {
    if (!c) return;
    memset(c, 0, sizeof *c);
    c->sm = CORE_SM_IDLE;
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

/* ---------- Internal helpers ---------- */

static bool handle_cmd_payload(ps_core_t* c, const uint8_t* payload, uint16_t len) {
    if (!c || !payload || len == 0) return false;

    bool handled = false;

    for (uint16_t i = 0; i < len; ++i) {
        switch (payload[i]) {
            case PROTO_CMD_START:
                c->cmd.streaming_requested = 1;
                handled = true;
                break;
            case PROTO_CMD_STOP:
                c->cmd.streaming_requested = 0;
                handled = true;
                break;
            /* future commands go here */
            default:
                break;
        }
    }

    return handled;
}

static void handle_cmd_frame(ps_core_t* c, const proto_hdr_t* hdr, const uint8_t* payload,
                             uint16_t len) {
    bool handled = handle_cmd_payload(c, payload, len);
    uint8_t resp_type = handled ? PROTO_TYPE_ACK : PROTO_TYPE_NACK;

    if (c->tx.ctx != NULL) {
        ps_tx_send_hdr(c->tx.ctx, resp_type, hdr->seq, (c->now_ms != NULL) ? c->now_ms() : 0U);
    }
}

static void ps_core_process_rx(ps_core_t* c) {
    if (!c || !c->rx.iface || !c->tx.iface) return;

    const uint8_t* data = NULL;

    while (c->rx.iface->size(c->rx.iface->ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN)) {
        uint16_t contiguous = c->rx.iface->peek_contiguous(c->rx.iface->ctx, &data);
        if (contiguous < (PROTO_HDR_LEN + PROTO_CRC_LEN)) break;

        proto_hdr_t hdr;
        const uint8_t* payload = NULL;
        uint16_t payload_len = 0;

        size_t frame_len = proto_parse_frame(data, contiguous, &hdr, &payload, &payload_len);
        if (frame_len == 0) {
            c->rx.iface->pop(c->rx.iface->ctx, 1);
            continue;
        }

        if (hdr.type == PROTO_TYPE_CMD && payload && payload_len > 0U) {
            handle_cmd_frame(c, &hdr, payload, payload_len);
        }

        c->rx.iface->pop(c->rx.iface->ctx, (uint16_t)frame_len);
    }
}

static void update_streaming_state(ps_core_t* c) {
    if (c->cmd.streaming_requested && c->sensor_ready && c->stream.sensor) {
        c->cmd.streaming = 1;
    } else {
        c->cmd.streaming = 0;
    }
}

static void sm_handle_idle(ps_core_t* c, uint32_t now) {
    if ((uint32_t)(now - c->stream.last_emit_ms) >= c->stream.period_ms) {
        c->sm = CORE_SM_SENSOR_START;
    }
}

static void sm_handle_sensor_start(ps_core_t* c) {
    int res = (c->stream.sensor->start) ? c->stream.sensor->start(c->stream.sensor->ctx) : 1;

    if (res > 0) {
        c->sm = CORE_SM_READY;
    } else if (res == 0) {
        c->sm = CORE_SM_SENSOR_POLL;
    } else {
        c->sm = CORE_SM_ERROR;
    }
}

static void sm_handle_sensor_poll(ps_core_t* c) {
    int res = (c->stream.sensor->poll) ? c->stream.sensor->poll(c->stream.sensor->ctx) : 1;

    if (res > 0) {
        c->sm = CORE_SM_READY;
    } else if (res < 0) {
        c->sm = CORE_SM_ERROR;
    }
}

static void sm_handle_ready(ps_core_t* c, uint32_t now) {
    if (c->stream.sensor->fill) {
        uint8_t payload[PROTO_MAX_PAYLOAD];
        size_t want = (c->stream.max_payload && c->stream.max_payload < PS_STREAM_PAYLOAD_LEN)
                          ? c->stream.max_payload
                          : PS_STREAM_PAYLOAD_LEN;

        size_t filled = c->stream.sensor->fill(c->stream.sensor->ctx, payload, want);
        if (filled > 0) {
            if (filled > want) filled = want;
            if (c->tx.ctx) {
                ps_tx_send_stream(c->tx.ctx, payload, (uint16_t)filled, now);
            }
        }
    }
    c->stream.last_emit_ms = now;
    c->sm = CORE_SM_IDLE;
}

static void sm_handle_error(ps_core_t* c) {
    if (!c) return;
    c->sm = CORE_SM_IDLE;
}

/* ---------- Tick (main loop) ---------- */

void ps_core_tick(ps_core_t* c) {
    if (!c || !c->now_ms) return;

    ps_core_process_rx(c);

    const uint32_t now = c->now_ms();

    update_streaming_state(c);

    if (c->cmd.streaming) {
        switch (c->sm) {
            case CORE_SM_IDLE:
                sm_handle_idle(c, now);
                break;
            case CORE_SM_SENSOR_START:
                sm_handle_sensor_start(c);
                break;
            case CORE_SM_SENSOR_POLL:
                sm_handle_sensor_poll(c);
                break;
            case CORE_SM_READY:
                sm_handle_ready(c, now);
                break;
            case CORE_SM_ERROR:
                sm_handle_error(c);
                break;
        }
    }

    if (c->tx.ctx) {
        ps_tx_pump(c->tx.ctx);
    }
}
