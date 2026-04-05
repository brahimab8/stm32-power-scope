/**
 * @file    responses.h
 * @brief   Protocol response payload definitions and builders.
 *
 * These helpers build semantic response payloads only.
 * Framing (ACK/NACK header fields, CRC, etc.) lives in protocol/header.h
 * and the tx layer.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "protocol/constants.h"

#ifdef __cplusplus
extern "C" {
#endif

/* --------------------------- Typed response bodies ------------------------- */

typedef struct {
    uint32_t period_ms;
} ps_resp_get_period_t;

typedef struct {
    uint32_t uptime_ms;
} ps_resp_get_uptime_t;

/* One sensor description entry returned by GET_SENSORS. */
typedef struct {
    uint8_t sensor_runtime_id;
    uint8_t type_id;
} ps_resp_sensor_info_t;

/* Semantic container for GET_SENSORS response assembly. */
typedef struct {
    size_t count;
    ps_resp_sensor_info_t sensors[PS_PROTOCOL_MAX_SENSORS];
} ps_resp_get_sensors_t;

/* Payload emitted by READ_SENSOR.
 * Wire layout:
 *   [sensor_runtime_id][raw_readings...]
 */
typedef struct {
    uint8_t sensor_runtime_id;
    uint8_t raw_readings[];
} ps_resp_sensor_packet_t;

/* NACK payload: one byte error code. */
typedef struct {
    uint8_t error_code;
} ps_resp_nack_t;

static inline size_t ps_resp_write_u8(uint8_t* out, size_t cap, uint8_t value) {
    if (!out || cap < 1u) {
        return 0u;
    }
    out[0] = value;
    return 1u;
}

static inline size_t ps_resp_write_u32_le(uint8_t* out, size_t cap, uint32_t value) {
    if (!out || cap < 4u) {
        return 0u;
    }
    out[0] = (uint8_t)(value & 0xFFu);
    out[1] = (uint8_t)((value >> 8) & 0xFFu);
    out[2] = (uint8_t)((value >> 16) & 0xFFu);
    out[3] = (uint8_t)((value >> 24) & 0xFFu);
    return 4u;
}

static inline size_t ps_resp_encode_get_period(uint8_t* out, size_t cap,
                                               uint32_t period_ms) {
    return ps_resp_write_u32_le(out, cap, period_ms);
}

static inline size_t ps_resp_encode_get_uptime(uint8_t* out, size_t cap,
                                               uint32_t uptime_ms) {
    return ps_resp_write_u32_le(out, cap, uptime_ms);
}

/*
 * GET_SENSORS wire format is a repeated list of 2-byte entries:
 *   [sensor_runtime_id][type_id] ...
 */
static inline size_t ps_resp_get_sensors_wire_size(size_t count) {
    return count * 2u;
}

static inline size_t ps_resp_encode_get_sensors(uint8_t* out, size_t cap,
                                                const ps_resp_get_sensors_t* sensors) {
    if (!out || !sensors) {
        return 0u;
    }
    if (sensors->count > PS_PROTOCOL_MAX_SENSORS) {
        return 0u;
    }

    const size_t need = ps_resp_get_sensors_wire_size(sensors->count);
    if (cap < need) {
        return 0u;
    }

    for (size_t i = 0; i < sensors->count; ++i) {
        out[(i * 2u) + 0u] = sensors->sensors[i].sensor_runtime_id;
        out[(i * 2u) + 1u] = sensors->sensors[i].type_id;
    }
    return need;
}

static inline size_t ps_resp_encode_sensor_packet(uint8_t* out, size_t cap,
                                                  uint8_t sensor_runtime_id,
                                                  const uint8_t* raw_readings,
                                                  size_t raw_readings_len) {
    if (!out || (!raw_readings && raw_readings_len != 0u)) {
        return 0u;
    }
    if (cap < (raw_readings_len + 1u)) {
        return 0u;
    }

    out[0] = sensor_runtime_id;
    for (size_t i = 0; i < raw_readings_len; ++i) {
        out[i + 1u] = raw_readings[i];
    }
    return raw_readings_len + 1u;
}

static inline size_t ps_resp_encode_nack(uint8_t* out, size_t cap, uint8_t error_code) {
    return ps_resp_write_u8(out, cap, error_code);
}

#ifdef __cplusplus
}
#endif
