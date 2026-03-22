/**
 * @file    comm_tcp.h
 * @brief   TCP transport interface for simulation firmware.
 */

#pragma once

#include <stdbool.h>
#include <stdint.h>

#include <ps_transport_adapter.h>

bool comm_tcp_init(uint16_t port);
void comm_tcp_set_rx_handler(ps_transport_rx_cb_t cb);
uint16_t comm_tcp_best_chunk(void);
bool comm_tcp_link_ready(void);
int comm_tcp_try_write(const uint8_t* buf, uint16_t len);
void comm_tcp_poll(void);
