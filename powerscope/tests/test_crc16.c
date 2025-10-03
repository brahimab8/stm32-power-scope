/**
 * @file    test_crc16.c
 * @brief   Unit tests for CRC-16/CCITT-FALSE (little-endian) in ps_crc16.h.
 *
 * @note    The expected CRC values in these tests were calculated using the online reference
 *          implementation and test vectors from:
 *          https://www.sunshine2k.de/coding/javascript/crc/crc_js.html
 */

#include "ps_crc16.h"
#include "unity.h"

/* --- Setup/teardown --- */
void setUp(void) {}
void tearDown(void) {}

/* --- Known vector --- */
void test_crc16_known_vector(void) {
    const uint8_t data[] = {0x01, 0x02, 0x03, 0x04};
    uint16_t crc = ps_crc16_le(data, sizeof(data), PS_CRC16_INIT);
    // Precomputed CRC-16/CCITT-FALSE for {0x01,0x02,0x03,0x04} = 0x89C3
    TEST_ASSERT_EQUAL_UINT16(0x89C3, crc);
}

/* --- Empty buffer --- */
void test_crc16_empty_buffer(void) {
    uint16_t crc = ps_crc16_le(NULL, 0, PS_CRC16_INIT);
    // CRC of empty buffer should equal initial seed
    TEST_ASSERT_EQUAL_UINT16(PS_CRC16_INIT, crc);
}

/* --- Incremental / accumulate --- */
void test_crc16_accumulate(void) {
    const uint8_t part1[] = {0x10, 0x20};
    const uint8_t part2[] = {0x30, 0x40};
    uint16_t crc = ps_crc16_le(part1, sizeof(part1), PS_CRC16_INIT);
    crc = ps_crc16_le(part2, sizeof(part2), crc);
    // Precomputed CRC-16/CCITT-FALSE for {0x10,0x20,0x30,0x40} = 0x54F0
    TEST_ASSERT_EQUAL_UINT16(0x54F0, crc);
}

/* --- One-byte buffers --- */
void test_crc16_one_byte(void) {
    const uint8_t b = 0xFF;
    uint16_t crc = ps_crc16_le(&b, 1, PS_CRC16_INIT);
    // Precomputed CRC-16/CCITT-FALSE for {0xFF} = 0xFF00
    TEST_ASSERT_EQUAL_UINT16(0xFF00, crc);
}

/* --- Main --- */
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_crc16_known_vector);
    RUN_TEST(test_crc16_empty_buffer);
    RUN_TEST(test_crc16_accumulate);
    RUN_TEST(test_crc16_one_byte);
    return UNITY_END();
}
