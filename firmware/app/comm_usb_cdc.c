/**
 * @file    comm_usb_cdc.c
 * @brief   USB CDC transport adapter: init, TX wrapper, and RX handler dispatch.
 *
 * Provides a thin abstraction layer between the USB CDC driver and the
 * application. Upper layers can register a callback to receive raw CDC bytes,
 * and can send data via comm_usb_cdc_write().
 */

#include "app/comm_usb_cdc.h"
#include "usbd_cdc_if.h"   // CDC_Transmit_FS + USBD_CDC_SetRxCallback
#include <stdint.h>

// Registered receive callback (NULL if none). Volatile for ISR/main access.
static volatile comm_rx_handler_t s_rx = 0;

// Forward declaration of the private RX dispatcher
static void comm_usb_cdc_on_rx_bytes(const uint8_t* data, uint32_t len);

void comm_usb_cdc_init(void) {
    s_rx = 0;  // reset callback
    USBD_CDC_SetRxCallback(comm_usb_cdc_on_rx_bytes); // hook RX path
}

int comm_usb_cdc_write(const void* buf, uint16_t len) {
    if (!buf || len == 0) return 0;
    // CDC_Transmit_FS takes non-const; cast away const for driver
    return (CDC_Transmit_FS((uint8_t*)buf, len) == USBD_OK) ? (int)len : -1;
}

void comm_usb_cdc_set_rx_handler(comm_rx_handler_t cb) {
    s_rx = cb;  // register or unregister callback
}

static void comm_usb_cdc_on_rx_bytes(const uint8_t* data, uint32_t len) {
    comm_rx_handler_t cb = s_rx;  // snapshot to avoid race on volatile
    if (cb && data && len) {
        cb(data, len);  // forward raw bytes to upper layer
    }
}
