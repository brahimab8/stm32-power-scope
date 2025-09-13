/**
 * @file    ps_core.c
 * @file    ps_core.c
 * @brief   Generic streaming core: transport- and sensor-agnostic logic.
 *
 * Owns the TX/RX rings, frames payloads according to the protocol,
 * pumps the transport, and parses incoming START/STOP commands.
 * Hardware access is provided via function pointers.
 */

#include "app/ps_core.h"

#include <string.h>

#include "app/byteio.h"
#include "app/protocol_defs.h"

/* ---------- Init / RX ---------- */

void ps_core_init(ps_core_t* c, uint8_t* tx_mem, uint16_t tx_cap, uint8_t* rx_mem,
                  uint16_t rx_cap) {
    if (!c) return;
    (void)memset(c, 0, sizeof *c);
    rb_init(&c->tx, tx_mem, tx_cap);
    rb_init(&c->rx, rx_mem, rx_cap);

    /* Defaults (caller may override fields after init) */
    c->streaming = 0u;
    c->sensor_ready = 0u;
    c->seq = 0u;
    c->last_emit_ms = 0u;
}

void ps_core_on_rx(ps_core_t* c, const uint8_t* d, uint32_t n) {
    if (!c || !d || (n == 0u)) return;
    (void)rb_write_try(&c->rx, d, (uint16_t)n);
}

/* ---------- TX helpers (frame-aware) ---------- */

/* Drop exactly one frame (oldest) from a ring that stores protocol frames. */
static int tx_drop_one_frame(rb_t* r) {
    uint16_t used = rb_used(r);
    if (used < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) return 0;

    /* Peek header */
    proto_hdr_t hdr;
    rb_copy_from_tail(r, &hdr, (uint16_t)sizeof hdr);

    /* If header looks bad, resync by one byte. */
    if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
        rb_pop(r, 1);
        return 1;
    }

    const uint16_t frame_len = (uint16_t)(PROTO_FRAME_OVERHEAD + hdr.len + PROTO_CRC_LEN);
    if (used < frame_len) return 0; /* incomplete frame present */

    rb_pop(r, frame_len);
    return 1;
}

/* Enqueue a completed frame (hdr+payload+CRC) into tx ring with frame-aware drop-oldest. */
static void tx_enqueue_frame(ps_core_t* c, const uint8_t* frame, uint16_t frame_len) {
    if (!c || !frame) return;

    /* Must fit into usable capacity (cap-1). If not, just drop it. */
    if (frame_len == 0 || frame_len >= rb_capacity(&c->tx)) return;

    /* Make room by dropping whole frames until enough space exists. */
    while (rb_free(&c->tx) < frame_len) {
        if (!tx_drop_one_frame(&c->tx)) {
            /* If we can’t drop a full frame (e.g., garbage), clear as last resort. */
            rb_clear(&c->tx);
            break;
        }
    }

    /* Enqueue atomically; no partial writes. */
    (void)rb_write_try(&c->tx, frame, frame_len);
}

/* Enqueue a header-only reply (ACK/NACK). CRC is appended by proto_write_frame().
   'seq' echoes the CMD's seq. */
static void ps_send_hdr_only(ps_core_t* c, uint8_t type, uint32_t req_seq) {
    uint8_t buf[sizeof(proto_hdr_t) + PROTO_CRC_LEN] __attribute__((aligned(4)));
    const uint32_t now = c->now_ms ? c->now_ms() : 0u;
    size_t n = proto_write_frame(buf, sizeof buf, type,
                                 /*payload*/ NULL, /*len*/ 0,
                                 /*seq*/ req_seq, now);
    if ((n != 0u) && (n <= UINT16_MAX)) {
        tx_enqueue_frame(c, buf, (uint16_t)n);
    }
}

/*  TX pump (frame-aware, transport-agnostic).
    Assumes higher-level sanity ensures: frame_len <= best_chunk(). */
static void tx_pump(ps_core_t* c) {
    if (!c || !c->link_ready || !c->tx_write || !c->best_chunk) return;
    if (!c->link_ready()) return;

    /* Need at least a header+CRC */
    uint16_t used = rb_used(&c->tx);
    if (used < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) return;

    /* Peek header to compute full frame_len */
    proto_hdr_t hdr;
    rb_copy_from_tail(&c->tx, &hdr, (uint16_t)sizeof hdr);

    if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
        rb_pop(&c->tx, 1); /* resync */
        return;
    }

    const uint16_t frame_len = (uint16_t)(PROTO_FRAME_OVERHEAD + hdr.len + PROTO_CRC_LEN);
    if (used < frame_len) return; /* incomplete frame in ring */

    /* Make sure we can send it in one write (guaranteed by sanity checks) */
    if (frame_len > c->best_chunk()) return;

    /* Try a contiguous send; if wrap, copy to a temp and send */
    const uint8_t* p = NULL;
    uint16_t linear = rb_peek_linear(&c->tx, &p);

    if (linear >= frame_len) {
        int w = c->tx_write(p, frame_len);
        if (w == (int)frame_len) {
            rb_pop(&c->tx, frame_len);
        }
        /* if 0/busy: just return and try next tick */
    } else {
        uint8_t tmp[PROTO_FRAME_MAX_BYTES];
        rb_copy_from_tail(&c->tx, tmp, frame_len);
        int w = c->tx_write(tmp, frame_len);
        if (w == (int)frame_len) rb_pop(&c->tx, frame_len);
    }
}

/*  Build STREAM frame and enqueue to TX ring */
static void ps_send_frame(ps_core_t* c, const uint8_t* payload, size_t payload_len) {
    uint8_t buf[sizeof(proto_hdr_t) + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN]
        __attribute__((aligned(4)));
    const uint32_t now = c->now_ms ? c->now_ms() : 0u;
    size_t n =
        proto_write_stream_frame(buf, sizeof buf, payload, (uint16_t)payload_len, c->seq++, now);
    if (n) tx_enqueue_frame(c, buf, (uint16_t)n);
}

/* ---------- CMD parser ---------- */

static void ps_parse_commands(ps_core_t* c) {
    for (;;) {
        uint16_t used = rb_used(&c->rx);
        if (used < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) break;

        /* Peek header to learn length */
        proto_hdr_t hdr;
        rb_copy_from_tail(&c->rx, &hdr, (uint16_t)sizeof hdr);

        if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
            rb_pop(&c->rx, 1); /* resync on bad header */
            continue;
        }

        const uint16_t frame_len = (uint16_t)(PROTO_FRAME_OVERHEAD + hdr.len + PROTO_CRC_LEN);
        if (used < frame_len) break; /* incomplete */

        /* Copy the whole candidate frame into a temp buffer, then parse+CRC */
        uint8_t tmp[PROTO_FRAME_OVERHEAD + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN];
        rb_copy_from_tail(&c->rx, tmp, frame_len);

        /* Validate and extract payload (proto_parse_frame checks CRC) */
        proto_hdr_t hh;
        const uint8_t* pl = NULL;
        uint16_t pln = 0;
        size_t consumed = proto_parse_frame(tmp, frame_len, &hh, &pl, &pln);
        if (!consumed) {
            rb_pop(&c->rx, 1); /* bad CRC or header — resync */
            continue;
        }

        if (hh.type == PROTO_TYPE_CMD) {
            /* Strict: one opcode per frame (len must be exactly 1) */
            if (pln != 1) {
                ps_send_hdr_only(c, PROTO_TYPE_NACK, hh.seq);
            } else {
                uint8_t op = pl[0];
                switch (op) {
                    case PROTO_CMD_START:
                        if (c->sensor_ready != 0u) {
                            c->streaming = 1u;
                            ps_send_hdr_only(c, PROTO_TYPE_ACK, hh.seq);
                        } else {
                            /* sensor not initialized; refuse to start */
                            ps_send_hdr_only(c, PROTO_TYPE_NACK, hh.seq);
                        }
                        break;
                    case PROTO_CMD_STOP:
                        c->streaming = 0;
                        ps_send_hdr_only(c, PROTO_TYPE_ACK, hh.seq);
                        break;
                    default:
                        ps_send_hdr_only(c, PROTO_TYPE_NACK, hh.seq);
                        break;
                }
            }
        }

        rb_pop(&c->rx, (uint16_t)consumed); /* drop exactly one full frame */
    }
}

/* ---------- Periodic streaming helper ---------- */

/* 6-byte payload (little-endian):
   [0..1]  u16 bus_mV
   [2..5]  i32 current_uA
*/
static void ps_fill_sensor_payload(ps_core_t* c, uint8_t* dst, size_t len) {
    if (len < 6u) {
        (void)memset(dst, 0, len);
        return;
    }

    uint16_t bus_mV = 0u;
    int32_t current_uA = 0;

    /* Read BUS voltage and CURRENT (depends on CALIBRATION & mode) */
    if (!(c->sensor_read_bus_mV && c->sensor_read_bus_mV(&bus_mV))) {
        bus_mV = 0u;
    }
    if (!(c->sensor_read_current_uA && c->sensor_read_current_uA(&current_uA))) {
        current_uA = 0;
    }

    /* Serialize LE */
    byteio_wr_u16le(&dst[0], bus_mV);
    byteio_wr_i32le(&dst[2], current_uA);

    /* Zero any extra bytes */
    if (len > 6u) {
        (void)memset(&dst[6], 0, (size_t)(len - 6u));
    }
}

/* ---------- Tick ---------- */

void ps_core_tick(ps_core_t* c) {
    if (!c) return;

    /* Periodic streaming */
    const uint32_t now = c->now_ms ? c->now_ms() : 0u;
    if (c->streaming && (uint32_t)(now - c->last_emit_ms) >= c->stream_period_ms) {
        c->last_emit_ms = now;

        uint8_t payload[46]; /* current build uses 6 bytes; max payload guarded by caller */
        ps_fill_sensor_payload(c, payload, 6u);
        ps_send_frame(c, payload, 6u);
    }

    /* TX pump */
    tx_pump(c);

    /* Handle incoming host commands */
    ps_parse_commands(c);
}
