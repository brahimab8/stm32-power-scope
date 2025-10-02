/**
 * @file    ring_buffer.h
 * @brief   SPSC byte ring buffer (power-of-two capacity).
 *
 * Single-producer / single-consumer:
 * Notes:
 *  - Capacity MUST be a power of two (e.g., 1024, 8192). One slot is reserved.
 *  - Indices are 16-bit; wrap is modulo capacity.
 *
 * Write mode:
 *   rb_write_try()       → write only if free >= len; otherwise write nothing.
 *                          Fails if len > (cap-1) or not enough space.
 */

#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct rb_t {
    uint8_t* buf;                /**< Backing byte buffer (capacity bytes). */
    uint16_t cap;                /**< Capacity (power of two). One slot is reserved. */
    volatile uint16_t head;      /**< Producer-owned write index. */
    volatile uint16_t tail;      /**< Consumer-owned read index. */
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
void rb_init(rb_t* r, uint8_t* mem, uint16_t cap_pow2);

/**
 * @brief   Clear the ring (drops all pending data, keeps metrics).
 * @param r Ring buffer
 */
void rb_clear(rb_t* r);

/**
 * @brief   Return the capacity in bytes (power of two; one slot reserved; usable = cap−1).
 * @param r Ring buffer
 */
uint16_t rb_capacity(const rb_t* r);

/**
 * @brief   Bytes currently stored (available to read).
 * @param r Ring buffer
 */
uint16_t rb_used(const rb_t* r);

/**
 * @brief   Free space in bytes (that can be written without overwrite).
 * @param r Ring buffer
 */
uint16_t rb_free(const rb_t* r);

/**
 * @brief   Total bytes that were rejected (try/no-overwrite mode)..
 * @param r Ring buffer
 */
uint32_t rb_reject_count(const rb_t* r);

/**
 * @brief   Highest 'used' watermark seen since init.
 * @param r Ring buffer
 */
uint16_t rb_highwater(const rb_t* r);

/* --- read side --- */

/**
 * @brief Peek a contiguous region at the tail without popping.
 * @param r   Ring buffer.
 * @param ptr Out pointer to the start of the contiguous region (or NULL if empty).
 * @return Number of contiguous bytes available at @p ptr.
 */
uint16_t rb_peek_linear(const rb_t* r, const uint8_t** ptr);

/**
 * @brief Pop bytes from the tail.
 * @param r Ring buffer.
 * @param n Number of bytes to remove (caller guarantees n ≤ used).
 */
void rb_pop(rb_t* r, uint16_t n);

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
uint16_t rb_copy_from_tail(const rb_t* r, void* dst, uint16_t n);

/* --- write side --- */

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
uint16_t rb_write_try(rb_t* r, const uint8_t* src, uint16_t len);

#ifdef __cplusplus
}
#endif
