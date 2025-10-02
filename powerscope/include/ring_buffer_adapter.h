/**
 * @file   ring_buffer_adapter.h
 * @brief  Adapter: ps_buffer_if_t over rb_t ring buffer.
 */

#ifndef RING_BUFFER_ADAPTER_H
#define RING_BUFFER_ADAPTER_H

#include <stdbool.h>
#include <stdint.h>

#include "ps_buffer_if.h"
#include "ring_buffer.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    rb_t rb; /**< Internal ring buffer */
} ps_ring_buffer_t;

/**
 * @brief Initialize a ring-buffer-backed ps_buffer_if.
 *
 * @param buf      Pointer to the ps_ring_buffer_t object.
 * @param mem      Backing storage (uint8_t array).
 * @param cap_pow2 Capacity (power of two).
 * @param iface    Output vtable (ps_buffer_if_t) to wire into ps_core.
 */
void ps_ring_buffer_init(ps_ring_buffer_t* buf, uint8_t* mem, uint16_t cap_pow2,
                         ps_buffer_if_t* iface);

#ifdef __cplusplus
}
#endif

#endif /* RING_BUFFER_ADAPTER_H */
