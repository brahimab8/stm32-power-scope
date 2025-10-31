/**
 * @file   ps_app.c
 * @brief  Application integration for Power Scope core.
 */

#include <board.h>
#include <protocol_defs.h>
#include <ps_app.h>
#include <ps_config.h>
#include <ps_core.h>
#include <ps_sensor_adapter.h>
#include <ps_sensor_config.h>
#include <ps_transport_adapter.h>
#include <ring_buffer_adapter.h>
#include <string.h>

#include "ps_buffer_if.h"
#include "ps_cmd_defs.h"
#include "ps_cmd_dispatcher.h"
#include "ps_cmd_parsers.h"
#include "ps_tx.h"

/* ---------- Instances ---------- */
static ps_core_t g_core;

/* ---------- TX/RX interfaces ---------- */
static ps_buffer_if_t tx_iface;
static ps_buffer_if_t rx_iface;

/* ---------- Ring buffer instances ---------- */
static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];
ps_ring_buffer_t tx_adapter;  // TODO: make static
static ps_ring_buffer_t rx_adapter;

/* ---------- Transport adapter ---------- */
static ps_transport_adapter_t g_transport;

/* --- TX context and sequence counter --- */
static ps_tx_ctx_t g_tx_ctx;
static uint32_t g_tx_seq = 0;

/* ---------- Command dispatcher ---------- */
static ps_cmd_dispatcher_t g_dispatcher;

/* ---------- Core RX hook ---------- */
static void transport_rx_cb(const uint8_t* data, uint32_t len) {
    ps_core_on_rx(&g_core, data, len);
}

/* ---------- Command Handlers (operate on ps_core state) ---------- */
static bool handle_start(const void* cmd_struct) {
    (void)cmd_struct;
    g_core.stream.streaming = 1;
    g_core.sm = CORE_SM_IDLE;
    return true;
}

static bool handle_stop(const void* cmd_struct) {
    (void)cmd_struct;
    g_core.stream.streaming = 0;
    g_core.sm = CORE_SM_IDLE;
    return true;
}

static bool handle_set_period(const void* cmd_struct) {
    const cmd_set_period_t* cmd = (const cmd_set_period_t*)cmd_struct;
    g_core.stream.period_ms = cmd->period_ms;
    return true;
}

/* ---------- App lifecycle ---------- */
void ps_app_init(void) {
    ps_core_init(&g_core);

    /* --- Command dispatcher --- */
    ps_cmds_init(&g_dispatcher);

    /* --- Command dispatcher wiring --- */
    ps_cmd_register_handler(&g_dispatcher, CMD_START, ps_parse_noarg, handle_start);
    ps_cmd_register_handler(&g_dispatcher, CMD_STOP, ps_parse_noarg, handle_stop);
    ps_cmd_register_handler(&g_dispatcher, CMD_SET_PERIOD, ps_parse_set_period, handle_set_period);

    g_core.dispatcher = &g_dispatcher;

    /* --- TX/RX buffers --- */
    ps_ring_buffer_init(&tx_adapter, tx_mem, PS_TX_RING_CAP, &tx_iface);
    ps_ring_buffer_init(&rx_adapter, rx_mem, PS_RX_RING_CAP, &rx_iface);

    /* --- Core dependencies --- */
    g_core.now_ms = board_millis;

    /* --- Initialize USB transport --- */
    board_transport_init(&g_transport);
    g_transport.set_rx_handler(transport_rx_cb);
    g_core.transport = &g_transport;

    /* --- Initialize TX module --- */
    ps_tx_init(&g_tx_ctx, &tx_iface,   /* TX ring buffer interface */
               g_transport.tx_write,   /* transport write callback */
               g_transport.link_ready, /* link ready callback */
               g_transport.best_chunk, /* max chunk callback */
               &g_tx_seq,              /* sequence counter */
               PROTO_MAX_PAYLOAD);     /* max payload */

    g_core.tx.ctx = &g_tx_ctx;
    g_core.tx.iface = &tx_iface;
    g_core.rx.iface = &rx_iface;

    /* --- Core configuration --- */
    g_core.stream.period_ms = PS_STREAM_PERIOD_MS;
    g_core.stream.max_payload = PROTO_MAX_PAYLOAD;

    /* --- Get sensor adapter from centralized module --- */
    g_core.stream.sensor = ps_get_sensor_adapter();
    g_core.sensor_ready = (g_core.stream.sensor != NULL);

    /* --- Debug LED callbacks --- */
    g_core.led_on = board_debug_led_on;
    g_core.led_off = board_debug_led_off;
    g_core.led_toggle = board_debug_led_toggle;
}

void ps_app_tick(void) {
    ps_core_tick(&g_core);
}
