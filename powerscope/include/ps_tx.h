/**
 * @file    ps_tx.h
 * @brief   TX framing + transmit policy (enqueue + pump).
 *
 * Minimal, transport-agnostic module that:
 *  - builds protocol frames (header + payload + CRC),
 *  - enqueues frames into a supplied ring buffer via ps_buffer_if_t,
 *  - keeps a simple "drop whole frames" policy to make room,
 *  - pumps data to transport using provided tx_write()/link_ready()/best_chunk().
 *
 * The module is intentionally independent of ps_core_t.
 */

#ifndef PS_TX_H
#define PS_TX_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "protocol_defs.h" /* proto types, sizes, proto_write_frame, proto_write_stream_frame */
#include "ps_buffer_if.h"  /* minimal buffer interface */

#ifdef __cplusplus
extern "C" {
#endif

/** Return codes for tx_write (mirror of transport): len on success, 0 busy, -1 error */
typedef int (*ps_tx_write_fn)(const uint8_t* buf, uint16_t len);
typedef bool (*ps_link_ready_fn)(void);
typedef uint16_t (*ps_best_chunk_fn)(void);

/**
 * @brief TX module runtime/context.
 *
 * This small struct holds the runtime pieces the module needs. The application
 * owns this structure and passes it to the module init function.
 */
typedef struct ps_tx_ctx_t {
    ps_buffer_if_t* tx_buf; /**< tx ring buffer interface (must be non-NULL) */

    ps_tx_write_fn tx_write;     /**< transport write function (non-blocking) */
    ps_link_ready_fn link_ready; /**< transport link status */
    ps_best_chunk_fn best_chunk; /**< max safe write size */

    uint32_t* seq_ptr;    /**< optional pointer to sequence counter (incremented by send_stream) */
    uint16_t max_payload; /**< optional payload cap (0 = no cap) */
} ps_tx_ctx_t;

/**
 * @brief INTERNAL helper: drop one whole frame from tx buffer.
 *
 * Returns 1 if a frame (or garbage byte) was dropped, 0 otherwise.
 * Normally used internally by ps_tx_enqueue_frame(). Can be called directly
 * for testing or advanced buffer management, but should be used with caution.
 */
int drop_one_frame_buf(ps_buffer_if_t* buf);

/**
 * @brief Initialize a tx context structure.
 *
 * The context struct is owned by the caller; this copies values into it.
 * None of the pointers may be NULL except seq_ptr and max_payload (0 allowed).
 *
 * @return true on success, false on invalid args.
 */
bool ps_tx_init(ps_tx_ctx_t* ctx, ps_buffer_if_t* tx_buf, ps_tx_write_fn tx_write,
                ps_link_ready_fn link_ready, ps_best_chunk_fn best_chunk, uint32_t* seq_ptr,
                uint16_t max_payload);

/**
 * @brief Enqueue an already-built protocol frame into the TX ring (non-blocking).
 *
 * The frame buffer is NOT copied by this call beyond the append into the ring. If there
 * isn't space, the module will drop whole older frames (policy) to try to make room.
 *
 * @param ctx Context
 * @param frame Pointer to frame bytes
 * @param len Length of frame (bytes)
 */
void ps_tx_enqueue_frame(ps_tx_ctx_t* ctx, const uint8_t* frame, uint16_t len);

/**
 * @brief Build and enqueue header-only frames (ACK/NACK).
 *
 * @param ctx Context
 * @param type PROTO_TYPE_ACK / PROTO_TYPE_NACK etc.
 * @param req_seq Sequence to echo (request seq)
 */
void ps_tx_send_hdr(ps_tx_ctx_t* ctx, uint8_t type, uint32_t req_seq, uint32_t ts);

/**
 * @brief Build and enqueue STREAM frame (increments seq if seq_ptr supplied).
 *
 * @param ctx Context
 * @param payload Pointer to payload
 * @param payload_len Payload length in bytes
 * @param ts Timestamp to embed in frame (board_millis)
 */
void ps_tx_send_stream(ps_tx_ctx_t* ctx, const uint8_t* payload, uint16_t payload_len, uint32_t ts);

/**
 * @brief Attempt to pump TX: send the next whole frame if link ready and fits best_chunk.
 *
 * Should be called periodically from the core main loop.
 *
 * @param ctx Context
 */
void ps_tx_pump(ps_tx_ctx_t* ctx);

#ifdef __cplusplus
}
#endif

#endif /* PS_TX_H */