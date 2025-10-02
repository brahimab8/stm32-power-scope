/**
 * @file ps_sensor_adapter.h
 * @brief Generic sensor adapter.
 *
 */
#ifndef PS_SENSOR_ADAPTER_H
#define PS_SENSOR_ADAPTER_H

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Generic sensor adapter for streaming core.
 *
 * Wraps a sensor context and exposes function pointers for:
 *  - fill (serialize sample),
 *  - start (cooperative request),
 *  - poll  (complete request).
 */
typedef struct ps_sensor_adapter_t {
    void* ctx;
    size_t (*fill)(void* ctx, uint8_t* dst, size_t max_len);
    int (*start)(void* ctx);
    int (*poll)(void* ctx);
} ps_sensor_adapter_t;

#endif /* PS_SENSOR_ADAPTER_H */
