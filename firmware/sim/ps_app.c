/**
 * @file   ps_app.c
 * @brief  Application integration for Power Scope core.
 */

#include "board.h"
#include "protocol_defs.h"
#include "ps_app.h"
#include "ps_core.h"
#include "drivers/defs.h"
#include "drivers/ina219/driver.h"
#include "ps_buffer_if.h"
#include "ps_cmd_dispatcher.h"
#include "ps_cmd_handlers.h"
#include "ps_config.h"
#include "ps_payload.h"
#include "ps_transport_adapter.h"
#include "ps_tx.h"
#include "ring_buffer_adapter.h"
#include "sensor/adapter.h"
#include "sensor/registry.h"
#include "sensors/ina219/fake.h"


static ps_core_t g_core;

static ps_buffer_if_t tx_iface;
static ps_buffer_if_t rx_iface;

static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];
static ps_ring_buffer_t tx_adapter;
static ps_ring_buffer_t rx_adapter;
static uint8_t tx_response_slot[PROTO_FRAME_MAX_BYTES];

static ps_transport_adapter_t g_transport;

static ps_tx_ctx_t g_tx_ctx;

static ps_cmd_dispatcher_t g_dispatcher;

static void transport_rx_cb(const uint8_t* data, uint32_t len) {
	ps_core_on_rx(&g_core, data, len);
}

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
		sensors[registered].max_payload = PROTO_MAX_PAYLOAD;
		sensors[registered].last_emit_ms = 0u;
		registered++;
	}

	core->num_sensors = registered;
}

void ps_app_init(void) {
	fake_ina219_init();
	ps_core_init(&g_core);

	ps_cmds_init(&g_dispatcher);
	ps_cmd_handlers_register(&g_core, &g_dispatcher);

	g_core.dispatcher = &g_dispatcher;

	ps_ring_buffer_init(&tx_adapter, tx_mem, PS_TX_RING_CAP, &tx_iface);
	ps_ring_buffer_init(&rx_adapter, rx_mem, PS_RX_RING_CAP, &rx_iface);

	g_core.now_ms = board_millis;

	board_transport_init(&g_transport);
	g_transport.set_rx_handler(transport_rx_cb);
	g_core.transport = &g_transport;

	ps_tx_init(&g_tx_ctx,
			   &tx_iface,
			   g_transport.tx_write,
			   g_transport.link_ready,
			   g_transport.best_chunk,
			   PROTO_MAX_PAYLOAD,
			   tx_response_slot,
			   sizeof(tx_response_slot));

	g_core.tx.ctx = &g_tx_ctx;
	g_core.tx.iface = &tx_iface;
	g_core.rx.iface = &rx_iface;

	ps_app_init_sensors(&g_core);
	g_core.build_stream_payload = ps_payload_build_sensor;

	g_core.led_on = board_debug_led_on;
	g_core.led_off = board_debug_led_off;
	g_core.led_toggle = board_debug_led_toggle;
}

void ps_app_tick(void) {
	fake_ina219_tick();
	ps_core_tick(&g_core);
}

