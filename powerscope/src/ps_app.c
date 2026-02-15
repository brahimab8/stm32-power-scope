/**
 * @file   ps_app.c
 * @brief  Application integration for Power Scope core.
 */

#include <board.h>
#include <protocol_defs.h>
#include <ps_app.h>
#include <ps_config.h>
#include "ps_core.h"
#include "sensor/adapter.h"
#include "sensor/ina219/config.h"
#include "sensor/registry.h"
#include "sensor/defs.h" 

#include <ps_transport_adapter.h>
#include <ring_buffer_adapter.h>
#include <string.h>

#include "ps_buffer_if.h"
#include "ps_cmd_defs.h"
#include "ps_cmd_dispatcher.h"
#include "ps_cmd_parsers.h"
#include "ps_errors.h"
#include "ps_tx.h"

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
static uint8_t tx_response_slot[PROTO_FRAME_MAX_BYTES];

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

/* ---------- Helper: find sensor by runtime ID ---------- */
static ps_core_sensor_stream_t* get_sensor_by_runtime_id(uint8_t runtime_id) {
    for (uint8_t i = 0; i < g_core.num_sensors; ++i) {
        if (g_core.sensors[i].runtime_id == runtime_id) {
            return &g_core.sensors[i];
        }
    }
    return NULL;
}


/* Build the payload of a sensor reading */
size_t ps_app_build_sensor_payload(uint8_t runtime_id,
                                   const uint8_t* sample_buf,
                                   size_t sample_len,
                                   uint8_t* out,
                                   size_t cap)
{
    if (!sample_buf || !out || cap < (sample_len + 1))
        return 0;

    out[0] = runtime_id;
    memcpy(out + 1, sample_buf, sample_len);

    return sample_len + 1;
}


/* ---------- Command Handlers ---------- */

static bool handle_ping(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    (void)cmd_struct;             // no payload
    if (resp_len) *resp_len = 0;  // empty ACK
    return true;                  // ACK
}

// Start streaming for all sensors
static bool handle_start(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_start_t* cmd = (const cmd_start_t*)cmd_struct;
    ps_core_sensor_stream_t* s = get_sensor_by_runtime_id(cmd->sensor_id);
    if (!s) {
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_INVALID_VALUE;
        if (resp_len) *resp_len = 1;
        return false;  // NACK
    }

    if (resp_len) *resp_len = 0;

    // Initialize streaming state
    s->streaming = 1;
    s->sm = CORE_SM_IDLE;
    s->seq = 0;
    // board_debug_led_toggle();

    return true;  // ACK
}

static bool handle_stop(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_stop_t* cmd = (const cmd_stop_t*)cmd_struct;
    ps_core_sensor_stream_t* s = get_sensor_by_runtime_id(cmd->sensor_id);
    if (!s) {
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_INVALID_VALUE;
        if (resp_len) *resp_len = 1;
        return false;  // NACK
    }

    if (resp_len) *resp_len = 0;

    // Stop streaming
    s->streaming = 0;
    s->sm = CORE_SM_IDLE;
    return true;  // ACK
}

static bool handle_set_period(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_set_period_t* cmd = (const cmd_set_period_t*)cmd_struct;
    ps_core_sensor_stream_t* s = get_sensor_by_runtime_id(cmd->sensor_id);

    if (!s) {
        /* NACK: invalid sensor id */
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_INVALID_VALUE;
        if (resp_len) *resp_len = 1;
        return false;
    }

    /* validate period range */
    if (cmd->period_ms < PS_STREAM_PERIOD_MIN_MS || cmd->period_ms > PS_STREAM_PERIOD_MAX_MS) {
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_INVALID_VALUE;
        if (resp_len) *resp_len = 1;
        return false;
    }

    /* apply */
    s->period_ms = cmd->period_ms;

    /* ACK with zero-length payload (important!!) */
    if (resp_len) *resp_len = 0;
    return true;
}

static bool handle_get_period(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_get_period_t* cmd = (const cmd_get_period_t*)cmd_struct;
    ps_core_sensor_stream_t* s = get_sensor_by_runtime_id(cmd->sensor_id);

    if (!s) {
        /* NACK */
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_INVALID_VALUE;
        if (resp_len) *resp_len = 1;
        return false;
    }

    if (!resp_buf || !resp_len || *resp_len < (int)sizeof(uint32_t)) {
        /* NACK overflow */
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_OVERFLOW;
        if (resp_len) *resp_len = 1;
        return false;
    }

    /* return 32-bit period in little-endian as defined by protocol */
    uint32_t period = s->period_ms;
    memcpy(resp_buf, &period, sizeof(period));
    if (resp_len) *resp_len = sizeof(period);
    return true;
}

// Get sensor info for all sensors
static bool handle_get_sensors(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    (void)cmd_struct;

    // Each sensor contributes 2 bytes: runtime_id + type_id
    if (!resp_buf || !resp_len || *resp_len < (2 * g_core.num_sensors)) {
        if (resp_buf && resp_len && *resp_len >= 1) resp_buf[0] = PS_ERR_OVERFLOW;
        if (resp_len) *resp_len = 1;
        return false;  // NACK
    }

    for (uint8_t i = 0; i < g_core.num_sensors; ++i) {
        ps_core_sensor_stream_t* s = &g_core.sensors[i];
        resp_buf[2 * i + 0] = s->runtime_id;                            // runtime_id
        resp_buf[2 * i + 1] = s->adapter ? s->adapter->type_id : 0xFF;  // static type_id
    }

    *resp_len = 2 * g_core.num_sensors;
    return true;  // ACK
}

// Read sensor sample on demand (non-streaming)
static bool handle_read_sensor(const void* cmd_struct,
                               uint8_t* resp_buf,
                               uint16_t* resp_len)
{
    const cmd_read_sensor_t* cmd = cmd_struct;

    if (!resp_buf || !resp_len || *resp_len == 0)
        return false;

    ps_core_sensor_stream_t* s = get_sensor_by_runtime_id(cmd->sensor_id);
    if (!s || !s->adapter) {
        resp_buf[0] = PS_ERR_INVALID_VALUE;
        *resp_len = 1;
        return false;
    }

    /* Reject if sensor is already streaming */
    if (s->streaming) {
        resp_buf[0] = PS_ERR_SENSOR_BUSY;
        *resp_len = 1;
        return false;
    }

    /* --- Start sensor --- */
    int res = s->adapter->start(s->adapter->ctx);
    if (res == CORE_SENSOR_ERROR) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1;
        return false;
    }

    /* --- Poll until ready or error --- */
    while (res == CORE_SENSOR_BUSY) {
        res = s->adapter->poll(s->adapter->ctx);
        if (res == CORE_SENSOR_ERROR) {
            resp_buf[0] = PS_ERR_INTERNAL;
            *resp_len = 1;
            return false;
        }
    }

    /* --- Fill sample buffer --- */
    uint8_t sample_buf[PROTO_MAX_PAYLOAD - 1]; // reserve 1 byte for runtime_id
    size_t filled = s->adapter->fill(s->adapter->ctx, sample_buf, sizeof(sample_buf));
    if (filled == 0) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1;
        return false;
    }

    /* --- Build payload --- */
    size_t n = ps_app_build_sensor_payload(s->runtime_id, sample_buf, filled, resp_buf, *resp_len);
    if (n == 0) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1;
        return false;
    }

    *resp_len = n;
    return true;
}

// Get uptime in milliseconds since boot
static bool handle_get_uptime(const void* cmd_struct,
                              uint8_t* resp_buf,
                              uint16_t* resp_len)
{
    (void)cmd_struct;

    if (!resp_buf || !resp_len || *resp_len < sizeof(uint32_t)) {
        if (resp_buf && resp_len && *resp_len >= 1)
            resp_buf[0] = PS_ERR_OVERFLOW;
        if (resp_len) *resp_len = 1;
        return false;
    }

    uint32_t uptime = board_millis();

    memcpy(resp_buf, &uptime, sizeof(uptime));
    *resp_len = sizeof(uptime);

    return true;   // ACK
}


/* ---------- Helper: initialize sensors ---------- */

static void ps_app_init_sensors(ps_core_t* core) {
    ps_core_sensor_stream_t* sensors = core->sensors;

    // Sensor 1
    sensors[0].runtime_id  = 1;

    sensors[0].adapter     = ps_sensor_registry_get(PS_SENSOR_TYPE_INA219);

    sensors[0].ready       = (sensors[0].adapter != NULL);
    sensors[0].streaming   = 0;
    sensors[0].sm          = CORE_SM_IDLE;
    sensors[0].period_ms   = PS_STREAM_PERIOD_MS;
    sensors[0].default_period_ms = PS_STREAM_PERIOD_MS;
    sensors[0].max_payload = PROTO_MAX_PAYLOAD;
    sensors[0].last_emit_ms = 0;

    core->num_sensors = 1;
}


/* ---------- App lifecycle ---------- */
void ps_app_init(void) {

    /* --- Initialize core context --- */
    ps_core_init(&g_core);

    /* --- Command dispatcher --- */
    ps_cmds_init(&g_dispatcher);

    /* --- Command dispatcher wiring --- */
    ps_cmd_register_handler(&g_dispatcher, CMD_START, ps_parse_sensor_id, handle_start);
    ps_cmd_register_handler(&g_dispatcher, CMD_STOP, ps_parse_sensor_id, handle_stop);
    ps_cmd_register_handler(&g_dispatcher, CMD_GET_PERIOD, ps_parse_sensor_id, handle_get_period);
    ps_cmd_register_handler(&g_dispatcher, CMD_SET_PERIOD, ps_parse_set_period, handle_set_period);
    ps_cmd_register_handler(&g_dispatcher, CMD_PING, ps_parse_noarg, handle_ping);
    ps_cmd_register_handler(&g_dispatcher, CMD_GET_SENSORS, ps_parse_noarg, handle_get_sensors);
    ps_cmd_register_handler(&g_dispatcher, CMD_READ_SENSOR, ps_parse_sensor_id, handle_read_sensor);

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
               PROTO_MAX_PAYLOAD,      /* max payload */
               tx_response_slot,       /* response slot buffer */
               sizeof(tx_response_slot));
    g_core.tx.ctx = &g_tx_ctx;
    g_core.tx.iface = &tx_iface;
    g_core.rx.iface = &rx_iface;

    /* --- Core Sensors configuration --- */
    ps_app_init_sensors(&g_core);
    
    /* --- Frame builder callback --- */
    g_core.build_stream_payload = ps_app_build_sensor_payload;

    /* --- Debug LED callbacks --- */
    g_core.led_on = board_debug_led_on;
    g_core.led_off = board_debug_led_off;
    g_core.led_toggle = board_debug_led_toggle;
}

void ps_app_tick(void) {
    ps_core_tick(&g_core);
}
