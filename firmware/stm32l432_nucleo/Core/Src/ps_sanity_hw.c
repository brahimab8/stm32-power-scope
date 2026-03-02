/**
 * @file ps_sanity_hw.c
 * @brief Compile-time integration-checks for hardware and sensor configuration.
 *
 * This file performs static assertions to ensure that hardware-specific configuration
 * values are consistent with protocol definitions and app configuration.
 */

#include "protocol_defs.h"
#include "ps_assert.h"
#include "sensors/ina219/sample.h"

// /* Sensor stream payload must not exceed protocol max */
PS_STATIC_ASSERT(INA219_SAMPLE_SIZE <= PROTO_MAX_PAYLOAD, "PS_SENSOR_BUF_LEN > PROTO_MAX_PAYLOAD");
