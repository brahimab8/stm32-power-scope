/**
 * @file    ring_buffer.c
 * @brief   SPSC byte ring buffer (power-of-two capacity).
 */

#include <ring_buffer.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

void rb_init(rb_t* r, uint8_t* mem, uint16_t cap_pow2) {
    r->buf = mem;
    r->cap = cap_pow2;
    r->head = r->tail = 0;
    r->rejected = 0;
    r->highwater = 0;
}

void rb_clear(rb_t* r) {
    r->tail = r->head;
}

uint16_t rb_capacity(const rb_t* r) {
    return r->cap;
}

uint16_t rb_used(const rb_t* r) {
    return (uint16_t)((r->head - r->tail) & (r->cap - 1));
}

uint16_t rb_free(const rb_t* r) {
    return (uint16_t)(r->cap - 1 - rb_used(r));
}

uint32_t rb_reject_count(const rb_t* r) {
    return r->rejected;
}

uint16_t rb_highwater(const rb_t* r) {
    return r->highwater;
}

/* --- read side --- */

uint16_t rb_peek_linear(const rb_t* r, const uint8_t** ptr) {
    uint16_t used = rb_used(r);
    if (!used) {
        if (ptr) *ptr = NULL;
        return 0;
    }

    uint16_t mask = (uint16_t)(r->cap - 1);
    uint16_t linear = (uint16_t)(r->cap - (r->tail & mask));
    if (linear > used) linear = used;
    if (ptr) *ptr = &r->buf[r->tail & mask];
    return linear;
}

void rb_pop(rb_t* r, uint16_t n) {
    r->tail = (uint16_t)(r->tail + n);
}

uint16_t rb_copy_from_tail(const rb_t* r, void* dst, uint16_t n) {
    if (!dst) return 0;
    uint16_t used = rb_used(r);
    if (n > used) n = used;
    if (!n) return 0;

    uint16_t mask = (uint16_t)(r->cap - 1);
    uint16_t t = r->tail;
    uint16_t linear = (uint16_t)(r->cap - (t & mask));
    uint16_t first = (n < linear) ? n : linear;

    memcpy(dst, &r->buf[t & mask], first);
    if (first < n) {
        memcpy((uint8_t*)dst + first, &r->buf[0], (size_t)(n - first));
    }
    return n;
}

uint16_t rb_write_try(rb_t* r, const uint8_t* src, uint16_t len) {
    if (!len) return 0;
    const uint16_t usable = (uint16_t)(r->cap - 1);
    if (len > usable) {
        r->rejected += len;
        return 0;
    }

    uint16_t free = rb_free(r);
    if (free < len) {
        r->rejected += len;
        return 0;
    }

    uint16_t mask = (uint16_t)(r->cap - 1);
    uint16_t h = r->head;
    uint16_t first = (uint16_t)((len < (r->cap - (h & mask))) ? len : (r->cap - (h & mask)));
    memcpy(&r->buf[h & mask], src, first);
    memcpy(&r->buf[0], src + first, (size_t)len - first);
    r->head = (uint16_t)(h + len);

    uint16_t u = rb_used(r);
    if (u > r->highwater) r->highwater = u;
    return len;
}
