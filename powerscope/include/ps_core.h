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

#include <ps_buffer_if.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ps_cmd_dispatcher.h"

#ifdef __cplusplus
extern "C" {
#endif

struct ps_cmd_dispatcher_t;
struct ps_sensor_adapter_t;
struct ps_transport_adapter_t;
struct ps_tx_ctx_t;

/**
 * @brief Streaming core state machine states.
 * Used internally by ps_core_tick() to track streaming progress.
 */
typedef enum {
    CORE_SM_IDLE = 0,     /**< Not streaming or waiting period */
    CORE_SM_SENSOR_START, /**< Sensor start requested */
    CORE_SM_SENSOR_POLL,  /**< Polling sensor */
    CORE_SM_READY,        /**< Sensor ready, payload available */
    CORE_SM_ERROR         /**< Sensor or transport error */
} ps_core_sm_t;

/**
 * @brief Generic sensor return codes
 */
typedef enum {
    CORE_SENSOR_ERROR = -1, /**< Sensor read failed */
    CORE_SENSOR_BUSY = 0,   /**< Sampling in progress */
    CORE_SENSOR_READY = 1   /**< Sample ready */
} ps_core_sensor_ret_t;

/**
 * @brief TX subsystem.
 */
typedef struct {
    ps_buffer_if_t* iface;   /**< TX buffer interface */
    struct ps_tx_ctx_t* ctx; /**< TX context for sending frames */
} ps_core_tx_t;

/**
 * @brief RX subsystem.
 */
typedef struct {
    ps_buffer_if_t* iface; /**< RX buffer interface */
} ps_core_rx_t;

/**
 * @brief Streaming subsystem.
 */
typedef struct {
    struct ps_sensor_adapter_t* sensor; /**< Sensor adapter */
    uint16_t max_payload;               /**< Maximum payload size */
    uint8_t streaming;                  /**< 1 = streaming enabled, 0 = disabled */
    uint16_t default_period_ms;         /**< Initial/default period set at init */
    uint16_t period_ms;                 /**< Active period for streaming frames. */
    uint32_t last_emit_ms;              /**< Timestamp of last emitted frame */
} ps_core_stream_t;

/**
 * @brief Runtime context for the streaming core.
 *
 * All fields are owned by the caller; the core never allocates memory.
 * Populate the function pointers before calling ::ps_core_init().
 */
typedef struct ps_core {
    /* ---------- Subsystems ---------- */
    ps_core_tx_t tx;
    ps_core_rx_t rx;
    ps_core_stream_t stream;

    /* ---------- Configuration ---------- */
    uint8_t sensor_ready; /**< 1 = sensor initialized, 0 = not ready. */
    uint32_t seq;         /**< Outgoing STREAM frame sequence counter */

    /* ---------- Dependencies (injected by application) ---------- */
    uint32_t (*now_ms)(void); /**< Return milliseconds since boot (monotonic) */

    /* ---------- Streaming state machine ---------- */
    ps_core_sm_t sm;

    /* Command dispatcher */
    struct ps_cmd_dispatcher_t* dispatcher;

    struct ps_transport_adapter_t* transport;

    /* Debug LED hooks (hardware-agnostic) */
    void (*led_on)(void);
    void (*led_off)(void);
    void (*led_toggle)(void);
} ps_core_t;

/**
 * @brief Initialize the streaming core.
 *
 * Initializes both TX and RX rings and resets runtime state.
 *
 * @param c       Pointer to the core context (must be non-NULL).
 */
void ps_core_init(ps_core_t* c);

/**
 * @brief Attach TX and RX buffers to the core context.
 *
 * @param c       Pointer to the core context (must be non-NULL).
 * @param tx      Pointer to the TX buffer interface (must be non-NULL).
 * @param rx      Pointer to the RX buffer interface (must be non-NULL).
 */
void ps_core_attach_buffers(ps_core_t* c, ps_buffer_if_t* tx, ps_buffer_if_t* rx);

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
