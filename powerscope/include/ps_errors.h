/**
 * @file    ps_errors.h
 * @brief   Power Scope protocol error defs
 */
#ifndef PS_ERRORS_H
#define PS_ERRORS_H

#include <stdint.h>

/* --- Generic protocol error codes --- */
typedef enum {
    PS_OK = 0,                 // success / ACK
    PS_ERR_INVALID_CMD = 1,    // unrecognized command ID
    PS_ERR_INVALID_LEN = 2,    // payload too short/long
    PS_ERR_INVALID_VALUE = 3,  // invalid value in command payload
    PS_ERR_SENSOR_BUSY = 4,    // sensor not ready
    PS_ERR_OVERFLOW = 5,       // response buffer too small
    PS_ERR_INTERNAL = 6,       // unexpected internal error
    PS_ERR_UNKNOWN = 255       // fallback unknown error
} ps_error_t;

#endif /* PS_ERRORS_H */
