/**
 * @file    ps_payload.h
 * @brief   Protocol payload helper functions.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Build sensor payload: [runtime_id][sample bytes...].
 *
 * @param runtime_id Sensor runtime ID.
 * @param sample_buf Raw sensor sample bytes.
 * @param sample_len Number of sample bytes.
 * @param out Output payload buffer.
 * @param cap Output buffer capacity in bytes.
 * @return size_t Payload size written, or 0 on invalid args/capacity.
 */
size_t ps_payload_build_sensor(uint8_t runtime_id,
                               const uint8_t* sample_buf,
                               size_t sample_len,
                               uint8_t* out,
                               size_t cap);
