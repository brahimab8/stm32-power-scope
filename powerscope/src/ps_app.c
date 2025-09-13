/**
 * @file    ps_app.c
 * @brief   Application wiring for the streaming core.
 *
 * Binds the transport (USB-CDC) and sensor (INA219) to the generic
 * streaming engine in ps_core.c, and runs it from the main loop.
 */

#include "app/ps_app.h"

#include <string.h>

#include "app/board.h"
#include "app/comm_usb_cdc.h"
#include "app/ina219.h"
#include "app/protocol_defs.h"
#include "app/ps_config.h"
#include "app/ps_core.h"

/* ---------- Instances ---------- */
static ps_core_t g_core;
static INA219_Ctx_t g_ina;

/* ---------- Ring buffer instances ---------- */
static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];

/* ---------- Transport adapters ---------- */
static int tx_write(const uint8_t* buf, uint16_t len) {
    return comm_usb_cdc_try_write(buf, len);
}
static bool link_ready(void) {
    return comm_usb_cdc_link_ready();
}
static uint16_t best_chunk(void) {
    return comm_usb_cdc_best_chunk();
}

/* ---------- INA219 I2C adapters (user_ctx is the bus token) ---------- */
static bool ina_read(void* user_ctx, uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
    return board_i2c_bus_read_reg((board_i2c_bus_t)user_ctx, addr, reg, buf, len);
}
static bool ina_write(void* user_ctx, uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
    return board_i2c_bus_write_reg((board_i2c_bus_t)user_ctx, addr, reg, buf, len);
}

/* ---------- Sensor adapters for core ---------- */
static bool sensor_read_bus_mV(uint16_t* out) {
    return INA219_ReadBusVoltage_mV(&g_ina, out) == INA219_OK;
}
static bool sensor_read_current_uA(int32_t* out) {
    return INA219_ReadCurrent_uA(&g_ina, out) == INA219_OK;
}

/* ---------- RX hook ---------- */
static void on_usb_rx(const uint8_t* d, uint32_t n) {
    ps_core_on_rx(&g_core, d, n);
}

/* ---------- App lifecycle ---------- */

void ps_app_init(void) {
    ps_core_init(&g_core, tx_mem, PS_TX_RING_CAP, rx_mem, PS_RX_RING_CAP);

    /* Bind dependencies */
    g_core.now_ms = board_millis;
    g_core.link_ready = link_ready;
    g_core.best_chunk = best_chunk;
    g_core.tx_write = tx_write;
    g_core.sensor_read_bus_mV = sensor_read_bus_mV;
    g_core.sensor_read_current_uA = sensor_read_current_uA;

    g_core.stream_period_ms = PS_STREAM_PERIOD_MS;
    g_core.max_payload = PROTO_MAX_PAYLOAD;

    /* USB transport */
    comm_usb_cdc_init();
    comm_usb_cdc_set_rx_handler(on_usb_rx);

    /* ---- INA219 init (deterministic, fail-fast) ---- */
    {
        const board_i2c_bus_t bus = board_i2c_default_bus();

        /* Sensor-private wiring/config */
        static const uint8_t INA_ADDR_7B = 0x40u;
        static const uint32_t INA_SHUNT_MOHM = 100u;           /* 0.1 Ω */
        static const uint16_t INA_CAL = 4096u;                 /* tune for Current_LSB */
        static const uint16_t INA_CFG = INA219_CONFIG_DEFAULT; /* shunt+bus continuous */

        INA219_Init_t init = {.i2c_read = ina_read,
                              .i2c_write = ina_write,
                              .i2c_user = (void*)bus,
                              .i2c_address = INA_ADDR_7B,
                              .shunt_milliohm = INA_SHUNT_MOHM,
                              .calibration = INA_CAL,
                              .config = INA_CFG};

        if (INA219_Init(&g_ina, &init) == INA219_OK) {
            g_core.sensor_ready = 1u;
        } else {
            g_core.sensor_ready = 0u;
            g_core.streaming = 0u; /* gate: disable streaming on failure */
        }
    }
}

void ps_app_tick(void) {
    ps_core_tick(&g_core);
}
