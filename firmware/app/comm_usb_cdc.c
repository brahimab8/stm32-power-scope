/**
 * @file    comm_usb_cdc.c
 * @brief   USB CDC transport: init, RX dispatcher, link state, and staged try-write.
 *
 * Notes:
 *  - try_write() copies into an internal staging buffer so caller's memory
 *    may be volatile/stack and is safe to reuse immediately.
 */

#include "app/comm_usb_cdc.h"

#include <string.h>  // memcpy

#include "usbd_cdc_if.h"      // CDC_Transmit_FS + USBD_CDC_SetRxCallback
#include "usbd_def.h"         // USBD_STATE_CONFIGURED

// Declared in usbd_cdc_if.c
extern USBD_HandleTypeDef hUsbDeviceFS;

// Registered receive callback (NULL if none). Volatile for ISR/main access.
static volatile comm_rx_handler_t s_rx = 0;

// Link state + staging
static volatile uint8_t s_tx_ready = 1;
static volatile uint8_t s_dtr = 0;

/* 
 * Best single write size for USB CDC.
 * FS CDC endpoint size is 64 bytes.
 * Can be larger (multiples of 64) if batching at a higher level.
 */
#ifndef COMM_USB_CDC_BEST_CHUNK
#define COMM_USB_CDC_BEST_CHUNK 64u
#endif

static uint8_t s_stage[COMM_USB_CDC_BEST_CHUNK];

/* RX dispatcher: called by driver */
static void comm_usb_cdc_on_rx_bytes(const uint8_t* data, uint32_t len) {
    comm_rx_handler_t cb = s_rx;
    if (cb && data && len) cb(data, len);
}

/* --------- API --------- */
void comm_usb_cdc_init(void) {
    s_rx = 0;
    s_tx_ready = 1;
    s_dtr = 0;
    USBD_CDC_SetRxCallback(comm_usb_cdc_on_rx_bytes);
}

void comm_usb_cdc_set_rx_handler(comm_rx_handler_t cb) {
    s_rx = cb;  // register or unregister callback
}

bool comm_usb_cdc_link_ready(void) {
    return (hUsbDeviceFS.dev_state == USBD_STATE_CONFIGURED) && (s_dtr != 0) && (s_tx_ready != 0);
}

uint16_t comm_usb_cdc_best_chunk(void) { 
    return COMM_USB_CDC_BEST_CHUNK; 
}

int comm_usb_cdc_try_write(const void* buf, uint16_t len) {
    if (!buf || !len) return -1;
    if (!comm_usb_cdc_link_ready()) return 0;                 /* busy/not ready */

    uint16_t maxw = comm_usb_cdc_best_chunk();
    if (len > maxw) return -1;                                /* caller must respect best_chunk */

    memcpy(s_stage, buf, len);
    if (CDC_Transmit_FS(s_stage, len) != USBD_OK) return 0;   /* busy */
    s_tx_ready = 0;
    return (int)len;
}

/* Hooks called from usbd_cdc_if.c */
void comm_usb_cdc_on_tx_complete(void) {
    s_tx_ready = 1;
}
void comm_usb_cdc_on_dtr_change(bool asserted) {
    s_dtr = asserted ? 1u : 0u;
}
