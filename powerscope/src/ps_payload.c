/**
 * @file    ps_payload.c
 * @brief   Protocol payload helper functions.
 */

#include "ps_payload.h"

#include <string.h>

size_t ps_payload_build_sensor(uint8_t runtime_id,
                               const uint8_t* sample_buf,
                               size_t sample_len,
                               uint8_t* out,
                               size_t cap) {
    if ((sample_buf == NULL) || (out == NULL) || (cap < (sample_len + 1u))) {
        return 0u;
    }

    out[0] = runtime_id;
    memcpy(out + 1u, sample_buf, sample_len);

    return sample_len + 1u;
}
