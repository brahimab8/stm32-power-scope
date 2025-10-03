/**
 * @file    test_byteio.c
 * @brief   Unit tests for byteio.h helpers.
 */

#include <string.h>

#include "byteio.h"
#include "unity.h"

/* ---------- Setup/teardown ---------- */
void setUp(void) {}
void tearDown(void) {}

/* ---------- Tests ---------- */

void test_wr_u16le(void) {
    uint8_t buf[2] = {0xAA, 0xBB};
    byteio_wr_u16le(buf, 0x1234);
    TEST_ASSERT_EQUAL_HEX8(0x34, buf[0]);
    TEST_ASSERT_EQUAL_HEX8(0x12, buf[1]);
}

void test_wr_u32le(void) {
    uint8_t buf[4];
    byteio_wr_u32le(buf, 0x89ABCDEFu);
    TEST_ASSERT_EQUAL_HEX8(0xEF, buf[0]);
    TEST_ASSERT_EQUAL_HEX8(0xCD, buf[1]);
    TEST_ASSERT_EQUAL_HEX8(0xAB, buf[2]);
    TEST_ASSERT_EQUAL_HEX8(0x89, buf[3]);
}

void test_wr_i32le_positive(void) {
    uint8_t buf[4];
    byteio_wr_i32le(buf, 0x12345678);
    TEST_ASSERT_EQUAL_HEX8(0x78, buf[0]);
    TEST_ASSERT_EQUAL_HEX8(0x56, buf[1]);
    TEST_ASSERT_EQUAL_HEX8(0x34, buf[2]);
    TEST_ASSERT_EQUAL_HEX8(0x12, buf[3]);
}

void test_wr_i32le_negative(void) {
    uint8_t buf[4];
    int32_t v = -2; /* 0xFFFFFFFE in two’s complement */
    byteio_wr_i32le(buf, v);
    TEST_ASSERT_EQUAL_HEX8(0xFE, buf[0]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, buf[1]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, buf[2]);
    TEST_ASSERT_EQUAL_HEX8(0xFF, buf[3]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_wr_u16le);
    RUN_TEST(test_wr_u32le);
    RUN_TEST(test_wr_i32le_positive);
    RUN_TEST(test_wr_i32le_negative);
    return UNITY_END();
}