/**
 * @file    ps_cmd_handlers.h
 * @brief   Generic command handlers for Power Scope protocol.
 */

#pragma once

#include "ps_cmd_dispatcher.h"
#include "ps_core.h"

/**
 * @brief Register all generic command handlers with the dispatcher.
 * @param core Pointer to ps_core_t instance
 * @param dispatcher Pointer to ps_cmd_dispatcher_t instance
 *
 * Registers handlers for:
 *  - CMD_PING
 *  - CMD_START
 *  - CMD_STOP
 *  - CMD_GET_PERIOD
 *  - CMD_SET_PERIOD
 *  - CMD_GET_SENSORS
 *  - CMD_READ_SENSOR
 *  - CMD_GET_UPTIME
 *  - CMD_GET_BOARD_UID
 */
void ps_cmd_handlers_register(ps_core_t* core, ps_cmd_dispatcher_t* dispatcher);
