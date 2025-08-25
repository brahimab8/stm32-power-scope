/**
 * @file    ps_app.c
 * @brief   Streaming core: owns TX/RX rings, frames payloads (protocol),
 *          pumps USB-CDC (DTR-gated), and handles START/STOP commands.
 *
 */

#include "app/ps_app.h"

#include <string.h>

#include "app/board.h"
#include "app/comm_usb_cdc.h"
#include "app/protocol_defs.h"
#include "app/ps_config.h"
#include "app/ring_buffer.h"

static uint8_t s_streaming = 1;  // 1=on, 0=off
/* ---------- Ring buffer instances ---------- */
static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];
static rb_t txring;
static rb_t rxring;

static uint32_t s_seq = 0;

/* Copy N bytes from ring tail into dst without popping. */
static void rb_copy_from_tail(const rb_t* r, void* dst, uint16_t n) {
    uint16_t mask  = (uint16_t)(r->cap - 1);
    uint16_t t     = r->tail;
    uint16_t first = (uint16_t)((n < (r->cap - (t & mask))) ? n : (r->cap - (t & mask)));
    memcpy(dst, &r->buf[t & mask], first);
    if (first < n) memcpy((uint8_t*)dst + first, &r->buf[0], (size_t)n - first);
}

/* Enqueue a header-only reply (ACK/NACK). CRC is appended by proto_write_frame().
   'seq' echoes the CMD's seq. */
static void ps_send_hdr_only(uint8_t type, uint32_t req_seq) {
    uint8_t buf[sizeof(proto_hdr_t) + PROTO_CRC_LEN] __attribute__((aligned(4)));
    size_t n = proto_write_frame(buf, sizeof buf, type,
                                 /*payload*/NULL, /*len*/0,
                                 /*seq*/req_seq, board_millis());
    if (n) rb_write(&txring, buf, (uint16_t)n);
}

/* RX path: enqueue raw bytes from USB IRQ; parsed in main */
static void on_usb_rx(const uint8_t* d, uint32_t n) {
    rb_write(&rxring, d, (uint16_t)n);
}

/* Public-ish: wrap payload in header and enqueue to TX ring */
static void ps_send_frame(const uint8_t* payload, uint16_t payload_len) {
    uint8_t buf[sizeof(proto_hdr_t) + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN]
        __attribute__((aligned(4)));
    size_t n = 
            proto_write_stream_frame(buf, sizeof buf, payload, payload_len, s_seq++, board_millis());
    if (n) rb_write(&txring, buf, (uint16_t)n);
}

/* Parse complete framed CMDs from RX ring and reply with header-only ACK/NACK. */
static void ps_parse_commands(void) {
    for (;;) {
        uint16_t used = rb_used(&rxring);
        if (used < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) break;  /* need at least hdr+crc */

        /* Peek header to learn payload length (may wrap) */
        proto_hdr_t hdr;
        rb_copy_from_tail(&rxring, &hdr, (uint16_t)sizeof hdr);

        if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
            rb_pop(&rxring, 1);            /* resync on bad header */
            continue;
        }

        const uint16_t frame_len = (uint16_t)(PROTO_FRAME_OVERHEAD + hdr.len + PROTO_CRC_LEN);
        if (used < frame_len) break;       /* wait until the whole frame is present */

        /* Make contiguous copy (header + payload + CRC) */
        uint8_t tmp[PROTO_FRAME_OVERHEAD + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN];
        rb_copy_from_tail(&rxring, tmp, frame_len);

        /* Validate and extract payload (proto_parse_frame checks CRC) */
        proto_hdr_t hh;
        const uint8_t* pl = NULL;
        uint16_t pln = 0;
        size_t consumed = proto_parse_frame(tmp, frame_len, &hh, &pl, &pln);
        if (!consumed) {
            rb_pop(&rxring, 1);            /* bad CRC or header — resync */
            continue;
        }

        if (hh.type == PROTO_TYPE_CMD) {
            /* Strict: one opcode per frame (len must be exactly 1) */
            if (pln != 1) {
                ps_send_hdr_only(PROTO_TYPE_NACK, hh.seq);
            } else {
                uint8_t op = pl[0];
                switch (op) {
                    case PROTO_CMD_START: s_streaming = 1; ps_send_hdr_only(PROTO_TYPE_ACK,  hh.seq); break;
                    case PROTO_CMD_STOP:  s_streaming = 0; ps_send_hdr_only(PROTO_TYPE_ACK,  hh.seq); break;
                    default:                                 ps_send_hdr_only(PROTO_TYPE_NACK, hh.seq); break;
                }
            }
        }

        /* Consume exactly one whole frame (header + payload + CRC) */
        rb_pop(&rxring, (uint16_t)consumed);
    }
}

void ps_app_init(void) {
    rb_init(&txring, tx_mem, PS_TX_RING_CAP);
    rb_init(&rxring, rx_mem, PS_RX_RING_CAP);

    comm_usb_cdc_init();
    comm_usb_cdc_set_rx_handler(on_usb_rx);

    s_seq = 0;
}

/* Generate a small test payload → later swap with INA219 samples */
static void ps_fill_test_payload(uint8_t* dst, uint16_t len) {
    static uint8_t phase = 0;
    for (uint16_t i = 0; i < len; ++i) dst[i] = (uint8_t)(phase + i);
    phase += 1;
}

void ps_app_tick(void) {
    static uint32_t last_gen = 0;
    uint32_t now = board_millis();

    if (s_streaming && (uint32_t)(now - last_gen) >= PS_STREAM_PERIOD_MS) {
        last_gen = now;

        uint8_t payload[PS_STREAM_PAYLOAD_LEN];
        ps_fill_test_payload(payload, sizeof payload);

        ps_send_frame(payload, sizeof payload);
    }

    // Ship bytes to host when CONFIGURED + DTR + previous TX done
    comm_usb_cdc_pump(&txring);

    // Handle incoming host commands
    ps_parse_commands();
}
