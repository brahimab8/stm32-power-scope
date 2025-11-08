/**
 * @file    ps_cmd_dispatcher.h
 * @brief   Command dispatcher: register handlers and dispatch protocol CMD payloads.
 */

#ifndef PS_CMD_DISPATCHER_H
#define PS_CMD_DISPATCHER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CMD_MAX_STRUCT 64

typedef bool (*ps_cmd_parser_t)(const uint8_t* payload, uint16_t len, void* out_struct,
                                size_t out_max_len);
typedef bool (*ps_cmd_handler_t)(const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len);

typedef struct {
    ps_cmd_parser_t parser;
    ps_cmd_handler_t handler;
} ps_cmd_entry_t;

/* ----- Dispatcher struct ----- */
typedef struct ps_cmd_dispatcher_t {
    ps_cmd_entry_t table[256];
    bool (*dispatch)(struct ps_cmd_dispatcher_t* self, uint8_t cmd_id, const uint8_t* payload,
                     uint16_t len, uint8_t* resp_buf, uint16_t* resp_len);
} ps_cmd_dispatcher_t;

/* ---------- API ---------- */
void ps_cmds_init(ps_cmd_dispatcher_t* disp);
void ps_cmd_register_handler(ps_cmd_dispatcher_t* disp, uint8_t opcode, ps_cmd_parser_t parser,
                             ps_cmd_handler_t handler);
bool ps_cmd_dispatcher_dispatch_resp(ps_cmd_dispatcher_t* disp, uint8_t cmd_id,
                                     const uint8_t* payload, uint16_t len, uint8_t* resp_buf,
                                     uint16_t* resp_len);
#ifdef __cplusplus
}
#endif

#endif /* PS_CMD_DISPATCHER_H */
