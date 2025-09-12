/**
 * @file    ps_app.c
 * @brief   Streaming core: owns TX/RX rings, frames payloads (protocol),
 *          pumps USB-CDC (DTR-gated), and handles START/STOP commands.
 *
 */

#include "app/ps_app.h"

#include <string.h>

#include "app/board.h"
#include "app/byteio.h"
#include "app/comm_usb_cdc.h"
#include "app/ina219.h"
#include "app/protocol_defs.h"
#include "app/ps_config.h"
#include "app/ring_buffer.h"

static INA219_Ctx_t g_ina;

static uint8_t s_streaming = 0;    // 1=on, 0=off
static uint8_t s_sensor_ready = 0; /* 1=INA219 init OK, 0=not ready */
static uint32_t s_seq = 0;

/* ---------- Ring buffer instances ---------- */
static uint8_t tx_mem[PS_TX_RING_CAP];
static uint8_t rx_mem[PS_RX_RING_CAP];
static rb_t txring;
static rb_t rxring;

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
static void tx_enqueue_frame(const uint8_t* frame, uint16_t frame_len) {
    /* Must fit into usable capacity (cap-1). If not, just drop it. */
    if (frame_len == 0 || frame_len >= rb_capacity(&txring)) return;

    /* Make room by dropping whole frames until enough space exists. */
    while (rb_free(&txring) < frame_len) {
        if (!tx_drop_one_frame(&txring)) {
            /* If we can’t drop a full frame (e.g., garbage), clear as last resort. */
            rb_clear(&txring);
            break;
        }
    }

    /* Enqueue atomically; no partial writes. */
    (void)rb_write_try(&txring, frame, frame_len);
}

/* Enqueue a header-only reply (ACK/NACK). CRC is appended by proto_write_frame().
   'seq' echoes the CMD's seq. */
static void ps_send_hdr_only(uint8_t type, uint32_t req_seq) {
    uint8_t buf[sizeof(proto_hdr_t) + PROTO_CRC_LEN] __attribute__((aligned(4)));
    size_t n = proto_write_frame(buf, sizeof buf, type,
                                 /*payload*/ NULL, /*len*/ 0,
                                 /*seq*/ req_seq, board_millis());
    if ((n != 0u) && (n <= UINT16_MAX)) {
        tx_enqueue_frame(buf, (uint16_t)n);
    }
}

/*  TX pump (frame-aware, transport-agnostic).
    Assumes ps_sanity.c ensures: frame_len <= comm_usb_cdc_best_chunk(). */
static void tx_pump(void) {
    if (!comm_usb_cdc_link_ready()) return;

    /* Need at least a header+CRC */
    uint16_t used = rb_used(&txring);
    if (used < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) return;

    /* Peek header to compute full frame_len */
    proto_hdr_t hdr;
    rb_copy_from_tail(&txring, &hdr, (uint16_t)sizeof hdr);

    if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
        rb_pop(&txring, 1); /* resync */
        return;
    }

    const uint16_t frame_len = (uint16_t)(PROTO_FRAME_OVERHEAD + hdr.len + PROTO_CRC_LEN);
    if (used < frame_len) return; /* incomplete frame in ring */

    /* Make sure we can send it in one write (guaranteed by sanity checks in ps_sanity.c) */
    if (frame_len > comm_usb_cdc_best_chunk()) return;

    /* Try a contiguous send; if wrap, copy to a temp and send */
    const uint8_t* p = NULL;
    uint16_t linear = rb_peek_linear(&txring, &p);

    if (linear >= frame_len) {
        int w = comm_usb_cdc_try_write(p, frame_len);
        if (w == (int)frame_len) {
            rb_pop(&txring, frame_len);
        }
        /* if 0/busy: just return and try next tick */
    } else {
        uint8_t tmp[PROTO_FRAME_MAX_BYTES];
        rb_copy_from_tail(&txring, tmp, frame_len);
        int w = comm_usb_cdc_try_write(tmp, frame_len);
        if (w == (int)frame_len) rb_pop(&txring, frame_len);
    }
}

/* ---------- ISR RX hook ---------- */

/* USB RX ISR → write to RX ring with no-overwrite (drop-newest on pressure). */
static void on_usb_rx(const uint8_t* d, uint32_t n) {
    (void)rb_write_try(&rxring, d, (uint16_t)n);
}

/*  Build STREAM frame and enqueue to TX ring */

static void ps_send_frame(const uint8_t* payload, size_t payload_len) {
    uint8_t buf[sizeof(proto_hdr_t) + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN]
        __attribute__((aligned(4)));
    size_t n =
        proto_write_stream_frame(buf, sizeof buf, payload, payload_len, s_seq++, board_millis());
    if (n) tx_enqueue_frame(buf, (uint16_t)n);
}

/* ---------- CMD parser ---------- */

static void ps_parse_commands(void) {
    for (;;) {
        uint16_t used = rb_used(&rxring);
        if (used < PROTO_FRAME_OVERHEAD + PROTO_CRC_LEN) break;

        /* Peek header to learn length */
        proto_hdr_t hdr;
        rb_copy_from_tail(&rxring, &hdr, (uint16_t)sizeof hdr);

        if (hdr.magic != PROTO_MAGIC || hdr.ver != PROTO_VERSION || hdr.len > PROTO_MAX_PAYLOAD) {
            rb_pop(&rxring, 1); /* resync on bad header */
            continue;
        }

        const uint16_t frame_len = (uint16_t)(PROTO_FRAME_OVERHEAD + hdr.len + PROTO_CRC_LEN);
        if (used < frame_len) break; /* incomplete */

        /* Copy the whole candidate frame into a temp buffer, then parse+CRC */
        uint8_t tmp[PROTO_FRAME_OVERHEAD + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN];
        rb_copy_from_tail(&rxring, tmp, frame_len);

        /* Validate and extract payload (proto_parse_frame checks CRC) */
        proto_hdr_t hh;
        const uint8_t* pl = NULL;
        uint16_t pln = 0;
        size_t consumed = proto_parse_frame(tmp, frame_len, &hh, &pl, &pln);
        if (!consumed) {
            rb_pop(&rxring, 1); /* bad CRC or header — resync */
            continue;
        }

        if (hh.type == PROTO_TYPE_CMD) {
            /* Strict: one opcode per frame (len must be exactly 1) */
            if (pln != 1) {
                ps_send_hdr_only(PROTO_TYPE_NACK, hh.seq);
            } else {
                uint8_t op = pl[0];
                switch (op) {
                    case PROTO_CMD_START:
                        if (s_sensor_ready != 0u) {
                            s_streaming = 1u;
                            ps_send_hdr_only(PROTO_TYPE_ACK, hh.seq);
                        } else {
                            /* sensor not initialized; refuse to start */
                            ps_send_hdr_only(PROTO_TYPE_NACK, hh.seq);
                        }
                        break;
                    case PROTO_CMD_STOP:
                        s_streaming = 0;
                        ps_send_hdr_only(PROTO_TYPE_ACK, hh.seq);
                        break;
                    default:
                        ps_send_hdr_only(PROTO_TYPE_NACK, hh.seq);
                        break;
                }
            }
        }

        rb_pop(&rxring, (uint16_t)consumed); /* drop exactly one full frame */
    }
}

/* ---------- INA219 I2C adapters (user_ctx is the bus token) ---------- */
static bool ina_read(void* user_ctx, uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
    return board_i2c_bus_read_reg((board_i2c_bus_t)user_ctx, addr, reg, buf, len);
}
static bool ina_write(void* user_ctx, uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
    return board_i2c_bus_write_reg((board_i2c_bus_t)user_ctx, addr, reg, buf, len);
}

/* ---------- Periodic streaming ---------- */

/* 6-byte payload (little-endian):
   [0..1]  u16 bus_mV
   [2..5]  i32 current_uA
*/
static void ps_fill_sensor_payload(uint8_t* dst, size_t len) {
    if (len < 6u) {
        (void)memset(dst, 0, len);
        return;
    }

    uint16_t bus_mV = 0u;
    int32_t current_uA = 0;

    /* Read BUS voltage and CURRENT (depends on CALIBRATION & mode) */
    if (INA219_ReadBusVoltage_mV(&g_ina, &bus_mV) != INA219_OK) {
        bus_mV = 0u;
    }
    if (INA219_ReadCurrent_uA(&g_ina, &current_uA) != INA219_OK) {
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

/* ---------- App lifecycle ---------- */

void ps_app_init(void) {
    rb_init(&txring, tx_mem, PS_TX_RING_CAP);
    rb_init(&rxring, rx_mem, PS_RX_RING_CAP);

    comm_usb_cdc_init();
    comm_usb_cdc_set_rx_handler(on_usb_rx);

    s_seq = 0;

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
            s_sensor_ready = 1u;
        } else {
            s_sensor_ready = 0u;
            s_streaming = 0u; /* gate: disable streaming on failure */
        }
    }
}

void ps_app_tick(void) {
    static uint32_t last_gen = 0;
    uint32_t now = board_millis();

    if (s_streaming && (uint32_t)(now - last_gen) >= PS_STREAM_PERIOD_MS) {
        last_gen = now;

        uint8_t payload[PS_STREAM_PAYLOAD_LEN];
        ps_fill_sensor_payload(payload, sizeof payload);
        ps_send_frame(payload, sizeof payload);
    }

    tx_pump();

    // Handle incoming host commands
    ps_parse_commands();
}
