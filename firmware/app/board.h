/**
 * @file    board.h
 * @brief   Minimal board abstraction used by the app (no HAL leaks).
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Millisecond monotonic tick (wrap OK). */
uint32_t board_millis(void);

/** Timebase in Hz for board_millis() (usually 1000). */
static inline uint32_t board_timebase_hz(void) {
    return 1000u;
}

#ifdef __cplusplus
}
#endif
