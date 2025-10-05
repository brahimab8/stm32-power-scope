/**
 * @file    test_ina219.c
 * @brief   Unit tests for INA219 driver (ina219.c).
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "ina219.h"
#include "unity.h"

/* --- Mock I2C device --- */
static uint8_t mock_regs[256];
static uint8_t mock_addr_seen;
static bool mock_i2c_fail_on_write;
static bool mock_i2c_fail_on_read;

/* simple big-endian 16-bit helpers */
static void mock_write_be16(uint8_t reg, uint16_t val) {
    mock_regs[reg] = (uint8_t)((val >> 8) & 0xFFu);
    mock_regs[reg + 1] = (uint8_t)(val & 0xFFu);
}
static uint16_t mock_read_be16(uint8_t reg) {
    return (uint16_t)(((uint16_t)mock_regs[reg] << 8) | (uint16_t)mock_regs[reg + 1]);
}

/* Mock I2C callbacks */
static bool mock_i2c_write(void* user, uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
    (void)user;
    mock_addr_seen = addr;
    if (mock_i2c_fail_on_write) return false;
    if (len == 2u) {
        mock_regs[reg] = buf[0];
        mock_regs[reg + 1] = buf[1];
        return true;
    }
    return false;
}
static bool mock_i2c_read(void* user, uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
    (void)user;
    mock_addr_seen = addr;
    if (mock_i2c_fail_on_read) return false;
    if (len == 2u) {
        buf[0] = mock_regs[reg];
        buf[1] = mock_regs[reg + 1];
        return true;
    }
    return false;
}

/* --- Test fixtures --- */
static INA219_Ctx_t ctx;
static INA219_Init_t init;

/* reset mock device and ctx */
void setUp(void) {
    memset(&mock_regs, 0, sizeof mock_regs);
    mock_addr_seen = 0;
    mock_i2c_fail_on_write = false;
    mock_i2c_fail_on_read = false;
    memset(&ctx, 0, sizeof ctx);
    memset(&init, 0, sizeof init);
}
void tearDown(void) {}

/* --- Tests --- */

/* Init parameter validation (nulls and invalid params) */
void test_init_param_invalid(void) {
    INA219_Status_t st;

    st = INA219_Init(NULL, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    st = INA219_Init(&ctx, NULL);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    init.i2c_read = NULL;
    init.i2c_write = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 1;
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;

    init.i2c_address = 0x80; /* invalid >7-bit */
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    init.i2c_address = 0x40;
    init.shunt_milliohm = 0; /* too small */
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    init.shunt_milliohm = 100;
    init.calibration = 0; /* too small */
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);
}

void test_null_checks(void) {
    uint16_t u16;
    int32_t i32;
    uint32_t u32;

    // Null ctx
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_WriteConfig(NULL, 0));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_SetCalibration(NULL, 100));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadBusVoltage_mV(NULL, &u16));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadShuntVoltage_uV(NULL, &i32));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadCurrent_uA(NULL, &i32));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadPower_mW(NULL, &u32));

    // Null output pointers
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadBusVoltage_mV(&ctx, NULL));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadShuntVoltage_uV(&ctx, NULL));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadCurrent_uA(&ctx, NULL));
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, INA219_ReadPower_mW(&ctx, NULL));
}

void test_api_uninitialized(void) {
    INA219_Status_t st;
    int32_t i32;
    uint16_t u16;
    uint32_t u32;

    memset(&ctx, 0, sizeof(ctx));  // ctx.initialized = false

    // write_u16 / read_u16 wrappers indirectly
    st = INA219_WriteConfig(&ctx, 0x1234);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);

    st = INA219_SetCalibration(&ctx, 100);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);

    st = INA219_ReadBusVoltage_mV(&ctx, &u16);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);

    st = INA219_ReadShuntVoltage_uV(&ctx, &i32);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);

    st = INA219_ReadCurrent_uA(&ctx, &i32);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);

    st = INA219_ReadPower_mW(&ctx, &u32);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);
}

/* Successful init and scale computation */
void test_init_success_and_scales(void) {
    INA219_Status_t st;

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;

    init.shunt_milliohm = 100u;
    init.calibration = 4096u;
    init.config = 0x1234u;

    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    TEST_ASSERT_TRUE(ctx.initialized);
    TEST_ASSERT_EQUAL_UINT8(0x40u, ctx.addr);
    TEST_ASSERT_EQUAL_UINT32(100u, ctx.shunt_milliohm);
    TEST_ASSERT_EQUAL_UINT16(4096u, ctx.calibration);

    TEST_ASSERT_EQUAL_HEX16(0x1234u, mock_read_be16(INA219_REG_CONFIG));
    TEST_ASSERT_EQUAL_HEX16(4096u, mock_read_be16(INA219_REG_CALIBRATION));

    TEST_ASSERT_TRUE(ctx.current_scale_uA > 0);
    TEST_ASSERT_TRUE(ctx.power_scale_mW > 0);
}

/* Init fails on I²C write errors */
void test_init_i2c_write_failure(void) {
    INA219_Status_t st;
    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    init.config = 0x5555;

    mock_i2c_fail_on_write = true;
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, st);
    TEST_ASSERT_FALSE(ctx.initialized);
    mock_i2c_fail_on_write = false;
}

void test_i2c_failures(void) {
    int32_t i32;
    uint16_t u16;
    uint32_t u32;

    // Initialize ctx normally
    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    // simulate read failure
    mock_i2c_fail_on_read = true;
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, INA219_ReadBusVoltage_mV(&ctx, &u16));
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, INA219_ReadShuntVoltage_uV(&ctx, &i32));
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, INA219_ReadCurrent_uA(&ctx, &i32));
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, INA219_ReadPower_mW(&ctx, &u32));
    mock_i2c_fail_on_read = false;

    // simulate write failure
    mock_i2c_fail_on_write = true;
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, INA219_WriteConfig(&ctx, 0x1111));
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, INA219_SetCalibration(&ctx, 1234));
    mock_i2c_fail_on_write = false;
}

/* Bus voltage reading and saturation */
void test_read_bus_voltage_mV(void) {
    INA219_Status_t st;
    uint16_t bus_mV;

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    init.config = INA219_CONFIG_DEFAULT;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    mock_write_be16(INA219_REG_BUS_VOLT, (uint16_t)(0x200 << 3));
    st = INA219_ReadBusVoltage_mV(&ctx, &bus_mV);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    TEST_ASSERT_EQUAL_UINT16(2048u, bus_mV);

    /* Saturation test: set raw register to 0xFFFF */
    mock_write_be16(INA219_REG_BUS_VOLT, 0xFFFF);
    st = INA219_ReadBusVoltage_mV(&ctx, &bus_mV);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);

    /* raw=0xFFFF -> measurement=(0xFFFF>>3)=0x1FFF -> mV=0x1FFF*4=32764 */
    TEST_ASSERT_EQUAL_UINT16(32764u, bus_mV);

    /* I2C failure */
    mock_i2c_fail_on_read = true;
    st = INA219_ReadBusVoltage_mV(&ctx, &bus_mV);
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, st);
    mock_i2c_fail_on_read = false;
}

/* Shunt voltage reading */
void test_read_shunt_voltage_uV(void) {
    INA219_Status_t st;
    int32_t shunt_uV;

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    mock_write_be16(INA219_REG_SHUNT_VOLT, (uint16_t)100);
    st = INA219_ReadShuntVoltage_uV(&ctx, &shunt_uV);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    TEST_ASSERT_EQUAL_INT32(1000, shunt_uV);

    mock_write_be16(INA219_REG_SHUNT_VOLT, (uint16_t)((int16_t)-50));
    st = INA219_ReadShuntVoltage_uV(&ctx, &shunt_uV);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    TEST_ASSERT_EQUAL_INT32(-500, shunt_uV);
}

/* Current and power reading */
void test_read_current_uA_and_power_mW(void) {
    INA219_Status_t st;
    int32_t current_uA;
    uint32_t power_mW;

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    mock_write_be16(INA219_REG_CURRENT, (uint16_t)123);
    st = INA219_ReadCurrent_uA(&ctx, &current_uA);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    TEST_ASSERT_EQUAL_INT32(123 * ctx.current_scale_uA, current_uA);

    mock_write_be16(INA219_REG_POWER, (uint16_t)50);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    st = INA219_ReadPower_mW(&ctx, &power_mW);
    TEST_ASSERT_EQUAL_UINT32(50 * ctx.power_scale_mW, power_mW);
}

/* WriteConfig */
void test_write_config_errors(void) {
    INA219_Status_t st;
    st = INA219_WriteConfig(NULL, 0x1234);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    st = INA219_WriteConfig(&ctx, 0xABCD);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);

    mock_i2c_fail_on_write = true;
    st = INA219_WriteConfig(&ctx, 0x1111);
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, st);
    mock_i2c_fail_on_write = false;
}

/* SetCalibration */
void test_set_calibration(void) {
    INA219_Status_t st;
    st = INA219_SetCalibration(NULL, 100);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    st = INA219_SetCalibration(&ctx, 2000);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);
    TEST_ASSERT_EQUAL_UINT16(2000u, ctx.calibration);
    TEST_ASSERT_TRUE(ctx.current_scale_uA > 0);
    TEST_ASSERT_TRUE(ctx.power_scale_mW > 0);

    st = INA219_SetCalibration(&ctx, 0);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    mock_i2c_fail_on_write = true;
    st = INA219_SetCalibration(&ctx, 3000);
    TEST_ASSERT_NOT_EQUAL(INA219_OK, st);
    mock_i2c_fail_on_write = false;
}

void test_measurement_i2c_failures(void) {
    INA219_Status_t st;
    int32_t current;
    int32_t shunt;
    uint32_t power;

    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 100;
    init.calibration = 4096;
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    /* simulate I2C read failures */
    mock_i2c_fail_on_read = true;

    st = INA219_ReadShuntVoltage_uV(&ctx, &shunt);
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, st);

    st = INA219_ReadCurrent_uA(&ctx, &current);
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, st);

    st = INA219_ReadPower_mW(&ctx, &power);
    TEST_ASSERT_EQUAL_INT(INA219_E_IO, st);

    mock_i2c_fail_on_read = false;

    /* simulate uninitialized ctx */
    ctx.initialized = false;
    st = INA219_ReadCurrent_uA(&ctx, &current);
    TEST_ASSERT_EQUAL_INT(INA219_E_STATE, st);
}

void test_scale_edge_cases(void) {
    INA219_Status_t st;

    // zero denominator via shunt_milliohm
    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_address = 0x40;

    ctx.calibration = 4096;
    ctx.shunt_milliohm = 0;  // zero denominator
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    // zero denominator via calibration
    ctx.calibration = 0;
    ctx.shunt_milliohm = 100;
    st = INA219_Init(&ctx, &init);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    // force scales to zero by using large values to overflow current_scale_uA
    ctx.calibration = 1;
    ctx.shunt_milliohm = 1;
    st = INA219_Init(&ctx, &init);
    ctx.calibration = 0;  // zero cal will produce scale=0
    ctx.current_scale_uA = 0;
    ctx.power_scale_mW = 0;
    ctx.i2c_write = mock_i2c_write;
    ctx.initialized = true;

    st = INA219_SetCalibration(&ctx, 0);  // zero cal triggers INA219_E_PARAM
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);
}

void test_calibration_edge_cases(void) {
    INA219_Status_t st;

    // Normal initialization
    init.i2c_read = mock_i2c_read;
    init.i2c_write = mock_i2c_write;
    init.i2c_user = NULL;
    init.i2c_address = 0x40;
    init.shunt_milliohm = 1;  // small to trigger scale issues
    init.calibration = 1;     // minimal calibration
    TEST_ASSERT_EQUAL_INT(INA219_OK, INA219_Init(&ctx, &init));

    // Calibration below minimum
    st = INA219_SetCalibration(&ctx, INA219_CAL_MIN - 1);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);

    // Calibration exactly at minimum (should succeed)
    st = INA219_SetCalibration(&ctx, INA219_CAL_MIN);
    TEST_ASSERT_EQUAL_INT(INA219_OK, st);

    // Force zero scale by setting calibration that would overflow compute_current_scale_uA
    ctx.calibration = 1;
    ctx.shunt_milliohm = 0xFFFFFFFF;  // unrealistically large
    st = INA219_SetCalibration(&ctx, 1);
    TEST_ASSERT_EQUAL_INT(INA219_E_PARAM, st);
}

/* --- main --- */
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_param_invalid);
    RUN_TEST(test_null_checks);
    RUN_TEST(test_api_uninitialized);
    RUN_TEST(test_init_success_and_scales);
    RUN_TEST(test_init_i2c_write_failure);
    RUN_TEST(test_i2c_failures);
    RUN_TEST(test_read_bus_voltage_mV);
    RUN_TEST(test_read_shunt_voltage_uV);
    RUN_TEST(test_read_current_uA_and_power_mW);
    RUN_TEST(test_write_config_errors);
    RUN_TEST(test_set_calibration);
    RUN_TEST(test_measurement_i2c_failures);
    RUN_TEST(test_scale_edge_cases);
    RUN_TEST(test_calibration_edge_cases);
    return UNITY_END();
}
