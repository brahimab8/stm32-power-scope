/**
 * @file    ps_cmd_handlers.c
 * @brief   Generic command handler implementations.
 */

#include "ps_cmd_handlers.h"
#include <protocol/constants.h>
#include <board.h>
#include <byteio.h>

#include "protocol/commands.h"
#include "protocol/errors.h"
#include "protocol/responses.h"
#include "ps_config.h"

/* Forward declarations */
static ps_core_sensor_stream_t* get_sensor_by_runtime_id(ps_core_t* core, uint8_t runtime_id);

/* ===== Helper Functions ===== */

static ps_core_sensor_stream_t* get_sensor_by_runtime_id(ps_core_t* core, uint8_t runtime_id) {
    for (uint8_t i = 0; i < core->num_sensors; ++i) {
        if (core->sensors[i].runtime_id == runtime_id) {
            return &core->sensors[i];
        }
    }
    return NULL;
}

/* ===== Module state ===== */
static ps_core_t* g_handler_core = NULL;

/* ===== Command Handlers ===== */

static bool handle_ping(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    (void)core;
    (void)cmd_struct;
    (void)resp_buf;
    if (resp_len != NULL) {
        *resp_len = 0u;
    }
    return true;
}

static bool handle_start(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_start_t* cmd = (const cmd_start_t*)cmd_struct;
    ps_core_sensor_stream_t* sensor = get_sensor_by_runtime_id(core, cmd->sensor_id);

    if (sensor == NULL) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_INVALID_VALUE;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    if (resp_len != NULL) {
        *resp_len = 0u;
    }

    sensor->streaming = 1u;
    sensor->sm = CORE_SM_IDLE;
    sensor->seq = 0u;

    return true;
}

static bool handle_stop(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_stop_t* cmd = (const cmd_stop_t*)cmd_struct;
    ps_core_sensor_stream_t* sensor = get_sensor_by_runtime_id(core, cmd->sensor_id);

    if (sensor == NULL) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_INVALID_VALUE;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    if (resp_len != NULL) {
        *resp_len = 0u;
    }

    sensor->streaming = 0u;
    sensor->sm = CORE_SM_IDLE;
    return true;
}

static bool handle_set_period(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_set_period_t* cmd = (const cmd_set_period_t*)cmd_struct;
    ps_core_sensor_stream_t* sensor = get_sensor_by_runtime_id(core, cmd->sensor_id);

    if (sensor == NULL) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_INVALID_VALUE;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    if ((cmd->period_ms < PS_STREAM_PERIOD_MIN_MS) || (cmd->period_ms > PS_STREAM_PERIOD_MAX_MS)) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_INVALID_VALUE;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    sensor->period_ms = cmd->period_ms;

    if (resp_len != NULL) {
        *resp_len = 0u;
    }
    return true;
}

static bool handle_get_period(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_get_period_t* cmd = (const cmd_get_period_t*)cmd_struct;
    ps_core_sensor_stream_t* sensor = get_sensor_by_runtime_id(core, cmd->sensor_id);

    if (sensor == NULL) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_INVALID_VALUE;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    if ((resp_buf == NULL) || (resp_len == NULL) || (*resp_len < (uint16_t)sizeof(uint32_t))) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    size_t written = ps_resp_encode_get_period(resp_buf, *resp_len, sensor->period_ms);
    if (written == 0u) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    *resp_len = (uint16_t)written;
    return true;
}

static bool handle_get_sensors(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    (void)cmd_struct;

    if ((resp_buf == NULL) || (resp_len == NULL)) {
        return false;
    }

    if (core->num_sensors > PS_PROTOCOL_MAX_SENSORS) {
        if (*resp_len >= 1u) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        *resp_len = 1u;
        return false;
    }

    ps_resp_get_sensors_t resp = {0};
    resp.count = core->num_sensors;
    for (size_t i = 0; i < resp.count; ++i) {
        ps_core_sensor_stream_t* sensor = &core->sensors[i];
        resp.sensors[i].sensor_runtime_id = sensor->runtime_id;
        resp.sensors[i].type_id = (sensor->adapter != NULL) ? sensor->adapter->type_id
                                                            : PS_PROTOCOL_SENSOR_TYPE_UNKNOWN;
    }

    size_t written = ps_resp_encode_get_sensors(resp_buf, *resp_len, &resp);
    if (written == 0u) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    *resp_len = (uint16_t)written;
    return true;
}

static bool handle_read_sensor(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    const cmd_read_sensor_t* cmd = (const cmd_read_sensor_t*)cmd_struct;
    ps_core_sensor_stream_t* sensor = NULL;
    int status = 0;
    uint8_t sample_buf[PS_PROTOCOL_MAX_PAYLOAD - 1u];
    size_t filled = 0u;
    size_t payload_size = 0u;

    if ((resp_buf == NULL) || (resp_len == NULL) || (*resp_len == 0u)) {
        return false;
    }

    sensor = get_sensor_by_runtime_id(core, cmd->sensor_id);
    if ((sensor == NULL) || (sensor->adapter == NULL)) {
        resp_buf[0] = PS_ERR_INVALID_VALUE;
        *resp_len = 1u;
        return false;
    }

    if (sensor->streaming != 0u) {
        resp_buf[0] = PS_ERR_SENSOR_BUSY;
        *resp_len = 1u;
        return false;
    }

    status = sensor->adapter->start(sensor->adapter->ctx);
    if (status == CORE_SENSOR_ERROR) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1u;
        return false;
    }

    while (status == CORE_SENSOR_BUSY) {
        status = sensor->adapter->poll(sensor->adapter->ctx);
        if (status == CORE_SENSOR_ERROR) {
            resp_buf[0] = PS_ERR_INTERNAL;
            *resp_len = 1u;
            return false;
        }
    }

    filled = sensor->adapter->fill(sensor->adapter->ctx, sample_buf, sizeof(sample_buf));
    if (filled == 0u) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1u;
        return false;
    }

    payload_size = ps_resp_encode_sensor_packet(resp_buf, *resp_len, sensor->runtime_id,
                                                sample_buf, filled);
    if (payload_size == 0u) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1u;
        return false;
    }

    *resp_len = (uint16_t)payload_size;
    return true;
}

static bool handle_get_uptime(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf, uint16_t* resp_len) {
    (void)cmd_struct;

    if ((resp_buf == NULL) || (resp_len == NULL) || (*resp_len < (uint16_t)sizeof(uint32_t))) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    size_t written = ps_resp_encode_get_uptime(resp_buf, *resp_len, core->now_ms());
    if (written == 0u) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    *resp_len = (uint16_t)written;
    return true;
}

static bool handle_get_board_uid(ps_core_t* core, const void* cmd_struct, uint8_t* resp_buf,
                                 uint16_t* resp_len) {
    (void)core;
    (void)cmd_struct;

    if ((resp_buf == NULL) || (resp_len == NULL) || (*resp_len < PS_PROTOCOL_BOARD_UID_LEN)) {
        if ((resp_buf != NULL) && (resp_len != NULL) && (*resp_len >= 1u)) {
            resp_buf[0] = PS_ERR_OVERFLOW;
        }
        if (resp_len != NULL) {
            *resp_len = 1u;
        }
        return false;
    }

    uint8_t uid_raw[PS_PROTOCOL_BOARD_UID_LEN] = {0};
    if (!board_get_uid_raw(uid_raw)) {
        resp_buf[0] = PS_ERR_INTERNAL;
        *resp_len = 1u;
        return false;
    }

    ps_resp_get_board_uid_t info = {
        .uid_w0 = byteio_rd_u32le(uid_raw + 0u),
        .uid_w1 = byteio_rd_u32le(uid_raw + 4u),
        .uid_w2 = byteio_rd_u32le(uid_raw + 8u),
    };

    size_t written = ps_resp_encode_get_board_uid(resp_buf, *resp_len, &info);
    if (written == 0u) {
        resp_buf[0] = PS_ERR_OVERFLOW;
        *resp_len = 1u;
        return false;
    }

    *resp_len = (uint16_t)written;
    return true;
}

/* ===== Wrapper functions for registration ===== */

static bool ping_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_ping(g_handler_core, cmd, resp, len);
}

static bool start_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_start(g_handler_core, cmd, resp, len);
}

static bool stop_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_stop(g_handler_core, cmd, resp, len);
}

static bool set_period_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_set_period(g_handler_core, cmd, resp, len);
}

static bool get_period_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_get_period(g_handler_core, cmd, resp, len);
}

static bool get_sensors_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_get_sensors(g_handler_core, cmd, resp, len);
}

static bool read_sensor_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_read_sensor(g_handler_core, cmd, resp, len);
}

static bool get_uptime_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_get_uptime(g_handler_core, cmd, resp, len);
}

static bool get_board_uid_wrapper(const void* cmd, uint8_t* resp, uint16_t* len) {
    return handle_get_board_uid(g_handler_core, cmd, resp, len);
}

/* ===== Registration ===== */

void ps_cmd_handlers_register(ps_core_t* core, ps_cmd_dispatcher_t* dispatcher) {
    g_handler_core = core;

    ps_cmd_register_handler(dispatcher, CMD_PING, ps_parse_noarg, ping_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_START, ps_parse_sensor_id, start_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_STOP, ps_parse_sensor_id, stop_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_GET_PERIOD, ps_parse_sensor_id, get_period_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_SET_PERIOD, ps_parse_set_period, set_period_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_GET_SENSORS, ps_parse_noarg, get_sensors_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_READ_SENSOR, ps_parse_sensor_id, read_sensor_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_GET_UPTIME, ps_parse_noarg, get_uptime_wrapper);
    ps_cmd_register_handler(dispatcher, CMD_GET_BOARD_UID, ps_parse_noarg, get_board_uid_wrapper);
}
