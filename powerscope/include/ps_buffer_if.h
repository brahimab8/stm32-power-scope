/**
 * @file    ps_buffer_if.h
 * @brief   Generic byte-buffer abstraction (for TX/RX queues).
 *
 * Notes:
 *  - Data is appended at the "new" end.
 *  - Data is consumed (popped) from the "old" end.
 */

#ifndef PS_BUFFER_IF_H
#define PS_BUFFER_IF_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Generic buffer interface.
 *
 * Implementations may be backed by a ring buffer, a linear FIFO,
 * or a test double.  The @ref ctx pointer holds the implementation-
 * specific state (e.g. a `rb_t*`).
 */
typedef struct {
    void* ctx; /**< Implementation-specific context (must be set). */

    /** @return number of bytes currently stored. */
    uint16_t (*size)(void* ctx);

    /** @return number of free bytes available for appending. */
    uint16_t (*space)(void* ctx);

    /** @return total buffer capacity in bytes. */
    uint16_t (*capacity)(void* ctx);

    /** Clear the buffer to empty state. */
    void (*clear)(void* ctx);

    /**
     * @brief Append bytes to the buffer.
     * @param ctx Implementation context.
     * @param src Source buffer.
     * @param len Number of bytes to append.
     * @return true if all bytes were written, false otherwise.
     */
    bool (*append)(void* ctx, const uint8_t* src, uint16_t len);

    /**
     * @brief Remove (consume) bytes from the buffer.
     * @param ctx Implementation context.
     * @param len Number of bytes to remove (may be clamped internally).
     */
    void (*pop)(void* ctx, uint16_t len);

    /**
     * @brief Copy bytes from the buffer without removing them.
     * @param ctx Implementation context.
     * @param dst Destination buffer.
     * @param len Number of bytes to copy (must not exceed size()).
     */
    void (*copy)(void* ctx, void* dst, uint16_t len);

    /**
     * @brief Provide a pointer to a contiguous region of oldest data.
     *
     * If the underlying storage is contiguous, this may return up to `size()`
     * bytes. If wrapping occurs (e.g. ring buffer), only the first contiguous
     * region is returned.
     *
     * @param ctx Implementation context.
     * @param out On success, set to pointer to contiguous region.
     * @return number of contiguous bytes available at *out.
     */
    uint16_t (*peek_contiguous)(void* ctx, const uint8_t** out);
} ps_buffer_if_t;

#ifdef __cplusplus
}
#endif

#endif /* PS_BUFFER_IF_H */