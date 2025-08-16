/**
 * @file    comm_usb_cdc.h
 * @brief   Public API for USB CDC transport: init, TX, and RX handler registration.
 */

 #pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @file    comm_usb_cdc.h
 * @brief   USB CDC transport API: init, TX, and RX handler registration.
 */

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

#ifdef __cplusplus
}
#endif
