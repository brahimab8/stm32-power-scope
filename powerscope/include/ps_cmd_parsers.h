/**
 * @file    ps_cmd_parsers.h
 * @brief   Command parsers for Power Scope commands.
 */
#ifndef PS_CMD_PARSERS_H
#define PS_CMD_PARSERS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ps_cmd_defs.h"

#ifdef __cplusplus
extern "C" {
#endif

bool ps_parse_set_period(const uint8_t* payload, uint16_t len, void* out_struct,
                         size_t out_max_len);
bool ps_parse_noarg(const uint8_t* payload, uint16_t len, void* out_struct, size_t out_max_len);

#ifdef __cplusplus
}
#endif

#endif /* PS_CMD_PARSERS_H */
