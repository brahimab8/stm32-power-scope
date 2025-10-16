/**
 * @file    test_ps_cmd_dispatcher.c
 * @brief   Unit tests for ps_cmd_dispatcher using Unity
 */
#include <string.h>
#include <unity.h>

#include "ps_cmd_dispatcher.h"
#include "ps_config.h"  // for PS_STREAM_PERIOD_MIN_MS / MAX_MS

/* ---------- Fixtures ---------- */
static ps_cmds_t cmds;

void setUp(void) {
    memset(&cmds, 0xAA, sizeof(cmds));  // Fill with dummy to detect init
}

void tearDown(void) {}

/* ---------- Tests ---------- */

void test_cmds_init_clears_all(void) {
    ps_cmds_init(&cmds);
    TEST_ASSERT_FALSE(cmds.start_stop.requested);
    TEST_ASSERT_FALSE(cmds.start_stop.start);
    TEST_ASSERT_FALSE(cmds.set_period.requested);
    TEST_ASSERT_EQUAL_UINT16(0, cmds.set_period.period_ms);
}

void test_dispatch_start_command_sets_requested_and_start(void) {
    uint8_t payload[] = {CMD_START};
    ps_cmds_init(&cmds);

    bool handled = ps_cmd_dispatch(payload, sizeof(payload), &cmds);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(cmds.start_stop.requested);
    TEST_ASSERT_TRUE(cmds.start_stop.start);
}

void test_dispatch_stop_command_sets_requested_and_stop(void) {
    uint8_t payload[] = {CMD_STOP};
    ps_cmds_init(&cmds);

    bool handled = ps_cmd_dispatch(payload, sizeof(payload), &cmds);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(cmds.start_stop.requested);
    TEST_ASSERT_FALSE(cmds.start_stop.start);
}

void test_dispatch_set_period_valid_value_sets_requested_and_period(void) {
    uint16_t period = PS_STREAM_PERIOD_MIN_MS + 10;
    uint8_t payload[] = {CMD_SET_PERIOD, (uint8_t)(period & 0xFF), (uint8_t)(period >> 8)};
    ps_cmds_init(&cmds);

    bool handled = ps_cmd_dispatch(payload, sizeof(payload), &cmds);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(cmds.set_period.requested);
    TEST_ASSERT_EQUAL_UINT16(period, cmds.set_period.period_ms);
}

void test_dispatch_set_period_out_of_bounds_ignored(void) {
    uint16_t period = PS_STREAM_PERIOD_MAX_MS + 1;
    uint8_t payload[] = {CMD_SET_PERIOD, (uint8_t)(period & 0xFF), (uint8_t)(period >> 8)};
    ps_cmds_init(&cmds);

    bool handled = ps_cmd_dispatch(payload, sizeof(payload), &cmds);

    TEST_ASSERT_FALSE(handled);
    TEST_ASSERT_FALSE(cmds.set_period.requested);
}

void test_dispatch_unknown_command_returns_false(void) {
    uint8_t payload[] = {0xFF};
    ps_cmds_init(&cmds);

    bool handled = ps_cmd_dispatch(payload, sizeof(payload), &cmds);

    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_multiple_commands(void) {
    uint16_t period = PS_STREAM_PERIOD_MIN_MS + 5;
    uint8_t payload[] = {CMD_START, CMD_SET_PERIOD, (uint8_t)(period & 0xFF),
                         (uint8_t)(period >> 8)};
    ps_cmds_init(&cmds);

    bool handled = ps_cmd_dispatch(payload, sizeof(payload), &cmds);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(cmds.start_stop.requested);
    TEST_ASSERT_TRUE(cmds.start_stop.start);
    TEST_ASSERT_TRUE(cmds.set_period.requested);
    TEST_ASSERT_EQUAL_UINT16(period, cmds.set_period.period_ms);
}

/* ---------- Main ---------- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_cmds_init_clears_all);
    RUN_TEST(test_dispatch_start_command_sets_requested_and_start);
    RUN_TEST(test_dispatch_stop_command_sets_requested_and_stop);
    RUN_TEST(test_dispatch_set_period_valid_value_sets_requested_and_period);
    RUN_TEST(test_dispatch_set_period_out_of_bounds_ignored);
    RUN_TEST(test_dispatch_unknown_command_returns_false);
    RUN_TEST(test_dispatch_multiple_commands);

    return UNITY_END();
}
