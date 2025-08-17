/**
 * @file    comm_usb_cdc.h
 * @brief   Public API for USB CDC transport: init, TX, and RX handler registration.
 */

#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Callback signature for received USB CDC data.
 *
 * @param data Pointer to received bytes
 * @param len  Number of bytes received
 */
typedef void (*comm_rx_handler_t)(const uint8_t* data, uint32_t len);

/**
 * Initialize the comm layer and hook into the USB CDC receive path.
 * Call this once after the USB device is initialized.
 */
void comm_usb_cdc_init(void);

/**
 * Write bytes over USB CDC.
 *
 * @param buf Pointer to data
 * @param len Number of bytes to send
 * @return Number of bytes sent on success, -1 on busy/error
 */
int comm_usb_cdc_write(const void* buf, uint16_t len);

/**
 * Register or unregister the upper-layer receive handler.
 * Pass NULL to unregister.
 *
 * @param cb Callback to invoke on received data, or NULL
 */
void comm_usb_cdc_set_rx_handler(comm_rx_handler_t cb);


/* ------- link gating + pump API ------- */


/** Forward-declaration of ring type. */
struct rb_t;

/**
 * @brief  Returns true when USB is configured, DTR is asserted, and a TX slot is free.
 */
bool comm_usb_cdc_link_ready(void);

/**
 * @brief  Drain bytes from a TX ring into USB when the link is ready.
 *         Call this from the main loop.
 *
 * @param txring Pointer to an rb_t (SPSC byte ring)
 */
void comm_usb_cdc_pump(struct rb_t* txring);

/** Hook called from CDC TX-complete IRQ (wired in usbd_cdc_if.c). */
void comm_usb_cdc_on_tx_complete(void);

/** Hook called from CDC SET_CONTROL_LINE_STATE (DTR change) (wired in usbd_cdc_if.c). */
void comm_usb_cdc_on_dtr_change(bool asserted);

#ifdef __cplusplus
}
#endif
