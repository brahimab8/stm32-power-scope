/**
 * @file    ps_cmd_dispatcher.h
 * @brief   Command dispatcher: parse protocol CMD payloads and update pending commands.
 * @details Each command has a 'requested' flag. The core applies commands in its tick
 *          when requested.
 */

#ifndef PS_CMD_DISPATCHER_H
#define PS_CMD_DISPATCHER_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- command opcodes --- */
typedef enum {
    CMD_START = 0x01U,
    CMD_STOP = 0x02U,
    CMD_SET_PERIOD = 0x03U,
} ps_cmd_opcode_t;

/* --- Command structs --- */

/**
 * @brief Start/Stop streaming command
 */
typedef struct {
    bool requested; /**< Set to true when host requests start/stop */
    bool start;     /**< true = start, false = stop */
} ps_cmd_start_stop_t;

/**
 * @brief Set streaming period command
 */
typedef struct {
    bool requested;     /**< true = host requested new period */
    uint16_t period_ms; /**< requested period in ms */
} ps_cmd_set_period_t;

/**
 * @brief All pending commands
 */
typedef struct {
    ps_cmd_start_stop_t start_stop;
    ps_cmd_set_period_t set_period;
} ps_cmds_t;

/* --- Public API --- */

/**
 * @brief Initialize all command structs to default state (no request)
 */
void ps_cmds_init(ps_cmds_t* cmds);

/**
 * @brief Parse CMD payload and mark commands as requested if valid
 *
 * @param payload Pointer to protocol CMD payload
 * @param len     Payload length
 * @param cmds    Pointer to command structs to update
 * @return true if any command was recognized, false otherwise
 */
bool ps_cmd_dispatch(const uint8_t* payload, uint16_t len, ps_cmds_t* cmds);

#ifdef __cplusplus
}
#endif

#endif /* PS_CMD_DISPATCHER_H */
