/**
 * @file    board_stm32l432.c
 * @brief   Board shim for STM32L432: timebase + I2C.
 *
 */

#include "app/board.h"
#include "stm32l4xx_hal.h"

extern I2C_HandleTypeDef hi2c1;   /* provided by CubeMX */

/* Constant timeout (ms) for I2C transfers. */
#define BOARD_I2C_TIMEOUT_MS (10u)

/** @brief Milliseconds since boot (HAL_GetTick wrapper). */
uint32_t board_millis(void) {
    return HAL_GetTick();
}

/* ---- I2C ---- */

board_i2c_bus_t board_i2c_default_bus(void)
{
    /* Hand out the default bus token explicitly. */
    return (board_i2c_bus_t)&hi2c1;
}

bool board_i2c_bus_read_reg(board_i2c_bus_t bus, 
                            uint8_t addr7, uint8_t reg, 
                            uint8_t *buf, uint8_t len)
{
    bool ok = false;
    I2C_HandleTypeDef *i2c = NULL;
    HAL_StatusTypeDef rc = HAL_ERROR;
    uint16_t addr8 = 0u;

    /* Preconditions: explicit bus; buffer rules */
    if ((bus == NULL) || ((buf == NULL) && (len != 0u))) {
        ok = false;
    } else {
        i2c = (I2C_HandleTypeDef *)bus;     /* cast from opaque token */

        if (len == 0u) {
            ok = true;                      /* no-op success */
        } else {
            /* Build 8-bit address (7-bit << 1) */
            addr8 = (uint16_t)((uint16_t)addr7 << 1u);

            rc = HAL_I2C_Mem_Read(i2c,
                                  addr8,
                                  (uint16_t)reg,
                                  I2C_MEMADD_SIZE_8BIT,
                                  buf,
                                  (uint16_t)len,
                                  (uint32_t)BOARD_I2C_TIMEOUT_MS);

            ok = (rc == HAL_OK) ? true : false;
        }
    }

    return ok;
}

bool board_i2c_bus_write_reg(board_i2c_bus_t bus, 
                            uint8_t addr7, uint8_t reg, 
                            uint8_t *buf, uint8_t len)
{
    bool ok = false; 
    I2C_HandleTypeDef *i2c = NULL;
    HAL_StatusTypeDef rc = HAL_ERROR;
    uint16_t addr8 = 0u;

    if ((bus == NULL) || ((buf == NULL) && (len != 0u))) {
        ok = false;
    } else {
        i2c = (I2C_HandleTypeDef *)bus;     /* cast from opaque token */

        if (len == 0u) {
            ok = true;                      /* no-op success */
        } else {
            addr8 = (uint16_t)((uint16_t)addr7 << 1u);

            rc = HAL_I2C_Mem_Write(i2c,
                                   addr8,
                                   (uint16_t)reg,
                                   I2C_MEMADD_SIZE_8BIT,
                                   buf,
                                   (uint16_t)len,
                                   (uint32_t)BOARD_I2C_TIMEOUT_MS);

            ok = (rc == HAL_OK) ? true : false;
        }
    }

    return ok;
}
