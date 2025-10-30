/**
 * @file    board_stm32l432.c
 * @brief   Board shim for STM32L432: timebase + I2C.
 *
 */

#include <board.h>
#include "stm32l4xx_hal.h"
#include "ps_transport_adapter.h"

#include <stddef.h>
#include <stdbool.h>

/* Choose transport: uncomment one */
// #define USE_UART_TRANSPORT
#define USE_USB_CDC_TRANSPORT

#if defined(USE_USB_CDC_TRANSPORT) && defined(USE_UART_TRANSPORT)
#error "Only one transport can be selected at a time!"
#elif !defined(USE_USB_CDC_TRANSPORT) && !defined(USE_UART_TRANSPORT)
#error "You must select exactly one transport!"
#endif

#ifdef USE_USB_CDC_TRANSPORT
#include "comm_usb_cdc.h"
#endif

#ifdef USE_UART_TRANSPORT
#include "comm_uart.h"
extern UART_HandleTypeDef huart2;
#endif

/* provided by CubeMX */
extern I2C_HandleTypeDef hi2c1;

/* Internal state to track if LED GPIO is initialized */
static bool debug_led_initialized = false;

/* LED GPIO settings for Nucleo L432KC */
#define DEBUG_LED_GPIO_PORT GPIOA
#define DEBUG_LED_PIN       GPIO_PIN_5

/* Constant timeout (ms) for I2C transfers. */
#define BOARD_I2C_TIMEOUT_MS (10u)

/** @brief Milliseconds since boot (HAL_GetTick wrapper). */
uint32_t board_millis(void) {
    return HAL_GetTick();
}

/* ---- I2C ---- */

board_i2c_bus_t board_i2c_default_bus(void) {
    /* Hand out the default bus token explicitly. */
    return (board_i2c_bus_t)&hi2c1;
}

bool board_i2c_bus_read_reg(board_i2c_bus_t bus, uint8_t addr7, uint8_t reg, uint8_t* buf,
                            uint8_t len) {
    bool ok = false;
    I2C_HandleTypeDef* i2c = NULL;
    HAL_StatusTypeDef rc = HAL_ERROR;
    uint16_t addr8 = 0u;

    /* Preconditions: explicit bus; buffer rules */
    if ((bus == NULL) || ((buf == NULL) && (len != 0u))) {
        ok = false;
    } else {
        i2c = (I2C_HandleTypeDef*)bus; /* cast from opaque token */

        if (len == 0u) {
            ok = true; /* no-op success */
        } else {
            /* Build 8-bit address (7-bit << 1) */
            addr8 = (uint16_t)((uint16_t)addr7 << 1u);

            rc = HAL_I2C_Mem_Read(i2c, addr8, (uint16_t)reg, I2C_MEMADD_SIZE_8BIT, buf,
                                  (uint16_t)len, (uint32_t)BOARD_I2C_TIMEOUT_MS);

            ok = (rc == HAL_OK) ? true : false;
        }
    }

    return ok;
}

bool board_i2c_bus_write_reg(board_i2c_bus_t bus, uint8_t addr7, uint8_t reg, uint8_t* buf,
                             uint8_t len) {
    bool ok = false;
    I2C_HandleTypeDef* i2c = NULL;
    HAL_StatusTypeDef rc = HAL_ERROR;
    uint16_t addr8 = 0u;

    if ((bus == NULL) || ((buf == NULL) && (len != 0u))) {
        ok = false;
    } else {
        i2c = (I2C_HandleTypeDef*)bus; /* cast from opaque token */

        if (len == 0u) {
            ok = true; /* no-op success */
        } else {
            addr8 = (uint16_t)((uint16_t)addr7 << 1u);

            rc = HAL_I2C_Mem_Write(i2c, addr8, (uint16_t)reg, I2C_MEMADD_SIZE_8BIT, buf,
                                   (uint16_t)len, (uint32_t)BOARD_I2C_TIMEOUT_MS);

            ok = (rc == HAL_OK) ? true : false;
        }
    }

    return ok;
}

/* -------- Transport adapter -------- */

void board_transport_init(ps_transport_adapter_t* adapter) {
    if (!adapter) return;

#ifdef USE_USB_CDC_TRANSPORT
    // USB CDC driver functions
    adapter->tx_write       = comm_usb_cdc_try_write;
    adapter->link_ready     = comm_usb_cdc_link_ready;
    adapter->best_chunk     = comm_usb_cdc_best_chunk;
    adapter->set_rx_handler = comm_usb_cdc_set_rx_handler;

    comm_usb_cdc_init(); // initialize hardware driver
#endif

#ifdef USE_UART_TRANSPORT
    // UART driver functions
    comm_uart_init(&huart2);
    uart_transport_set_min_frame_len(BOARD_MIN_CMD_FRAME_LEN );

    adapter->tx_write       = uart_transport_tx_write;
    adapter->link_ready     = uart_transport_link_ready;
    adapter->best_chunk     = uart_transport_best_chunk;
    adapter->set_rx_handler = uart_transport_set_rx_handler;

#endif
}

/* -------- Debug LED -------- */

static void debug_led_init(void) {
    if (debug_led_initialized) return;

    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = DEBUG_LED_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(DEBUG_LED_GPIO_PORT, &gpio);

    HAL_GPIO_WritePin(DEBUG_LED_GPIO_PORT, DEBUG_LED_PIN, GPIO_PIN_RESET);

    debug_led_initialized = true;
}

void board_debug_led_on(void) {
    debug_led_init();
    HAL_GPIO_WritePin(DEBUG_LED_GPIO_PORT, DEBUG_LED_PIN, GPIO_PIN_SET);
}

void board_debug_led_off(void) {
    debug_led_init();
    HAL_GPIO_WritePin(DEBUG_LED_GPIO_PORT, DEBUG_LED_PIN, GPIO_PIN_RESET);
}

void board_debug_led_toggle(void) {
    debug_led_init();
    HAL_GPIO_TogglePin(DEBUG_LED_GPIO_PORT, DEBUG_LED_PIN);
}
