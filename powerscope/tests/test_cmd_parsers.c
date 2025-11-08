/**
 * @file    test_cmd_parsers.c
 * @brief   Unit tests for ps_cmd_parsers.c
 */

#include <string.h>
#include <unity.h>

#include "ps_cmd_defs.h"
#include "ps_cmd_parsers.h"

/* ---------- Test structs ---------- */
static cmd_set_period_t set_period;
static uint8_t sensor_id;

/* ---------- Setup / Teardown ---------- */
void setUp(void) {
    memset(&set_period, 0xAA, sizeof(set_period));
    sensor_id = 0xAA;
}

void tearDown(void) {}

/* ---------- Tests ---------- */

void test_parse_noarg_valid(void) {
    bool ok = ps_parse_noarg(NULL, 0, NULL, 0);
    TEST_ASSERT_TRUE(ok);
}

void test_parse_noarg_invalid_len(void) {
    uint8_t payload[] = {0x01};
    bool ok = ps_parse_noarg(payload, sizeof(payload), NULL, 0);
    TEST_ASSERT_FALSE(ok);
}

/* ---------- ps_parse_set_period ---------- */

void test_parse_set_period_valid(void) {
    uint8_t payload[] = {
        0x05,       // sensor_id
        0x34, 0x12  // period_ms = 0x1234 (LE)
    };

    bool ok = ps_parse_set_period(payload, sizeof(payload), &set_period, sizeof(set_period));

    TEST_ASSERT_TRUE(ok);
    TEST_ASSERT_EQUAL_UINT8(0x05, set_period.sensor_id);
    TEST_ASSERT_EQUAL_UINT16(0x1234, set_period.period_ms);
}

void test_parse_set_period_too_short(void) {
    uint8_t payload[] = {
        0x01, 0x34  // missing MSB of period
    };

    bool ok = ps_parse_set_period(payload, sizeof(payload), &set_period, sizeof(set_period));

    TEST_ASSERT_FALSE(ok);
}

void test_parse_set_period_null_out(void) {
    uint8_t payload[] = {0x01, 0x34, 0x12};

    bool ok = ps_parse_set_period(payload, sizeof(payload), NULL, sizeof(set_period));

    TEST_ASSERT_FALSE(ok);
}

void test_parse_set_period_small_out_buffer(void) {
    uint8_t payload[] = {0x01, 0x34, 0x12};

    bool ok = ps_parse_set_period(payload, sizeof(payload), &set_period,
                                  sizeof(uint8_t));  // too small

    TEST_ASSERT_FALSE(ok);
}

/* ---------- ps_parse_sensor_id ---------- */

void test_parse_sensor_id_valid(void) {
    uint8_t payload[] = {0x09};

    bool ok = ps_parse_sensor_id(payload, sizeof(payload), &sensor_id, sizeof(sensor_id));

    TEST_ASSERT_TRUE(ok);
    TEST_ASSERT_EQUAL_UINT8(0x09, sensor_id);
}

void test_parse_sensor_id_too_short(void) {
    bool ok = ps_parse_sensor_id(NULL, 0, &sensor_id, sizeof(sensor_id));
    TEST_ASSERT_FALSE(ok);
}

void test_parse_sensor_id_null_out(void) {
    uint8_t payload[] = {0x01};

    bool ok = ps_parse_sensor_id(payload, sizeof(payload), NULL, sizeof(sensor_id));

    TEST_ASSERT_FALSE(ok);
}

void test_parse_sensor_id_small_out_buffer(void) {
    uint8_t payload[] = {0x01};

    bool ok = ps_parse_sensor_id(payload, sizeof(payload), &sensor_id,
                                 0);  // too small

    TEST_ASSERT_FALSE(ok);
}

/* ---------- Main ---------- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_parse_noarg_valid);
    RUN_TEST(test_parse_noarg_invalid_len);

    RUN_TEST(test_parse_set_period_valid);
    RUN_TEST(test_parse_set_period_too_short);
    RUN_TEST(test_parse_set_period_null_out);
    RUN_TEST(test_parse_set_period_small_out_buffer);

    RUN_TEST(test_parse_sensor_id_valid);
    RUN_TEST(test_parse_sensor_id_too_short);
    RUN_TEST(test_parse_sensor_id_null_out);
    RUN_TEST(test_parse_sensor_id_small_out_buffer);

    return UNITY_END();
}
