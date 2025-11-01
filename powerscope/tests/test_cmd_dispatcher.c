#include <string.h>
#include <unity.h>

#include "ps_cmd_defs.h"
#include "ps_cmd_dispatcher.h"
#include "ps_cmd_parsers.h"  // use the real parsers
#include "ps_config.h"

/* ---------- Fixtures ---------- */
static ps_cmd_dispatcher_t dispatcher;

/* Tracking flags for handler calls */
static bool start_called;
static bool stop_called;
static bool set_period_called;
static uint16_t set_period_value;

/* ---------- Handlers ---------- */
static bool handle_start(const void* cmd_struct) {
    (void)cmd_struct;
    start_called = true;
    return true;
}

static bool handle_stop(const void* cmd_struct) {
    (void)cmd_struct;
    stop_called = true;
    return true;
}

static bool handle_set_period(const void* cmd_struct) {
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
}

void tearDown(void) {}

/* ---------- Tests ---------- */

/* Normal dispatch tests */
void test_dispatch_start(void) {
    bool handled = dispatcher.dispatch(&dispatcher, CMD_START, NULL, 0);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(start_called);
}

void test_dispatch_stop(void) {
    bool handled = dispatcher.dispatch(&dispatcher, CMD_STOP, NULL, 0);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(stop_called);
}

void test_dispatch_set_period_valid(void) {
    cmd_set_period_t cmd = {.period_ms = PS_STREAM_PERIOD_MIN_MS + 10};
    uint8_t payload[] = {(uint8_t)(cmd.period_ms & 0xFF), (uint8_t)(cmd.period_ms >> 8)};

    bool handled = dispatcher.dispatch(&dispatcher, CMD_SET_PERIOD, payload, sizeof(payload));
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(set_period_called);
    TEST_ASSERT_EQUAL_UINT16(cmd.period_ms, set_period_value);
}

void test_dispatch_set_period_too_short(void) {
    uint8_t payload[] = {0x12};

    bool handled = dispatcher.dispatch(&dispatcher, CMD_SET_PERIOD, payload, sizeof(payload));
    TEST_ASSERT_FALSE(handled);
    TEST_ASSERT_FALSE(set_period_called);
}

void test_dispatch_unknown_command(void) {
    bool handled = dispatcher.dispatch(&dispatcher, 0xFF, NULL, 0);
    TEST_ASSERT_FALSE(handled);
}

/* ---------- NULL pointers tests ---------- */
void test_ps_cmds_init_null(void) {
    ps_cmds_init(NULL);  // safely return
    TEST_PASS();
}

void test_ps_cmd_register_handler_null(void) {
    ps_cmd_register_handler(NULL, 0x01, ps_parse_noarg, handle_start);  // safely return
    TEST_PASS();
}

void test_dispatch_null_dispatcher(void) {
    bool handled = ps_cmd_dispatcher_dispatch_hdr(NULL, CMD_START, NULL, 0);
    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_null_handler(void) {
    dispatcher.table[2].parser = ps_parse_noarg;
    dispatcher.table[2].handler = NULL;
    bool handled = dispatcher.dispatch(&dispatcher, 2, NULL, 0);
    TEST_ASSERT_FALSE(handled);
}

void test_dispatch_null_parser(void) {
    dispatcher.table[3].parser = NULL;
    dispatcher.table[3].handler = handle_start;
    bool handled = dispatcher.dispatch(&dispatcher, 3, NULL, 0);
    TEST_ASSERT_FALSE(handled);
}

/* ---------- Main ---------- */
int main(void) {
    UNITY_BEGIN();

    /* dispatch tests */
    RUN_TEST(test_dispatch_start);
    RUN_TEST(test_dispatch_stop);
    RUN_TEST(test_dispatch_set_period_valid);
    RUN_TEST(test_dispatch_set_period_too_short);
    RUN_TEST(test_dispatch_unknown_command);

    /* NULL/edge branches */
    RUN_TEST(test_ps_cmds_init_null);
    RUN_TEST(test_ps_cmd_register_handler_null);
    RUN_TEST(test_dispatch_null_dispatcher);
    RUN_TEST(test_dispatch_null_handler);
    RUN_TEST(test_dispatch_null_parser);

    return UNITY_END();
}
