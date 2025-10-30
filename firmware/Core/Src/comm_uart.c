/**
 * @file    comm_uart.c
 * @brief   UART transport: init, RX handler registration, link state, and queued TX.
 */
#include "comm_uart.h"
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

static UART_HandleTypeDef* s_huart = NULL;
static volatile ps_transport_rx_cb_t s_rx_cb = NULL;
static uint8_t s_rx_byte = 0;  // internal single-byte RX buffer

#define UART_TRANSPORT_MAX_CHUNK 64u
#define UART_RX_ASSEMBLY_BUF_SIZE 128   // must be >= max frame length
#define UART_TX_RING_SIZE 8             // number of TX frames to queue

/* ---- RX buffer ---- */
static uint8_t s_rx_assembly[UART_RX_ASSEMBLY_BUF_SIZE];
static size_t s_rx_assembly_len = 0;
static size_t s_rx_min_frame_len = 0; 

/* ---- TX queue ---- */
typedef struct {
    uint8_t buf[UART_TRANSPORT_MAX_CHUNK];
    uint16_t len;
} tx_item_t;

static tx_item_t s_tx_ring[UART_TX_RING_SIZE];
static volatile size_t s_tx_ring_head = 0;
static volatile size_t s_tx_ring_tail = 0;
static volatile bool s_tx_busy = false;

/* ---- Helpers ---- */
static bool tx_ring_empty(void) {
    return s_tx_ring_head == s_tx_ring_tail;
}

static bool tx_ring_full(void) {
    return ((s_tx_ring_head + 1) % UART_TX_RING_SIZE) == s_tx_ring_tail;
}

static void uart_transport_flush_rx(void) {
    if (s_rx_assembly_len == 0) return;

    if (s_rx_cb) {
        s_rx_cb(s_rx_assembly, s_rx_assembly_len);
    }
    s_rx_assembly_len = 0;
}

static void uart_transport_start_next_tx(void) {
    if (s_tx_busy) return;
    if (tx_ring_empty()) return;

    tx_item_t* item = &s_tx_ring[s_tx_ring_tail];
    s_tx_busy = true;
    if (HAL_UART_Transmit_IT(s_huart, item->buf, item->len) != HAL_OK) {
        s_tx_busy = false; // failed, try next time
    }
}

/* ---- Public API ---- */
void comm_uart_init(UART_HandleTypeDef* huart) {
    s_huart = huart;
    s_rx_cb = NULL;
    s_rx_assembly_len = 0;
    s_rx_min_frame_len = 0;
    s_tx_busy = false;
    s_tx_ring_head = s_tx_ring_tail = 0;

    if (s_huart) {
        HAL_UART_Receive_IT(s_huart, &s_rx_byte, 1); // enable RX interrupt
    }
}

void uart_transport_set_rx_handler(ps_transport_rx_cb_t cb) {
    s_rx_cb = cb;
}

uint16_t uart_transport_best_chunk(void) {
    return UART_TRANSPORT_MAX_CHUNK;
}

bool uart_transport_link_ready(void) {
    return (s_huart != NULL);
}

int uart_transport_tx_write(const uint8_t* buf, uint16_t len) {
    if (!s_huart || !buf || len == 0 || len > UART_TRANSPORT_MAX_CHUNK) return -1;

    // If busy, enqueue
    size_t next_head = (s_tx_ring_head + 1) % UART_TX_RING_SIZE;
    if (next_head == s_tx_ring_tail) {
        // Ring full
        return 0;
    }

    // Copy frame to ring
    memcpy(s_tx_ring[s_tx_ring_head].buf, buf, len);
    s_tx_ring[s_tx_ring_head].len = len;
    s_tx_ring_head = next_head;

    // If UART idle, start transmitting immediately
    uart_transport_start_next_tx();

    return len;
}

void uart_transport_set_min_frame_len(size_t min_len) {
    s_rx_min_frame_len = min_len;
}

/* ---- HAL Callbacks ---- */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart != s_huart) return;

    // accumulate in assembly buffer
    if (s_rx_assembly_len < UART_RX_ASSEMBLY_BUF_SIZE) {
        s_rx_assembly[s_rx_assembly_len++] = s_rx_byte;
    }

    // flush if enough bytes
    if (s_rx_min_frame_len > 0 && s_rx_assembly_len >= s_rx_min_frame_len) {
        uart_transport_flush_rx();
    }

    // re-enable next byte
    HAL_UART_Receive_IT(s_huart, &s_rx_byte, 1);
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart != s_huart) return;

    // Advance tail
    if (!tx_ring_empty()) {
        s_tx_ring_tail = (s_tx_ring_tail + 1) % UART_TX_RING_SIZE;
    }
    s_tx_busy = false;

    // Start next frame if pending
    uart_transport_start_next_tx();
}
