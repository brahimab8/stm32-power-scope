/**
 * @file    ps_sensor_mgr.h
 * @brief   Generic sensor manager – cooperative and cached sampling.
 *
 * Hardware-agnostic module implementing a ps_sensor_adapter_t interface
 * for streaming cores. Supports cooperative start/poll and deterministic
 * fill of last sample.
 */

#ifndef PS_SENSOR_MGR_H
#define PS_SENSOR_MGR_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ps_sensor_adapter.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Sampling result codes */
#define SENSOR_MGR_READY 1  /**< Sample is ready */
#define SENSOR_MGR_BUSY 0   /**< Sampling in progress */
#define SENSOR_MGR_ERROR -1 /**< Sampling failed */

/* diagnostic error codes */
typedef enum {
    SENSOR_MGR_ERR_NONE = 0,
    SENSOR_MGR_ERR_READ_FAIL = -1,
    SENSOR_MGR_ERR_INVALID_CTX = -2,
    SENSOR_MGR_ERR_NO_DRIVER = -3,
} sensor_mgr_err_t;

/**
 * @brief Hardware interface for a single sensor.
 */
typedef struct {
    void* hw_ctx;                                 /**< Sensor-specific context */
    bool (*read_sample)(void* hw_ctx, void* out); /**< Reads latest sample into buffer */
    size_t sample_size;                           /**< Size of the sample buffer in bytes */
} sensor_iface_t;

/**
 * @brief Opaque sensor manager context.
 *
 * Stores last sample, state, and error code.
 */
typedef struct {
    sensor_iface_t iface;                             /**< Hardware interface */
    uint8_t* last_sample;                             /**< Pointer to last sample buffer */
    size_t sample_len;                                /**< Length of sample buffer */
    int last_err;                                     /**< Last error code */
    uint32_t last_sample_ms;                          /**< Timestamp of last sample */
    uint32_t (*now_ms)(void);                         /**< Timestamp provider from app */
    enum { IDLE = 0, REQUESTED, READY, ERROR } state; /**< Cooperative state */
} sensor_mgr_ctx_t;

/**
 * @brief Initialize a sensor manager.
 *
 * @param ctx Sensor manager context (must be allocated by caller)
 * @param iface Hardware interface
 * @param buf Pre-allocated buffer for last sample (size iface.sample_size)
 * @param now_ms_fn Function pointer returning current time in ms
 * @return true on success, false if parameters invalid
 */
bool sensor_mgr_init(sensor_mgr_ctx_t* ctx, sensor_iface_t iface, uint8_t* buf,
                     uint32_t (*now_ms_fn)(void));

/**
 * @brief Deinitialize sensor manager.
 *
 * Frees internal resources if needed (none in this refactor).
 */
void sensor_mgr_deinit(sensor_mgr_ctx_t* ctx);

/**
 * @brief Blocking read of the sensor.
 *
 * Updates last_sample, last_err, and last_sample_ms.
 */
bool sensor_mgr_sample_blocking(sensor_mgr_ctx_t* ctx);

/**
 * @brief Cooperative start request.
 *
 * Marks sample as requested; read occurs in poll().
 */
int sensor_mgr_start(sensor_mgr_ctx_t* ctx);

/**
 * @brief Cooperative poll.
 *
 * Completes a start request by reading the sensor.
 */
int sensor_mgr_poll(sensor_mgr_ctx_t* ctx);

/**
 * @brief Fill a buffer with the last sample.
 *
 * Non-blocking: returns cached sample only.
 *
 * @return Number of bytes copied (0 if unavailable)
 */
size_t sensor_mgr_fill(sensor_mgr_ctx_t* ctx, uint8_t* dst, size_t max_len);

/**
 * @brief Returns last error code.
 */
int sensor_mgr_last_error(sensor_mgr_ctx_t* ctx);

/**
 * @brief Returns timestamp of last successful sample.
 */
uint32_t sensor_mgr_last_sample_ms(sensor_mgr_ctx_t* ctx);

/**
 * @brief Wraps a sensor_mgr_ctx_t into a ps_sensor_adapter_t for core.
 */
ps_sensor_adapter_t sensor_mgr_as_adapter(sensor_mgr_ctx_t* ctx);

#ifdef __cplusplus
}
#endif

#endif /* PS_SENSOR_MGR_H */
