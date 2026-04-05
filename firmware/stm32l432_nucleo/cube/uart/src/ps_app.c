/**
 * @file   ps_app.c
 * @brief  Application integration for Power Scope core.
 */

#include <board.h>
#include <protocol/framing.h>
#include <protocol/responses.h>
#include <ps_app.h>
#include "ps_core.h"
#include "drivers/defs.h"
#include "drivers/ina219/driver.h"
#include "ps_buffer_if.h"
#include "ps_cmd_dispatcher.h"
#include "ps_cmd_handlers.h"
#include "ps_config.h"
#include "ps_transport_adapter.h"
#include "ps_tx.h"
#include "ring_buffer_adapter.h"
#include "sensor/adapter.h"
#include "sensor/registry.h"


/* ---------- Instances ---------- */
static ps_core_t g_core;

/* ---------- TX/RX interfaces ---------- */
static ps_buffer_if_t tx_iface;
static ps_buffer_if_t rx_iface;

/* ---------- Ring buffer instances ---------- */
static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];
static ps_ring_buffer_t tx_adapter;
static ps_ring_buffer_t rx_adapter;

/* ---------- Response-Buffer ---------- */
static uint8_t tx_response_slot[PS_PROTOCOL_FRAME_MAX_BYTES];

/* ---------- Transport adapter ---------- */
static ps_transport_adapter_t g_transport;

/* --- TX context --- */
static ps_tx_ctx_t g_tx_ctx;

/* ---------- Command dispatcher ---------- */
static ps_cmd_dispatcher_t g_dispatcher;

/* ---------- Core RX hook ---------- */
static void transport_rx_cb(const uint8_t* data, uint32_t len) {
    ps_core_on_rx(&g_core, data, len);
}

static size_t ps_app_build_stream_payload(uint8_t runtime_id, const uint8_t* sample_buf,
                                          size_t sample_len, uint8_t* out, size_t cap) {
    return ps_resp_encode_sensor_packet(out, cap, runtime_id, sample_buf, sample_len);
}

/* ---------- Helper: initialize sensors ---------- */

static void ps_app_init_sensors(ps_core_t* core) {
    /* Instance table: define all sensor instances to be used */
    typedef struct {
        uint8_t runtime_id;
        ps_ina219_config_t config;
    } sensor_instance_t;

    static const sensor_instance_t instances[] = {
        {1u, {.i2c_addr = 0x40u, .shunt_milliohm = 100u, .calibration = 4096u}},
        {2u, {.i2c_addr = 0x41u, .shunt_milliohm = 100u, .calibration = 4096u}},
    };

    static const uint8_t num_instances = sizeof(instances) / sizeof(instances[0]);
    ps_core_sensor_stream_t* sensors = core->sensors;
    uint8_t registered = 0u;

    /* Register each instance via registry */
    for (uint8_t i = 0u; (i < num_instances) && (i < PS_CORE_MAX_SENSORS); ++i) {
        ps_sensor_adapter_t* adapter =
            ps_sensor_registry_get(PS_SENSOR_TYPE_INA219, (const void*)&instances[i].config);
        if (adapter == NULL) {
            continue;
        }

        sensors[registered].runtime_id = instances[i].runtime_id;
        sensors[registered].adapter = adapter;
        sensors[registered].ready = 1u;
        sensors[registered].streaming = 0u;
        sensors[registered].sm = CORE_SM_IDLE;
        sensors[registered].period_ms = PS_STREAM_PERIOD_MS;
        sensors[registered].default_period_ms = PS_STREAM_PERIOD_MS;
        sensors[registered].max_payload = PS_PROTOCOL_MAX_PAYLOAD;
        sensors[registered].last_emit_ms = 0u;
        registered++;
    }

    core->num_sensors = registered;
}


/* ---------- App lifecycle ---------- */
void ps_app_init(void) {

    /* --- Initialize core context --- */
    ps_core_init(&g_core);

    /* --- Command dispatcher --- */
    ps_cmds_init(&g_dispatcher);
    ps_cmd_handlers_register(&g_core, &g_dispatcher);

    g_core.dispatcher = &g_dispatcher;

    /* --- TX/RX buffers --- */
    ps_ring_buffer_init(&tx_adapter, tx_mem, PS_TX_RING_CAP, &tx_iface);
    ps_ring_buffer_init(&rx_adapter, rx_mem, PS_RX_RING_CAP, &rx_iface);

    /* --- Core dependencies --- */
    g_core.now_ms = board_millis;

    /* --- Initialize transport --- */
    board_transport_init(&g_transport);
    g_transport.set_rx_handler(transport_rx_cb);
    g_core.transport = &g_transport;

    /* --- Initialize TX module --- */
    ps_tx_init(&g_tx_ctx, &tx_iface,   /* TX ring buffer interface */
               g_transport.tx_write,   /* transport write callback */
               g_transport.link_ready, /* link ready callback */
               g_transport.best_chunk, /* max chunk callback */
               PS_PROTOCOL_MAX_PAYLOAD, /* max payload */
               tx_response_slot,       /* response slot buffer */
               sizeof(tx_response_slot));
    g_core.tx.ctx = &g_tx_ctx;
    g_core.tx.iface = &tx_iface;
    g_core.rx.iface = &rx_iface;

    /* --- Core Sensors configuration --- */
    ps_app_init_sensors(&g_core);
    
    /* --- Frame builder callback --- */
    g_core.build_stream_payload = ps_app_build_stream_payload;

    /* --- Debug LED callbacks --- */
    g_core.led_on = board_debug_led_on;
    g_core.led_off = board_debug_led_off;
    g_core.led_toggle = board_debug_led_toggle;
}

void ps_app_tick(void) {
    ps_core_tick(&g_core);
}
