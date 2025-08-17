/**
 * @file    ps_app.h
 * @brief   Streaming core API: initialize and run the tick loop.
 *
 * Call ps_app_init() once after USB init; call ps_app_tick() in main loop.
 */


#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Initialize rings, USB hooks, and internal state. Call once after USB init. */
void ps_app_init(void);

/** Run periodic work: produce payload (current build), pump USB, parse commands. */
void ps_app_tick(void);   // call from the main loop

#ifdef __cplusplus
}
#endif
