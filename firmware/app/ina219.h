/**
 * @file    ina219.h
 * @brief   Minimal INA219 driver: init, configuration, and measurements in engineering units.
 * @note
 *  - Device registers are 16-bit big-endian; this driver reads/writes 2 bytes per register.
 *  - Requires blocking I²C callbacks supplied by the caller (see typedefs below).
 *  - The caller is responsible for selecting a CONFIG mode compatible with intended reads.
 *  - The API is not re-entrant; serialize access if used from multiple contexts.
 */

#ifndef INA219_H
#define INA219_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

/** @name Status codes */
///@{
typedef enum {
    INA219_OK = 0,  /**< Operation successful */
    INA219_E_PARAM, /**< Invalid parameter */
    INA219_E_IO,    /**< I2C transaction failed */
    INA219_E_STATE  /**< Invalid state (e.g., context not initialized) */
} INA219_Status_t;
///@}

/**
 * @brief I²C read callback type (blocking).
 *        Used to read a register starting at @p reg.
 * @param user_ctx  Opaque pointer passed through unchanged.
 * @param addr      7-bit I²C address (0..0x7F).
 * @param reg       8-bit register address.
 * @param buf       Destination buffer.
 * @param len       Number of bytes to read (driver passes 2 for INA219).
 * @return true on success, false on failure.
 */
typedef bool (*INA219_I2C_ReadFn)(void* user_ctx, uint8_t addr, uint8_t reg, uint8_t* buf,
                                  uint8_t len);

/**
 * @brief I²C write callback type (blocking).
 *        Used to write @p len bytes starting at @p reg.
 * @param user_ctx  Opaque pointer passed through unchanged.
 * @param addr      7-bit I²C address (0..0x7F).
 * @param reg       8-bit register address.
 * @param buf       Source buffer.
 * @param len       Number of bytes to write (driver passes 2 for INA219).
 * @return true on success, false on failure.
 */
typedef bool (*INA219_I2C_WriteFn)(void* user_ctx, uint8_t addr, uint8_t reg, uint8_t* buf,
                                   uint8_t len);

/** @name Register addresses (16-bit big-endian) */
///@{
#define INA219_REG_CONFIG (0x00u)
#define INA219_REG_SHUNT_VOLT (0x01u) /**< signed 16-bit, 10 µV/LSB */
#define INA219_REG_BUS_VOLT (0x02u)   /**< 13-bit data at bits[15:3], 4 mV/LSB */
#define INA219_REG_POWER (0x03u)      /**< 20 × current_LSB */
#define INA219_REG_CURRENT (0x04u)    /**< signed 16-bit, current_LSB */
#define INA219_REG_CALIBRATION (0x05u)
///@}

/** @name CONFIG field helpers */
///@{
#define INA219_CFG_BRNG_16V (0x0000u)
#define INA219_CFG_BRNG_32V (0x2000u)

#define INA219_CFG_PG_40mV (0x0000u)
#define INA219_CFG_PG_80mV (0x0800u)
#define INA219_CFG_PG_160mV (0x1000u)
#define INA219_CFG_PG_320mV (0x1800u)

#define INA219_CFG_BADC_12BIT (0x0180u) /**< bus ADC 12-bit (single sample) */
#define INA219_CFG_SADC_12BIT (0x0018u) /**< shunt ADC 12-bit (single sample) */

#define INA219_CFG_MODE_PWRDOWN (0x0000u)
#define INA219_CFG_MODE_SHUNT_TRIG (0x0001u)
#define INA219_CFG_MODE_BUS_TRIG (0x0002u)
#define INA219_CFG_MODE_SHUNT_BUS_TRIG (0x0003u)
#define INA219_CFG_MODE_ADC_OFF (0x0004u)
#define INA219_CFG_MODE_SHUNT_CONT (0x0005u)
#define INA219_CFG_MODE_BUS_CONT (0x0006u)
#define INA219_CFG_MODE_SHUNT_BUS_CONT (0x0007u)

/**
 * @brief Sensible continuous default:
 *        BRNG=32V, PG=320mV, BADC=12-bit (single sample), SADC=12-bit (single sample),
 *        MODE=shunt+bus continuous.
 */
#define INA219_CONFIG_DEFAULT                                                       \
    ((uint16_t)(INA219_CFG_BRNG_32V | INA219_CFG_PG_320mV | INA219_CFG_BADC_12BIT | \
                INA219_CFG_SADC_12BIT | INA219_CFG_MODE_SHUNT_BUS_CONT))

/**
 * @brief One-shot initialization parameters.
 * Pass to ::INA219_Init; values are copied into the context as needed.
 */
typedef struct {
    INA219_I2C_ReadFn i2c_read;   /**< I2C read callback */
    INA219_I2C_WriteFn i2c_write; /**< I2C write callback */
    void* i2c_user;               /**< User pointer passed to callbacks */
    uint8_t i2c_address;          /**< 7-bit I2C address (0..127) */
    uint32_t shunt_milliohm;      /**< Shunt resistance in milliohms (1..1,000,000) */
    uint16_t calibration;         /**< Calibration register value (1..65535) */
    uint16_t config;              /**< CONFIG register value (e.g., ::INA219_CONFIG_DEFAULT) */
} INA219_Init_t;

/**
 * @brief Driver context (persistent runtime state).
 * Keep one instance per sensor.
 */
typedef struct {
    INA219_I2C_ReadFn i2c_read;   /**< I2C read callback */
    INA219_I2C_WriteFn i2c_write; /**< I2C write callback */
    void* i2c_user;               /**< User pointer passed to callbacks */
    uint8_t addr;                 /**< 7-bit I2C address */
    uint32_t shunt_milliohm;      /**< Stored to recompute scales on calibration change */
    uint16_t calibration;         /**< Current calibration register value */
    uint16_t current_scale_uA;    /**< µA per LSB for CURRENT register */
    uint16_t power_scale_mW;      /**< mW per LSB for POWER register */
    bool initialized;             /**< True after successful ::INA219_Init */
} INA219_Ctx_t;

/**
 * @brief Initialize the INA219 and precompute scaling factors.
 *        Writes CONFIG then CALIBRATION and caches integer scales.
 * @param ctx   Driver context (output); must be non-NULL.
 * @param init  Initialization parameters; must be non-NULL.
 * @return ::INA219_OK on success.
 */
INA219_Status_t INA219_Init(INA219_Ctx_t* ctx, const INA219_Init_t* init);

/**
 * @brief Write a new CONFIG value to the device.
 * @param ctx          Driver context.
 * @param config_value Full 16-bit CONFIG register value.
 * @return ::INA219_OK on success.
 * @note Set the MODE bits in the CONFIG register to choose between continuous or triggered
 * (single-shot) conversion.
 */
INA219_Status_t INA219_WriteConfig(INA219_Ctx_t* ctx, uint16_t config_value);

/**
 * @brief Update the CALIBRATION register and recompute scales.
 * @param ctx          Driver context.
 * @param calibration  New calibration value (1..65535).
 * @return ::INA219_OK on success.
 */
INA219_Status_t INA219_SetCalibration(INA219_Ctx_t* ctx, uint16_t calibration);

/**
 * @brief Read bus voltage.
 * @param ctx     Driver context.
 * @param bus_mV  Output in millivolts (0..65535).
 * @return ::INA219_OK on success.
 */
INA219_Status_t INA219_ReadBusVoltage_mV(INA219_Ctx_t* ctx, uint16_t* bus_mV);

/**
 * @brief Read shunt voltage.
 * @param ctx       Driver context.
 * @param shunt_uV  Output, microvolts (signed).
 * @return ::INA219_OK on success.
 */
INA219_Status_t INA219_ReadShuntVoltage_uV(INA219_Ctx_t* ctx, int32_t* shunt_uV);

/**
 * @brief Read current.
 * @param ctx         Driver context.
 * @param current_uA  Output in microamperes (signed).
 * @return ::INA219_OK on success.
 * @note Requires a mode that measures shunt current and a valid calibration.
 */
INA219_Status_t INA219_ReadCurrent_uA(INA219_Ctx_t* ctx, int32_t* current_uA);

/**
 * @brief Read power.
 * @param ctx        Driver context.
 * @param power_mW   Output, milliwatts.
 * @return ::INA219_OK on success.
 * @note Requires a mode that measures both bus and shunt (for internal power computation).
 */
INA219_Status_t INA219_ReadPower_mW(INA219_Ctx_t* ctx, uint32_t* power_mW);

#ifdef __cplusplus
}
#endif
#endif /* INA219_H */
