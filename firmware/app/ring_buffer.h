/**
 * @file    ring_buffer.h
 * @brief   SPSC byte ring buffer (power-of-two capacity), overwrite-oldest policy.
 *
 * Single-producer / single-consumer:
 *  - Producer calls rb_write()
 *  - Consumer calls rb_peek_linear() + rb_pop()
 *
 * Notes:
 *  - Capacity MUST be a power of two (e.g., 1024, 8192). One slot is reserved.
 *  - Head/tail are 16-bit: max capacity <= 65536 bytes.
 *
 */

#pragma once
#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Ring buffer handle.
 *
 * Allocate backing storage separately (uint8_t array). Initialize with rb_init().
 */
typedef struct rb_t {
    uint8_t* buf;            /**< Backing byte buffer (capacity bytes). */
    uint16_t cap;            /**< Capacity (power of two). One slot is reserved. */
    volatile uint16_t head;  /**< Producer-owned write index. */
    volatile uint16_t tail;  /**< Consumer-owned read index. */
    volatile uint32_t dropped;   /**< Total bytes overwritten to make room. */
    volatile uint16_t highwater; /**< Max 'used' ever observed. */
} rb_t;

/**
 * @brief   Initialize a ring buffer over user-provided storage.
 *
 * @param r         Ring buffer object
 * @param mem       Pointer to backing storage (uint8_t array)
 * @param cap_pow2  Capacity in bytes (MUST be a power of two; max 65536)
 */
static inline void rb_init(rb_t* r, uint8_t* mem, uint16_t cap_pow2)
{
    r->buf = mem;
    r->cap = cap_pow2;
    r->head = r->tail = 0;
    r->dropped = 0;
    r->highwater = 0;
}

/**
 * @brief   Clear the ring (drops all pending data, keeps metrics).
 * @param r Ring buffer
 */
static inline void rb_clear(rb_t* r)
{
    r->tail = r->head;
}

/**
 * @brief   Return the capacity in bytes (power of two; one slot reserved).
 * @param r Ring buffer
 */
static inline uint16_t rb_capacity(const rb_t* r)
{
    return r->cap;
}

/**
 * @brief   Bytes currently stored (available to read).
 * @param r Ring buffer
 */
static inline uint16_t rb_used(const rb_t* r)
{
    return (uint16_t)((r->head - r->tail) & (r->cap - 1));
}

/**
 * @brief   Free space in bytes (that can be written without overwrite).
 * @param r Ring buffer
 */
static inline uint16_t rb_free(const rb_t* r)
{
    return (uint16_t)(r->cap - 1 - rb_used(r));
}

/**
 * @brief   Total bytes that were overwritten to make room (monotonic).
 * @param r Ring buffer
 */
static inline uint32_t rb_drop_count(const rb_t* r)
{
    return r->dropped;
}

/**
 * @brief   Highest 'used' watermark seen since init.
 * @param r Ring buffer
 */
static inline uint16_t rb_highwater(const rb_t* r)
{
    return r->highwater;
}

/**
 * @brief   Write bytes, overwriting the oldest if needed (never fails).
 *
 * @param r     Ring buffer
 * @param src   Source bytes
 * @param len   Number of bytes to write
 * @return      len (always)
 */
static inline uint16_t rb_write(rb_t* r, const uint8_t* src, uint16_t len)
{
    uint16_t free = rb_free(r);
    if (len > free) {
        uint16_t drop = (uint16_t)(len - free);
        r->tail = (uint16_t)(r->tail + drop);   /* overwrite-oldest */
        r->dropped += drop;
    }

    uint16_t mask = (uint16_t)(r->cap - 1);
    uint16_t h = r->head;

    uint16_t first = (uint16_t)((len < (r->cap - (h & mask))) ? len
                                                              : (r->cap - (h & mask)));
    memcpy(&r->buf[h & mask], src, first);
    memcpy(&r->buf[0],       src + first, (size_t)len - first);

    r->head = (uint16_t)(h + len);

    uint16_t u = rb_used(r);
    if (u > r->highwater) r->highwater = u;

    return len;
}

/**
 * @brief   Peek a contiguous region from the tail without removing it.
 *
 * @param r     Ring buffer
 * @param ptr   Out: pointer to the first contiguous byte (NULL if empty)
 * @return      Number of contiguous bytes available at *ptr (0 if empty)
 *
 * @note        To consume data after a successful send/copy, call rb_pop(n).
 */
static inline uint16_t rb_peek_linear(const rb_t* r, const uint8_t** ptr)
{
    uint16_t used = rb_used(r);
    if (!used) { *ptr = 0; return 0; }

    uint16_t mask = (uint16_t)(r->cap - 1);
    uint16_t linear = (uint16_t)(r->cap - (r->tail & mask));
    if (linear > used) linear = used;

    *ptr = &r->buf[r->tail & mask];
    return linear;
}

/**
 * @brief   Pop (consume) n bytes from the tail. Caller guarantees n <= used.
 * @param r Ring buffer
 * @param n Number of bytes to drop
 */
static inline void rb_pop(rb_t* r, uint16_t n)
{
    r->tail = (uint16_t)(r->tail + n);
}

#ifdef __cplusplus
}
#endif
