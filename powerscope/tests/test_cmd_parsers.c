#include <string.h>
#include <unity.h>

#include "ps_cmd_defs.h"
#include "ps_cmd_parsers.h"

/* ---------- Test structs ---------- */
static cmd_set_period_t set_period;

/* ---------- Setup/Teardown ---------- */
void setUp(void) {
    memset(&set_period, 0xAA, sizeof(set_period));
}

void tearDown(void) {}

/* ---------- Tests ---------- */

void test_parse_noarg_valid(void) {
    uint8_t* payload = NULL;
    bool ok = ps_parse_noarg(payload, 0, NULL, 0);
    TEST_ASSERT_TRUE(ok);
}

void test_parse_noarg_invalid_len(void) {
    uint8_t payload[] = {0x01};
    bool ok = ps_parse_noarg(payload, 1, NULL, 0);
    TEST_ASSERT_FALSE(ok);
}

void test_parse_set_period_valid(void) {
    uint8_t payload[] = {0x34, 0x12};  // 0x1234 little-endian
    bool ok = ps_parse_set_period(payload, 2, &set_period, sizeof(set_period));
    TEST_ASSERT_TRUE(ok);
    TEST_ASSERT_EQUAL_UINT16(0x1234, set_period.period_ms);
}

void test_parse_set_period_too_short(void) {
    uint8_t payload[] = {0x34};
    bool ok = ps_parse_set_period(payload, 1, &set_period, sizeof(set_period));
    TEST_ASSERT_FALSE(ok);
}

/* ---------- Main ---------- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_parse_noarg_valid);
    RUN_TEST(test_parse_noarg_invalid_len);

    RUN_TEST(test_parse_set_period_valid);
    RUN_TEST(test_parse_set_period_too_short);

    return UNITY_END();
}
