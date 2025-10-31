/**
 * @file    ps_cmd_dispatcher.c
 * @brief   Generic command dispatcher: raw payload → typed struct → handler.
 */

#include "ps_cmd_dispatcher.h"

#include <string.h>

/* ---------- Initialize dispatcher ---------- */
void ps_cmds_init(ps_cmd_dispatcher_t* disp) {
    if (!disp) return;
    memset(disp->table, 0, sizeof(disp->table));
    disp->dispatch = ps_cmd_dispatcher_dispatch_hdr;
}

/* ---------- Register handler ---------- */
void ps_cmd_register_handler(ps_cmd_dispatcher_t* disp, uint8_t opcode, ps_cmd_parser_t parser,
                             ps_cmd_handler_t handler) {
    if (!disp) return;
    disp->table[opcode].parser = parser;
    disp->table[opcode].handler = handler;
}

/* ---------- Dispatch command ---------- */
bool ps_cmd_dispatcher_dispatch_hdr(ps_cmd_dispatcher_t* disp, uint8_t cmd_id,
                                    const uint8_t* payload, uint16_t len) {
    if (!disp) return false;

    ps_cmd_entry_t entry = disp->table[cmd_id];
    if (!entry.parser || !entry.handler) return false;

    uint8_t cmd_struct[CMD_MAX_STRUCT];

    if (!entry.parser(payload, len, cmd_struct, CMD_MAX_STRUCT)) return false;

    return entry.handler(cmd_struct);
}
