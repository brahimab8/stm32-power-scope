/**
 * @file    ps_cmd_parsers.c
 * @brief   Command parsers for Power Scope commands.
 */
#include "ps_cmd_parsers.h"

#include <stddef.h>
#include <string.h>

bool ps_parse_set_period(const uint8_t* payload, uint16_t len, void* out_struct,
                         size_t out_max_len) {
    if (len < 3 || !out_struct || out_max_len < sizeof(cmd_set_period_t)) return false;

    cmd_set_period_t* cmd = (cmd_set_period_t*)out_struct;
    cmd->sensor_id = payload[0];  // first byte = runtime sensor ID
    cmd->period_ms = (uint16_t)payload[1] | ((uint16_t)payload[2] << 8);
    return true;
}

bool ps_parse_noarg(const uint8_t* payload, uint16_t len, void* out_struct, size_t out_max_len) {
    (void)payload;
    (void)out_struct;
    (void)out_max_len;
    return (len == 0);
}

bool ps_parse_sensor_id(const uint8_t* payload, uint16_t len, void* out_struct,
                        size_t out_max_len) {
    if (len < 1 || !out_struct || out_max_len < sizeof(uint8_t)) return false;

    uint8_t* sensor_id_ptr = (uint8_t*)out_struct;
    *sensor_id_ptr = payload[0];  // first byte = sensor runtime ID
    return true;
}
