/**
 * @file    board_stm32l432.c
 * @brief   Board shim for STM32L432: timebase wrapper.
 *
 */

#include "app/board.h"
#include "stm32l4xx_hal.h"

/** @brief Milliseconds since boot (HAL_GetTick wrapper). */
uint32_t board_millis(void) {
    return HAL_GetTick();
}
