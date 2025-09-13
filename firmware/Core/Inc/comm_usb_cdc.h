/**
 * @file    comm_usb_cdc.h
 * @brief   USB CDC transport: init, RX handler registration, link state, and staged try-write.
 *
 * Note:
 *  - A single TX is in flight at a time;
 *  - Writes must be ≤ comm_usb_cdc_best_chunk().
 */

#pragma once
#include <stdbool.h>
#include <stdint.h>

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
 * Register or unregister the upper-layer receive handler.
 * Pass NULL to unregister.
 *
 * @param cb Callback to invoke on received data, or NULL
 */
void comm_usb_cdc_set_rx_handler(comm_rx_handler_t cb);

/**
 * @brief  Returns true when USB is configured, DTR is asserted, and previous TX completed.
 */
bool comm_usb_cdc_link_ready(void);

/**
 * @brief  Max safe single write size (bytes). Caller must not exceed this in try_write().
 *         Typical FS-CDC is 64.
 */
uint16_t comm_usb_cdc_best_chunk(void);

/**
 * @brief Try to write exactly @p len bytes (≤ best_chunk). Non-blocking.
 *
 * @param buf Pointer to data
 * @param len Number of bytes to send
 * @return len on success; 0 if busy/not ready; -1 on invalid args or len>best_chunk.
 */
int comm_usb_cdc_try_write(const void* buf, uint16_t len);

/** Hook called from CDC TX-complete IRQ (wired in usbd_cdc_if.c). */
void comm_usb_cdc_on_tx_complete(void);

/** Hook called from CDC SET_CONTROL_LINE_STATE (DTR change) (wired in usbd_cdc_if.c). */
void comm_usb_cdc_on_dtr_change(bool asserted);

#ifdef __cplusplus
}
#endif
