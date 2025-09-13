/**
 * @file    ps_core.h
 * @brief   Streaming core – transport- and sensor-agnostic logic.
 *
 * This module owns the TX/RX ring buffers, frames payloads according
 * to the binary protocol, pumps the transport, and parses incoming
 * START/STOP commands.  It contains no direct hardware or HAL calls.
 */

#ifndef PS_CORE_H
#define PS_CORE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "app/ring_buffer.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Runtime context for the streaming core.
 *
 * All fields are owned by the caller; the core never allocates memory.
 * Populate the function pointers before calling ::ps_core_init().
 */
typedef struct {
    /* ---------- Ring buffers ---------- */
    rb_t tx; /**< TX ring (frames queued for transport) */
    rb_t rx; /**< RX ring (bytes received from transport) */

    /* ---------- Configuration ---------- */
    uint16_t stream_period_ms; /**< Period between STREAM frames. */
    uint16_t max_payload;      /**< Maximum payload size (bytes). */

    /* ---------- Runtime state ---------- */
    uint8_t streaming;     /**< 1 = streaming enabled, 0 = disabled. */
    uint8_t sensor_ready;  /**< 1 = sensor initialized, 0 = not ready. */
    uint32_t seq;          /**< Outgoing STREAM frame sequence counter. */
    uint32_t last_emit_ms; /**< Timestamp of last emitted frame. */

    /* ---------- Dependencies (injected by application) ---------- */

    /** Return milliseconds since boot (monotonic). */
    uint32_t (*now_ms)(void);

    /** Transport link status: true if ready to write. */
    bool (*link_ready)(void);

    /** Maximum safe write size (bytes) for ::tx_write(). */
    uint16_t (*best_chunk)(void);

    /**
     * @brief Attempt to write exactly @p len bytes to the transport.
     * @return len on success, 0 if busy/not ready, -1 on error.
     */
    int (*tx_write)(const uint8_t* buf, uint16_t len);

    /** Sensor adapter: read bus voltage (mV). Return true on success. */
    bool (*sensor_read_bus_mV)(uint16_t* out);

    /** Sensor adapter: read current (µA). Return true on success. */
    bool (*sensor_read_current_uA)(int32_t* out);
} ps_core_t;

/**
 * @brief Initialize the streaming core.
 *
 * Initializes both TX and RX rings and resets runtime state.
 *
 * @param c       Pointer to the core context (must be non-NULL).
 * @param tx_mem  Backing storage for TX ring.
 * @param tx_cap  Capacity of TX ring (bytes).
 * @param rx_mem  Backing storage for RX ring.
 * @param rx_cap  Capacity of RX ring (bytes).
 */
void ps_core_init(ps_core_t* c, uint8_t* tx_mem, uint16_t tx_cap, uint8_t* rx_mem, uint16_t rx_cap);

/**
 * @brief RX ISR hook: enqueue raw bytes received from the transport.
 *
 * Uses a no-overwrite policy: if the RX ring is full, the newest bytes
 * are dropped.
 *
 * @param c   Core context.
 * @param d   Pointer to received data.
 * @param n   Number of bytes received.
 */
void ps_core_on_rx(ps_core_t* c, const uint8_t* d, uint32_t n);

/**
 * @brief Periodic main-loop work.
 *
 * - Generates a new STREAM frame at the configured period if
 *   streaming is enabled.
 * - Pumps the transport: attempts to transmit queued frames.
 * - Parses incoming CMD frames and updates the `streaming` flag.
 *
 * @param c Core context.
 */
void ps_core_tick(ps_core_t* c);

#ifdef __cplusplus
}
#endif

#endif /* PS_CORE_H */
