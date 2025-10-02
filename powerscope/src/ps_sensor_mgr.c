/**
 * @file    ps_sensor_mgr.c
 * @brief   Generic sensor manager – cooperative and cached sampling.
 *
 * Hardware-agnostic module implementing a ps_sensor_adapter_t interface
 * for streaming cores. Supports cooperative start/poll and deterministic
 * fill of last sample.
 */

#include "ps_sensor_mgr.h"

#include <string.h>

/* --- Init / Deinit --- */

bool sensor_mgr_init(sensor_mgr_ctx_t* ctx, sensor_iface_t iface, uint8_t* buf,
                     uint32_t (*now_ms_fn)(void)) {
    if (!ctx || !iface.read_sample || iface.sample_size == 0 || !buf || !now_ms_fn) return false;

    ctx->iface = iface;
    ctx->last_sample = buf;
    ctx->sample_len = iface.sample_size;
    memset(ctx->last_sample, 0, ctx->sample_len);
    ctx->last_err = 0;
    ctx->last_sample_ms = 0;
    ctx->state = IDLE;
    ctx->now_ms = now_ms_fn;
    return true;
}

void sensor_mgr_deinit(sensor_mgr_ctx_t* ctx) {
    if (!ctx) return;
    ctx->state = IDLE;
}

/* --- Blocking sample --- */

bool sensor_mgr_sample_blocking(sensor_mgr_ctx_t* ctx) {
    if (!ctx || !ctx->iface.read_sample || !ctx->last_sample) return false;

    if (ctx->iface.read_sample(ctx->iface.hw_ctx, ctx->last_sample)) {
        ctx->last_err = 0;
        ctx->last_sample_ms = ctx->now_ms();
        ctx->state = READY;
        return true;
    } else {
        ctx->last_err = -1;
        ctx->state = ERROR;
        return false;
    }
}

/* --- Cooperative interface --- */

int sensor_mgr_start(sensor_mgr_ctx_t* ctx) {
    if (!ctx) return SENSOR_MGR_ERROR;

    if (ctx->state == READY) return SENSOR_MGR_READY;
    if (ctx->state == REQUESTED) return SENSOR_MGR_BUSY;

    ctx->state = REQUESTED;
    return SENSOR_MGR_BUSY;
}

int sensor_mgr_poll(sensor_mgr_ctx_t* ctx) {
    if (!ctx) return SENSOR_MGR_ERROR;

    switch (ctx->state) {
        case READY:
        case IDLE:
            return SENSOR_MGR_READY;
        case REQUESTED:
            if (sensor_mgr_sample_blocking(ctx)) return SENSOR_MGR_READY;
            return SENSOR_MGR_ERROR;
        case ERROR:
            return SENSOR_MGR_ERROR;
        default:
            return SENSOR_MGR_ERROR;
    }
}

/* --- Fill cached sample (non-blocking) --- */

size_t sensor_mgr_fill(sensor_mgr_ctx_t* ctx, uint8_t* dst, size_t max_len) {
    if (!ctx || !dst || !ctx->last_sample || ctx->state != READY) return 0;
    if (max_len < ctx->sample_len) return 0;

    memcpy(dst, ctx->last_sample, ctx->sample_len);
    return ctx->sample_len;
}

/* --- Error / timestamp --- */

int sensor_mgr_last_error(sensor_mgr_ctx_t* ctx) {
    return ctx ? ctx->last_err : -999;
}

uint32_t sensor_mgr_last_sample_ms(sensor_mgr_ctx_t* ctx) {
    return ctx ? ctx->last_sample_ms : 0;
}

/* --- Adapter wrappers --- */
static size_t sensor_mgr_fill_adapter(void* ctx, uint8_t* dst, size_t max_len) {
    return sensor_mgr_fill((sensor_mgr_ctx_t*)ctx, dst, max_len);
}

static int sensor_mgr_start_adapter(void* ctx) {
    return sensor_mgr_start((sensor_mgr_ctx_t*)ctx);
}

static int sensor_mgr_poll_adapter(void* ctx) {
    return sensor_mgr_poll((sensor_mgr_ctx_t*)ctx);
}

/* --- Adapter factory --- */
ps_sensor_adapter_t sensor_mgr_as_adapter(sensor_mgr_ctx_t* ctx) {
    ps_sensor_adapter_t adapter;

    adapter.ctx = ctx;
    adapter.fill = sensor_mgr_fill_adapter;
    adapter.start = sensor_mgr_start_adapter;
    adapter.poll = sensor_mgr_poll_adapter;

    return adapter;
}
