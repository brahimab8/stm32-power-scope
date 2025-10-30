/**
 * @file    comm_uart.h
 * @brief   UART transport: init, RX handler registration, link state, and staged try-write.
 *
 * Note:
 *  - Single TX in flight at a time.
 *  - Writes must be ≤ uart_transport_best_chunk().
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "ps_transport_adapter.h"
#include "stm32l4xx_hal.h"

/** Initialize the UART transport with a given UART handle */
void comm_uart_init(UART_HandleTypeDef* huart);

/** Transport adapter callbacks (used by ps_transport_adapter_t) */
int uart_transport_tx_write(const uint8_t* buf, uint16_t len);
bool uart_transport_link_ready(void);
uint16_t uart_transport_best_chunk(void);
void uart_transport_set_rx_handler(ps_transport_rx_cb_t cb);
void uart_transport_set_min_frame_len(size_t min_len);
