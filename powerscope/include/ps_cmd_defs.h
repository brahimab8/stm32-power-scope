#ifndef PS_CMD_DEFS_H
#define PS_CMD_DEFS_H

#include <stdbool.h>
#include <stdint.h>

/* --- Command opcodes --- */
typedef enum {
    CMD_START = 0x01,
    CMD_STOP = 0x02,
    CMD_SET_PERIOD = 0x03,
    // Reserved for future commands
    CMD_NONE = 0xFF
} ps_cmd_opcode_t;

/* --- Command payload structs --- */
typedef struct {
    bool start; /* true=start, false=stop */
} cmd_start_stop_t;

typedef struct {
    uint16_t period_ms;
} cmd_set_period_t;

#endif /* PS_CMD_DEFS_H */
