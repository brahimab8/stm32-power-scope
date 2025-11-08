/**
 * @file    test_cmd_dispatcher.c
 * @brief   Unit tests for ps_cmd_dispatcher.c
 */

#include <string.h>
#include <unity.h>

#include "ps_cmd_defs.h"
#include "ps_cmd_dispatcher.h"
#include "ps_cmd_parsers.h"
#include "ps_config.h"

/* ---------- Fixtures ---------- */
static ps_cmd_dispatcher_t dispatcher;

/* Tracking flags */
static bool start_called;
static bool stop_called;
static bool set_period_called;
static uint16_t set_period_value;

/* Response buffer */
static uint8_t resp_buf[16];
static uint16_t resp_len;

/* ---------- Helpers ---------- */
static void reset_resp(void) {
    memset(resp_buf, 0, sizeof(resp_buf));
    resp_len = sizeof(resp_buf);  // IMPORTANT: capacity must be reset
}

/* ---------- Handlers ---------- */
static bool handle_start(const void* cmd_struct, uint8_t* out_buf, uint16_t* out_len) {
    (void)cmd_struct;
    (void)out_buf;
    (void)out_len;
    start_called = true;
    return true;
}

static bool handle_stop(const void* cmd_struct, uint8_t* out_buf, uint16_t* out_len) {
    (void)cmd_struct;
    (void)out_buf;
    (void)out_len;
    stop_called = true;
    return true;
}

static bool handle_set_period(const void* cmd_struct, uint8_t* out_buf, uint16_t* out_len) {
    (void)out_buf;
    (void)out_len;
    const cmd_set_period_t* cmd = (const cmd_set_period_t*)cmd_struct;
    set_period_called = true;
    set_period_value = cmd->period_ms;
    return true;
}

/* ---------- Unity setup/teardown ---------- */
void setUp(void) {
    ps_cmds_init(&dispatcher);

    start_called = false;
    stop_called = false;
    set_period_called = false;
    set_period_value = 0;

    ps_cmd_register_handler(&dispatcher, CMD_START, ps_parse_noarg, handle_start);
    ps_cmd_register_handler(&dispatcher, CMD_STOP, ps_parse_noarg, handle_stop);
    ps_cmd_register_handler(&dispatcher, CMD_SET_PERIOD, ps_parse_set_period, handle_set_period);

    reset_resp();
}

void tearDown(void) {}

/* ---------- Tests ---------- */

void test_dispatch_start(void) {
    reset_resp();

    bool handled = dispatcher.dispatch(&dispatcher, CMD_START, NULL, 0, resp_buf, &resp_len);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(start_called);
}

void test_dispatch_stop(void) {
    reset_resp();

    bool handled = dispatcher.dispatch(&dispatcher, CMD_STOP, NULL, 0, resp_buf, &resp_len);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(stop_called);
}

void test_dispatch_set_period_valid(void) {
    reset_resp();

    uint8_t sensor_id = 0x01;
    uint16_t period = PS_STREAM_PERIOD_MIN_MS + 10;
    uint8_t payload[] = {sensor_id, (uint8_t)(period & 0xFF), (uint8_t)(period >> 8)};

    bool handled = dispatcher.dispatch(&dispatcher, CMD_SET_PERIOD, payload, sizeof(payload),
                                       resp_buf, &resp_len);

    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(set_period_called);
    TEST_ASSERT_EQUAL_UINT16(period, set_period_value);
}

void test_dispatch_set_period_too_short(void) {
    reset_resp();

    uint8_t payload[] = {0x12};

    bool handled = dispatcher.dispatch(&dispatcher, CMD_SET_PERIOD, payload, sizeof(payload),
                                       resp_buf, &resp_len);

    TEST_ASSERT_FALSE(handled);
    TEST_ASSERT_FALSE(set_period_called);
}

void test_dispatch_unknown_command(void) {
    reset_resp();

    bool handled = dispatcher.dispatch(&dispatcher, 0xFF, NULL, 0, resp_buf, &resp_len);

    TEST_ASSERT_FALSE(handled);
}

/* ---------- NULL / edge cases ---------- */

void test_ps_cmds_init_null(void) {
    ps_cmds_init(NULL);
    TEST_PASS();
}

void test_ps_cmd_register_handler_null(void) {
    ps_cmd_register_handler(NULL, 0x01, ps_parse_noarg, handle_start);
    TEST_PASS();
}

void test_dispatch_null_dispatcher(void) {
    reset_resp();

    bool handled = ps_cmd_dispatcher_dispatch_resp(NULL, CMD_START, NULL, 0, resp_buf, &resp_len);

    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_null_respbuf(void) {
    reset_resp();

    bool handled = dispatcher.dispatch(&dispatcher, CMD_START, NULL, 0, NULL, &resp_len);

    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_null_resplen(void) {
    reset_resp();

    bool handled = dispatcher.dispatch(&dispatcher, CMD_START, NULL, 0, resp_buf, NULL);

    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_null_handler(void) {
    reset_resp();

    dispatcher.table[2].parser = ps_parse_noarg;
    dispatcher.table[2].handler = NULL;

    bool handled = dispatcher.dispatch(&dispatcher, 2, NULL, 0, resp_buf, &resp_len);

    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_null_parser(void) {
    reset_resp();

    dispatcher.table[3].parser = NULL;
    dispatcher.table[3].handler = handle_start;

    bool handled = dispatcher.dispatch(&dispatcher, 3, NULL, 0, resp_buf, &resp_len);

    TEST_ASSERT_FALSE(handled);
}

/* ---------- Main ---------- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_dispatch_start);
    RUN_TEST(test_dispatch_stop);
    RUN_TEST(test_dispatch_set_period_valid);
    RUN_TEST(test_dispatch_set_period_too_short);
    RUN_TEST(test_dispatch_unknown_command);

    RUN_TEST(test_ps_cmds_init_null);
    RUN_TEST(test_ps_cmd_register_handler_null);
    RUN_TEST(test_dispatch_null_dispatcher);
    RUN_TEST(test_dispatch_null_respbuf);
    RUN_TEST(test_dispatch_null_resplen);
    RUN_TEST(test_dispatch_null_handler);
    RUN_TEST(test_dispatch_null_parser);

    return UNITY_END();
}
