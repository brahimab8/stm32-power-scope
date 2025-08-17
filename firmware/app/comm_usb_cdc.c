/**
 * @file    comm_usb_cdc.c
 * @brief   USB CDC transport adapter: init, TX wrapper, and RX handler dispatch.
 *
 * Provides a thin abstraction layer between the USB CDC driver and the
 * application. Upper layers can register a callback to receive raw CDC bytes,
 * and can send data via comm_usb_cdc_write().
 */

#include "app/comm_usb_cdc.h"

#include <stdint.h>
#include <string.h>  // memcpy

#include "app/ring_buffer.h"  // rb_t + rb_peek_linear + rb_pop
#include "usbd_cdc_if.h"      // CDC_Transmit_FS + USBD_CDC_SetRxCallback
#include "usbd_def.h"         // USBD_STATE_CONFIGURED

// Declared in usbd_cdc_if.c
extern USBD_HandleTypeDef hUsbDeviceFS;

// Registered receive callback (NULL if none). Volatile for ISR/main access.
static volatile comm_rx_handler_t s_rx = 0;

// Link state + staging
static volatile uint8_t s_tx_ready = 1;
static volatile uint8_t s_dtr = 0;

#define COMM_USB_CDC_BEST_CHUNK 512u
static uint8_t s_stage[COMM_USB_CDC_BEST_CHUNK];

// Forward declaration of the private RX dispatcher
static void comm_usb_cdc_on_rx_bytes(const uint8_t* data, uint32_t len);

void comm_usb_cdc_init(void) {
    s_rx = 0;                                          // reset callback
    USBD_CDC_SetRxCallback(comm_usb_cdc_on_rx_bytes);  // hook RX path
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

/* ---------------- Link gating + pump API ---------------- */

bool comm_usb_cdc_link_ready(void) {
    return (hUsbDeviceFS.dev_state == USBD_STATE_CONFIGURED) && (s_dtr != 0) && (s_tx_ready != 0);
}

void comm_usb_cdc_pump(struct rb_t* txring) {
    if (!comm_usb_cdc_link_ready()) return;

    const uint8_t* p = NULL;
    uint16_t avail = rb_peek_linear(txring, &p);
    if (!avail) return;

    uint16_t n = (avail > COMM_USB_CDC_BEST_CHUNK) ? COMM_USB_CDC_BEST_CHUNK : avail;
    memcpy(s_stage, p, n);

    if (comm_usb_cdc_write(s_stage, n) == (int)n) {
        s_tx_ready = 0;  // wait for TX-complete IRQ to set this back to 1
        rb_pop(txring, n);
    }
}

/* Hooks called from usbd_cdc_if.c */
void comm_usb_cdc_on_tx_complete(void) {
    s_tx_ready = 1;
}
void comm_usb_cdc_on_dtr_change(bool asserted) {
    s_dtr = asserted ? 1u : 0u;
}
