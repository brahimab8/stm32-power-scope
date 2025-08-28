/**
 * @file    ring_buffer.h
 * @brief   SPSC byte ring buffer (power-of-two capacity). 
 *          Policy-free reads + two atomic write modes.
 *
 * Single-producer / single-consumer:
 * Notes:
 *  - Capacity MUST be a power of two (e.g., 1024, 8192). One slot is reserved.
 *  - Indices are 16-bit; wrap is modulo capacity.
 *
 * Write modes (all-or-nothing):
 *   rb_write_overwrite() → make room by dropping oldest, then write all len bytes.
 *                          Fails only if len > (cap-1).
 *   rb_write_try()       → write only if free >= len; otherwise write nothing.
 *                          Fails if len > (cap-1) or not enough space.
 */

#pragma once
#include <stdint.h>
#include <string.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct rb_t {
    uint8_t* buf;                /**< Backing byte buffer (capacity bytes). */
    uint16_t cap;                /**< Capacity (power of two). One slot is reserved. */
    volatile uint16_t head;      /**< Producer-owned write index. */
    volatile uint16_t tail;      /**< Consumer-owned read index. */
    volatile uint32_t dropped;   /**< Bytes discarded from the tail (overwrite mode). */
    volatile uint32_t rejected;  /**< Bytes refused (try/no-overwrite mode). */
    volatile uint16_t highwater; /**< Max 'used' ever observed. */
} rb_t;

/* --- core --- */
/**
 * @brief   Initialize a ring buffer over user-provided storage.
 *
 * @param r         Ring buffer object
 * @param mem       Pointer to backing storage (uint8_t array; >= cap_pow2 bytes).
 * @param cap_pow2  Capacity; must be non-zero power of two.
 *
 * Caller guarantees:
 *  - r and mem are non-NULL
 *  - cap_pow2 is a non-zero power of two (usable capacity is cap_pow2 - 1)
 */
static inline void rb_init(rb_t* r, uint8_t* mem, uint16_t cap_pow2) {
    r->buf = mem;
    r->cap = cap_pow2;
    r->head = r->tail = 0;
    r->dropped = 0;
    r->rejected = 0;
    r->highwater = 0;
}

/**
 * @brief   Clear the ring (drops all pending data, keeps metrics).
 * @param r Ring buffer
 */
static inline void rb_clear(rb_t* r) {
    r->tail = r->head;
}

/**
 * @brief   Return the capacity in bytes (power of two; one slot reserved; usable = cap−1).
 * @param r Ring buffer
 */
static inline uint16_t rb_capacity(const rb_t* r) {
    return r->cap;
}

/**
 * @brief   Bytes currently stored (available to read).
 * @param r Ring buffer
 */
static inline uint16_t rb_used(const rb_t* r) {
    return (uint16_t)((r->head - r->tail) & (r->cap - 1));
}

/**
 * @brief   Free space in bytes (that can be written without overwrite).
 * @param r Ring buffer
 */
static inline uint16_t rb_free(const rb_t* r) {
    return (uint16_t)(r->cap - 1 - rb_used(r));
}

/**
 * @brief   Total bytes dropped (overwrite mode).
 * @param r Ring buffer
 */
static inline uint32_t rb_drop_count(const rb_t* r) {
    return r->dropped;
}

/**
 * @brief   Total bytes that were rejected (try/no-overwrite mode)..
 * @param r Ring buffer
 */

static inline uint32_t rb_reject_count(const rb_t* r) { 
    return r->rejected; 
}

/**
 * @brief   Highest 'used' watermark seen since init.
 * @param r Ring buffer
 */
static inline uint16_t rb_highwater(const rb_t* r) {
    return r->highwater;
}

/* --- read side --- */

/**
 * @brief Peek a contiguous region at the tail without popping.
 * @param r   Ring buffer.
 * @param ptr Out pointer to the start of the contiguous region (or NULL if empty).
 * @return Number of contiguous bytes available at @p ptr.
 */
static inline uint16_t rb_peek_linear(const rb_t* r, const uint8_t** ptr) {
    uint16_t used = rb_used(r);
    if (!used) {
        if (ptr) *ptr = NULL; 
        return 0; 
    }

    uint16_t mask   = (uint16_t)(r->cap - 1);
    uint16_t linear = (uint16_t)(r->cap - (r->tail & mask));
    if (linear > used) linear = used;
    if (ptr) *ptr = &r->buf[r->tail & mask];
    return linear;
}

/**
 * @brief Pop bytes from the tail.
 * @param r Ring buffer.
 * @param n Number of bytes to remove (caller guarantees n ≤ used).
 */
static inline void rb_pop(rb_t* r, uint16_t n) { 
    r->tail = (uint16_t)(r->tail + n); 
}

/**
 * @brief Copy up to @p n bytes from the tail without popping.
 * @param r   Ring buffer (read side).
 * @param dst Destination buffer (may be NULL; then 0 is returned).
 * @param n   Requested bytes to copy.
 * @return Bytes actually copied (<= @p n).
 *
 * Clamps to available data (rb_used) and handles wraparound.
 * Non-destructive: does not advance @p tail.
 */
static inline uint16_t rb_copy_from_tail(const rb_t* r, void* dst, uint16_t n) {
    if (!dst) return 0;
    uint16_t used = rb_used(r);
    if (n > used) n = used;
    if (!n) return 0;

    uint16_t mask   = (uint16_t)(r->cap - 1);
    uint16_t t      = r->tail;
    uint16_t linear = (uint16_t)(r->cap - (t & mask));
    uint16_t first  = (n < linear) ? n : linear;

    memcpy(dst, &r->buf[t & mask], first);
    if (first < n) {
        memcpy((uint8_t*)dst + first, &r->buf[0], (size_t)(n - first));
    }
    return n;
}

/* --- write side (choose policy per call) --- */

/**
 * @brief Write with overwrite policy (drops oldest if needed).
 * @param r   Ring buffer.
 * @param src Source bytes.
 * @param len Bytes to write.
 * @return Bytes written (always @p len).
 *
 * Increments r->dropped by the number of bytes discarded to make room.
 * Fails if len > (cap-1).
 */
static inline uint16_t rb_write_overwrite(rb_t* r, const uint8_t* src, uint16_t len) {
    if (!len) return 0;
    const uint16_t usable = (uint16_t)(r->cap - 1);
    if (len > usable) { r->rejected += len; return 0; }

    uint16_t free = rb_free(r);
    if (len > free) {
        uint16_t drop = (uint16_t)(len - free);
        r->tail = (uint16_t)(r->tail + drop); /* overwrite-oldest */
        r->dropped += drop;
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

/**
 * @brief Write without overwrite (reject if not enough space).
 * @param r   Ring buffer.
 * @param src Source bytes.
 * @param len Requested bytes to write.
 * @return Bytes actually written (either @p len on success, or 0 on rejection).
 *
 * Notes:
 *  - Usable capacity is (cap - 1). If @p len > (cap - 1), the write is rejected.
 *  - If current free space < @p len, the write is rejected.
 *  - On rejection, r->rejected is incremented by @p len.
 *  - On success, data is copied (handling wrap) and head is advanced.
 */
static inline uint16_t rb_write_try(rb_t* r, const uint8_t* src, uint16_t len) {
    if (!len) return 0;
    const uint16_t usable = (uint16_t)(r->cap - 1);
    if (len > usable) { r->rejected += len; return 0; }

    uint16_t free = rb_free(r);
    if (free < len) { r->rejected += len; return 0; }

    uint16_t mask  = (uint16_t)(r->cap - 1);
    uint16_t h     = r->head;
    uint16_t first = (uint16_t)((len < (r->cap - (h & mask))) ? len : (r->cap - (h & mask)));
    memcpy(&r->buf[h & mask], src, first);
    memcpy(&r->buf[0], src + first, (size_t)len - first);
    r->head = (uint16_t)(h + len);

    uint16_t u = rb_used(r);
    if (u > r->highwater) r->highwater = u;
    return len;
}

#ifdef __cplusplus
}
#endif
