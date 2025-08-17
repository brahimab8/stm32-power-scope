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

/* RX path: enqueue raw bytes from USB IRQ; parsed in main */
static void on_usb_rx(const uint8_t* d, uint32_t n) {
    rb_write(&rxring, d, (uint16_t)n);
}

/* Public-ish: wrap payload in header and enqueue to TX ring */
static void ps_send_frame(const uint8_t* payload, uint16_t payload_len) {
    uint8_t buf[sizeof(proto_stream_hdr_t) + PROTO_MAX_PAYLOAD] __attribute__((aligned(4)));
    size_t n =
        proto_write_stream_frame(buf, sizeof buf, payload, payload_len, s_seq++, board_millis());
    if (n) rb_write(&txring, buf, (uint16_t)n);
}

/* Bounded RX parsing: consume up to PS_CMD_BUDGET_PER_TICK bytes.
   Commands are 1-byte (START/STOP), so no partials; leftovers are handled next tick. */
static void ps_parse_commands(void) {
    uint16_t budget = PS_CMD_BUDGET_PER_TICK;
    while (budget) {
        const uint8_t* p;
        uint16_t n = rb_peek_linear(&rxring, &p);
        if (!n) break;
        if (n > budget) n = budget;

        proto_apply_commands(p, n, &s_streaming);
        rb_pop(&rxring, n);
        budget -= n;
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
