#ifndef PS_CMD_DEFS_H
#define PS_CMD_DEFS_H

#include <stdbool.h>
#include <stdint.h>

/* --- Command opcodes --- */
typedef enum {
    CMD_START = 0x01,
    CMD_STOP = 0x02,
    CMD_SET_PERIOD = 0x03,
    CMD_GET_PERIOD = 0x04,
    CMD_PING = 0x05,
    CMD_GET_SENSORS = 0x06,
    CMD_READ_SENSOR = 0x07,
    CMD_GET_UPTIME  = 0x08, 
    // Reserved for future commands
    CMD_NONE = 0xFF
} ps_cmd_opcode_t;

/* --- Command payload structs --- */
typedef struct {
    uint8_t sensor_id;
} cmd_start_t;

typedef struct {
    uint8_t sensor_id;
} cmd_stop_t;

typedef struct {
    uint8_t sensor_id;
    uint16_t period_ms;
} cmd_set_period_t;

typedef struct {
    uint8_t sensor_id;
} cmd_get_period_t;

typedef struct {
    uint8_t sensor_id;
} cmd_read_sensor_t;

#endif /* PS_CMD_DEFS_H */
