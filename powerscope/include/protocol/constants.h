/**
 * @file    constants.h
 * @brief   Protocol-level constants for the Power Scope wire contract.
 *
 * These values describe the binary wire protocol and should stay stable
 * within a protocol version.
 */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Canonical protocol constants. */
#define PS_PROTOCOL_MAGIC 0x5AA5U
#define PS_PROTOCOL_VERSION 0U
#define PS_PROTOCOL_TYPE_STREAM 0U
#define PS_PROTOCOL_TYPE_CMD 1U
#define PS_PROTOCOL_TYPE_ACK 2U
#define PS_PROTOCOL_TYPE_NACK 3U

#define PS_PROTOCOL_HDR_LEN 16U
#define PS_PROTOCOL_CRC_LEN 2U
#define PS_PROTOCOL_MAX_PAYLOAD 46U
#define PS_PROTOCOL_FRAME_MAX_BYTES (PS_PROTOCOL_HDR_LEN + PS_PROTOCOL_MAX_PAYLOAD + PS_PROTOCOL_CRC_LEN)

/*
 * Upper bound used by variable-length protocol helpers such as GET_SENSORS.
 * This is a protocol contract limit, not a core runtime limit.
 */
#define PS_PROTOCOL_MAX_SENSORS 4U

/* Sensor type marker used when a sensor adapter is unavailable. */
#define PS_PROTOCOL_SENSOR_TYPE_UNKNOWN 0xFFU

/* Board identity payload contract (GET_BOARD_UID). */
#define PS_PROTOCOL_BOARD_UID_LEN 12U

#ifdef __cplusplus
}
#endif
