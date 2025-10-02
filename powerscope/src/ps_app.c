/**
 * @file   ps_app.c
 * @brief  Application integration for Power Scope core.
 */

#include <board.h>
#include <byteio.h>
#include <ina219.h>
#include <protocol_defs.h>
#include <ps_app.h>
#include <ps_config.h>
#include <ps_core.h>
#include <ps_sensor_adapter.h>
#include <ps_sensor_mgr.h>
#include <ps_transport_adapter.h>
#include <ring_buffer_adapter.h>
#include <string.h>

#include "ps_buffer_if.h"
#include "ps_tx.h"

/* ---------- Instances ---------- */
static ps_core_t g_core;
static sensor_mgr_ctx_t g_sensor_mgr;
static INA219_Ctx_t g_ina;
static ps_sensor_adapter_t g_sensor_adapter;

/* ---------- Sensor buffer ---------- */
static uint8_t g_sensor_buf[6];  // u16 + i32

/* ---------- TX/RX interfaces ---------- */
static ps_buffer_if_t tx_iface;
static ps_buffer_if_t rx_iface;

/* ---------- Ring buffer instances ---------- */
static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];
static ps_ring_buffer_t tx_adapter;
static ps_ring_buffer_t rx_adapter;

/* ---------- Transport adapter ---------- */
static ps_transport_adapter_t g_transport;

/* --- TX context and sequence counter --- */
static ps_tx_ctx_t g_tx_ctx;
static uint32_t g_tx_seq = 0;

/* ---------- INA219 hardware read adapter ---------- */
static bool hw_read_sample(void* user_ctx, void* out) {
    uint16_t bus_mV;
    int32_t current_uA;
    (void)user_ctx;

    if (INA219_ReadBusVoltage_mV(&g_ina, &bus_mV) != INA219_OK) return false;
    if (INA219_ReadCurrent_uA(&g_ina, &current_uA) != INA219_OK) return false;

    uint8_t* buf = (uint8_t*)out;
    byteio_wr_u16le(&buf[0], bus_mV);
    byteio_wr_i32le(&buf[2], current_uA);

    return true;
}

/* ---------- Sensor manager interface for INA219 ---------- */
static sensor_iface_t sensor_iface = {
    .hw_ctx = &g_ina, .read_sample = hw_read_sample, .sample_size = sizeof(g_sensor_buf)};

/* ---------- Core RX hook ---------- */
static void transport_rx_cb(const uint8_t* data, uint32_t len) {
    ps_core_on_rx(&g_core, data, len);
}

/* ---------- App lifecycle ---------- */
void ps_app_init(void) {
    ps_core_init(&g_core);

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

    g_core.tx.ctx = &g_tx_ctx; /* connect core to TX module */
    g_core.tx.iface = &tx_iface;
    g_core.rx.iface = &rx_iface;

    /* --- Core configuration --- */
    g_core.stream.period_ms = PS_STREAM_PERIOD_MS;
    g_core.stream.max_payload = PROTO_MAX_PAYLOAD;

    /* --- INA219 init --- */
    {
        const board_i2c_bus_t bus = board_i2c_default_bus();
        INA219_Init_t init = {.i2c_read = board_i2c_bus_read_reg,
                              .i2c_write = board_i2c_bus_write_reg,
                              .i2c_user = (void*)bus,
                              .i2c_address = 0x40U,
                              .shunt_milliohm = 100U,
                              .calibration = 4096U,
                              .config = INA219_CONFIG_DEFAULT};

        if (INA219_Init(&g_ina, &init) != INA219_OK) {
            g_core.sensor_ready = 0;
            g_core.cmd.streaming = 0;
            return;
        }
    }

    /* --- Bind sensor manager --- */
    if (sensor_mgr_init(&g_sensor_mgr, sensor_iface, g_sensor_buf, board_millis)) {
        g_sensor_adapter = sensor_mgr_as_adapter(&g_sensor_mgr);  // store value in static
        g_core.stream.sensor = &g_sensor_adapter;                 // pointer in core
        g_core.sensor_ready = 1;
    } else {
        g_core.sensor_ready = 0;
        g_core.cmd.streaming = 0;
    }

    /* --- Debug LED callbacks --- */
    g_core.led_on = board_debug_led_on;
    g_core.led_off = board_debug_led_off;
    g_core.led_toggle = board_debug_led_toggle;
}

void ps_app_tick(void) {
    ps_core_tick(&g_core);
}
