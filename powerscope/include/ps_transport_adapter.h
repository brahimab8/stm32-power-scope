/**
 * @file    ps_transport_adapter.h
 * @brief   Generic transport adapter interface.
 *
 * Provides a hardware-agnostic transport abstraction.
 * The physical layer (USB, UART, etc.) is wired in the application.
 */

#ifndef PS_TRANSPORT_H
#define PS_TRANSPORT_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** RX callback signature for incoming bytes from the physical layer. */
typedef void (*ps_transport_rx_cb_t)(const uint8_t* data, uint32_t len);

/**
 * @brief Transport adapter for ps_core.
 *
 * Implementations of this adapter provide tx, link check, best chunk, and
 * RX handler registration for the core.
 */
typedef struct ps_transport_adapter_t {
    /** Attempt to send exactly @p len bytes.
     * @return len on success, 0 if busy/not ready, -1 on error */
    int (*tx_write)(const uint8_t* buf, uint16_t len);

    /** Return true if link is ready for transmission. */
    bool (*link_ready)(void);

    /** Return maximum safe single write length. */
    uint16_t (*best_chunk)(void);

    /** Set RX callback to receive incoming bytes. Pass NULL to disable. */
    void (*set_rx_handler)(ps_transport_rx_cb_t cb);
} ps_transport_adapter_t;

#ifdef __cplusplus
}
#endif

#endif /* PS_TRANSPORT_H */
