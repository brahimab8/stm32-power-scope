#ifndef PS_PROTOCOL_COMMANDS_H
#define PS_PROTOCOL_COMMANDS_H

#include <stddef.h>
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

static inline bool ps_cmd_decode_noarg(const uint8_t* payload, uint16_t len) {
    (void)payload;
    return len == 0u;
}

static inline bool ps_cmd_decode_sensor_id(const uint8_t* payload, uint16_t len,
                                            uint8_t* sensor_id_out, size_t out_cap) {
    if (!payload || !sensor_id_out || out_cap < sizeof(uint8_t) || len < 1u) {
        return false;
    }
    sensor_id_out[0] = payload[0];
    return true;
}

static inline bool ps_cmd_decode_set_period(const uint8_t* payload, uint16_t len,
                                             cmd_set_period_t* out_cmd, size_t out_cap) {
    if (!payload || !out_cmd || out_cap < sizeof(cmd_set_period_t) || len < 3u) {
        return false;
    }
    out_cmd->sensor_id = payload[0];
    out_cmd->period_ms = (uint16_t)payload[1] | ((uint16_t)payload[2] << 8);
    return true;
}

/*
 * Callback-compatible parser adapters for ps_cmd_dispatcher.
 * These keep parser signatures uniform while reusing the decode helpers above.
 */
static inline bool ps_parse_noarg(const uint8_t* payload, uint16_t len,
                                  void* out_struct, size_t out_max_len) {
    (void)out_struct;
    (void)out_max_len;
    return ps_cmd_decode_noarg(payload, len);
}

static inline bool ps_parse_sensor_id(const uint8_t* payload, uint16_t len,
                                      void* out_struct, size_t out_max_len) {
    return ps_cmd_decode_sensor_id(payload, len, (uint8_t*)out_struct, out_max_len);
}

static inline bool ps_parse_set_period(const uint8_t* payload, uint16_t len,
                                       void* out_struct, size_t out_max_len) {
    return ps_cmd_decode_set_period(payload, len, (cmd_set_period_t*)out_struct, out_max_len);
}

#endif /* PS_PROTOCOL_COMMANDS_H */
