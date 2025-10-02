/**
 * @file   ring_buffer_adapter.c
 * @brief  Adapter: ps_buffer_if_t over rb_t ring buffer.
 */

#include "ring_buffer_adapter.h"

#include <string.h>

/* --- Adapter functions --- */

static bool append_adapter(void* ctx, const uint8_t* src, uint16_t len) {
    return rb_write_try(&((ps_ring_buffer_t*)ctx)->rb, src, len) == len;
}

static uint16_t size_adapter(void* ctx) {
    return rb_used(&((ps_ring_buffer_t*)ctx)->rb);
}

static uint16_t space_adapter(void* ctx) {
    return rb_free(&((ps_ring_buffer_t*)ctx)->rb);
}

static uint16_t capacity_adapter(void* ctx) {
    return rb_capacity(&((ps_ring_buffer_t*)ctx)->rb);
}

static void clear_adapter(void* ctx) {
    rb_clear(&((ps_ring_buffer_t*)ctx)->rb);
}

static void pop_adapter(void* ctx, uint16_t n) {
    rb_pop(&((ps_ring_buffer_t*)ctx)->rb, n);
}

static void copy_adapter(void* ctx, void* dst, uint16_t len) {
    rb_copy_from_tail(&((ps_ring_buffer_t*)ctx)->rb, dst, len);
}

static uint16_t peek_contiguous_adapter(void* ctx, const uint8_t** out) {
    return rb_peek_linear(&((ps_ring_buffer_t*)ctx)->rb, out);
}

/* --- Public initializer --- */

void ps_ring_buffer_init(ps_ring_buffer_t* buf, uint8_t* mem, uint16_t cap_pow2,
                         ps_buffer_if_t* iface) {
    if (!buf || !mem || !iface) return;

    rb_init(&buf->rb, mem, cap_pow2);

    iface->ctx = buf;
    iface->append = append_adapter;
    iface->size = size_adapter;
    iface->space = space_adapter;
    iface->capacity = capacity_adapter;
    iface->clear = clear_adapter;
    iface->pop = pop_adapter;
    iface->copy = copy_adapter;
    iface->peek_contiguous = peek_contiguous_adapter;
}
