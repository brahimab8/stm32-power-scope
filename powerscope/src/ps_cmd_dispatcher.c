/**
 * @file    ps_cmd_dispatcher.c
 * @brief   Command dispatcher: parse protocol CMD payloads and update pending commands.
 */

#include "ps_cmd_dispatcher.h"

#include <ps_config.h>
#include <string.h>

/* Initialize commands to default state */
void ps_cmds_init(ps_cmds_t* cmds) {
    if (!cmds) return;
    memset(cmds, 0, sizeof(*cmds));
}

/* Parse CMD payload and update requested commands */
bool ps_cmd_dispatch(const uint8_t* payload, uint16_t len, ps_cmds_t* cmds) {
    if (!payload || len == 0 || !cmds) return false;

    bool handled = false;

    for (uint16_t i = 0; i < len; ++i) {
        switch (payload[i]) {
            case CMD_START:
                cmds->start_stop.requested = true;
                cmds->start_stop.start = true;  // start requested
                handled = true;
                break;

            case CMD_STOP:
                cmds->start_stop.requested = true;
                cmds->start_stop.start = false;  // stop requested
                handled = true;
                break;

            case CMD_SET_PERIOD:
                if ((i + 2) < len) {  // period is 2 bytes LE
                    uint16_t period = (uint16_t)payload[i + 1] | ((uint16_t)payload[i + 2] << 8);
                    if (period >= PS_STREAM_PERIOD_MIN_MS && period <= PS_STREAM_PERIOD_MAX_MS) {
                        cmds->set_period.requested = true;
                        cmds->set_period.period_ms = period;
                        handled = true;
                    }
                    i += 2;  // skip period bytes
                }
                break;

            default:
                break;
        }
    }

    return handled;
}
