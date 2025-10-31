/**
 * @file    ps_cmd_parsers.c
 * @brief   Command parsers for Power Scope commands.
 */
#include "ps_cmd_parsers.h"

#include <stddef.h>
#include <string.h>

bool ps_parse_set_period(const uint8_t* payload, uint16_t len, void* out_struct,
                         size_t out_max_len) {
    if (len < 2 || !out_struct || out_max_len < sizeof(cmd_set_period_t)) return false;
    cmd_set_period_t* cmd = (cmd_set_period_t*)out_struct;
    cmd->period_ms = (uint16_t)payload[0] | ((uint16_t)payload[1] << 8);
    return true;
}

bool ps_parse_noarg(const uint8_t* payload, uint16_t len, void* out_struct, size_t out_max_len) {
    (void)payload;
    (void)out_struct;
    (void)out_max_len;
    return (len == 0);
}
