/**
 * @file    test_ps_core.c
 * @brief   Black-box Unity tests for ps_core using public API.
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "protocol_defs.h"
#include "ps_buffer_if.h"
#include "ps_core.h"
#include "ps_sensor_adapter.h"
#include "unity.h"

/* ---------------------------
 * TX stubs & capture variables
 * --------------------------- */
static uint8_t last_hdr_type;
static uint32_t last_hdr_seq;
static uint32_t last_hdr_ts;
static uint8_t last_stream_payload[PROTO_MAX_PAYLOAD];
static uint16_t last_stream_len;
static int ps_tx_pump_calls;

void ps_tx_send_hdr(struct ps_tx_ctx_t* ctx, uint8_t type, uint32_t seq, uint32_t ts) {
    (void)ctx;
    last_hdr_type = type;
    last_hdr_seq = seq;
    last_hdr_ts = ts;
}

void ps_tx_send_stream(struct ps_tx_ctx_t* ctx, const uint8_t* payload, uint16_t len,
                       uint32_t now) {
    (void)ctx;
    (void)now;
    if (len > sizeof(last_stream_payload)) len = sizeof(last_stream_payload);
    memcpy(last_stream_payload, payload, len);
    last_stream_len = len;
}

void ps_tx_pump(struct ps_tx_ctx_t* ctx) {
    (void)ctx;
    ps_tx_pump_calls++;
}

/* ---------------------------
 * proto_parse_frame stub (configurable)
 * --------------------------- */
static bool parse_returns_frame = false;
static proto_hdr_t parse_hdr_out;
static const uint8_t* parse_payload_out = NULL;
static uint16_t parse_payload_len_out = 0;
static size_t parse_frame_len_out = 0;

size_t proto_parse_frame(const uint8_t* data, size_t data_len, proto_hdr_t* hdr,
                         const uint8_t** payload, uint16_t* payload_len) {
    (void)data;
    (void)data_len;
    if (!parse_returns_frame) return 0;
    if (hdr) *hdr = parse_hdr_out;
    if (payload) *payload = parse_payload_out;
    if (payload_len) *payload_len = parse_payload_len_out;
    return parse_frame_len_out;
}

/* ---------------------------
 * Linear buffer mock
 * --------------------------- */
#define FB_CAP 2048
typedef struct {
    uint8_t buf[FB_CAP];
    uint16_t rd, wr;
} fake_buf_t;

static uint16_t fb_size(void* ctx) {
    return ((fake_buf_t*)ctx)->wr - ((fake_buf_t*)ctx)->rd;
}
static uint16_t fb_space(void* ctx) {
    (void)ctx;
    return FB_CAP;
}
static uint16_t fb_capacity(void* ctx) {
    (void)ctx;
    return FB_CAP;
}
static void fb_clear(void* ctx) {
    ((fake_buf_t*)ctx)->rd = ((fake_buf_t*)ctx)->wr = 0;
}

static bool fb_append(void* ctx, const uint8_t* src, uint16_t len) {
    fake_buf_t* b = (fake_buf_t*)ctx;
    uint16_t free_space = FB_CAP - b->wr;
    if (len > free_space) len = free_space;
    if (!len) return false;
    memcpy(&b->buf[b->wr], src, len);
    b->wr += len;
    return true;
}

static void fb_pop(void* ctx, uint16_t len) {
    fake_buf_t* b = (fake_buf_t*)ctx;
    if (len > fb_size(ctx)) len = fb_size(ctx);
    b->rd += len;
}

static void fb_copy(void* ctx, void* dst, uint16_t len) {
    fake_buf_t* b = (fake_buf_t*)ctx;
    if (len > fb_size(ctx)) len = fb_size(ctx);
    memcpy(dst, &b->buf[b->rd], len);
}

static uint16_t fb_peek_contiguous(void* ctx, const uint8_t** out) {
    fake_buf_t* b = (fake_buf_t*)ctx;
    if (b->wr == b->rd) {
        *out = NULL;
        return 0;
    }
    *out = &b->buf[b->rd];
    return b->wr - b->rd;
}

static void fb_reset(fake_buf_t* b) {
    b->rd = b->wr = 0;
}

static void make_fb_if(fake_buf_t* fb, ps_buffer_if_t* ifs) {
    ifs->ctx = fb;
    ifs->size = fb_size;
    ifs->space = fb_space;
    ifs->capacity = fb_capacity;
    ifs->clear = fb_clear;
    ifs->append = fb_append;
    ifs->pop = fb_pop;
    ifs->copy = fb_copy;
    ifs->peek_contiguous = fb_peek_contiguous;
}

/* ---------------------------
 * Sensors
 * --------------------------- */
static size_t sensor_fill_4(void* ctx, uint8_t* dst, size_t max_len) {
    (void)ctx;
    size_t n = max_len < 4 ? max_len : 4;
    for (size_t i = 0; i < n; i++) dst[i] = (uint8_t)(0x10 + i);
    return n;
}

static int sensor_start_ok(void* ctx) {
    (void)ctx;
    return CORE_SENSOR_READY;
}
static int sensor_poll_ok(void* ctx) {
    (void)ctx;
    return CORE_SENSOR_READY;
}

/* start=0 -> cooperative polling */
static int sensor_start_coop(void* ctx) {
    (void)ctx;
    return CORE_SENSOR_BUSY;
}
static int sensor_poll_coop_then_ready(void* ctx) {
    (void)ctx;
    return CORE_SENSOR_READY;
}
static ps_sensor_adapter_t sensor_coop = {.ctx = NULL,
                                          .fill = sensor_fill_4,
                                          .start = sensor_start_coop,
                                          .poll = sensor_poll_coop_then_ready,
                                          .sample_size = 4};

/* start=0 -> poll returns -1 -> error */
static int sensor_poll_err(void* ctx) {
    (void)ctx;
    return CORE_SENSOR_ERROR;
}
static ps_sensor_adapter_t sensor_coop_err = {.ctx = NULL,
                                              .fill = NULL,
                                              .start = sensor_start_coop,
                                              .poll = sensor_poll_err,
                                              .sample_size = 0};

/* fill returns 0 */
static size_t sensor_fill_empty(void* ctx, uint8_t* dst, size_t max_len) {
    (void)ctx;
    (void)dst;
    (void)max_len;
    return CORE_SENSOR_BUSY;
}
static ps_sensor_adapter_t sensor_empty = {.ctx = NULL,
                                           .fill = sensor_fill_empty,
                                           .start = sensor_start_ok,
                                           .poll = sensor_poll_ok,
                                           .sample_size = 0};
/* start<0 -> immediate error */
static int sensor_start_err(void* ctx) {
    (void)ctx;
    return CORE_SENSOR_ERROR;
}
static ps_sensor_adapter_t sensor_err = {
    .ctx = NULL, .fill = NULL, .start = sensor_start_err, .poll = NULL, .sample_size = 0};

/* ---------------------------
 * Fixtures & helpers
 * --------------------------- */
static ps_core_t core;
static fake_buf_t tx_fb, rx_fb;
static ps_buffer_if_t tx_if, rx_if;
static uint32_t now_val;
static uint32_t now_ms_stub(void) {
    return now_val;
}

/* advance ticks */
static void tick_n(ps_core_t* c, int n, uint32_t step_ms) {
    for (int i = 0; i < n; i++) {
        now_val += step_ms;
        ps_core_tick(c);
    }
}

/* inject frame using parse stub */
static void inject_frame(ps_core_t* c, uint8_t type, uint32_t seq, const uint8_t* payload,
                         uint16_t len) {
    parse_returns_frame = true;
    parse_hdr_out.type = type;
    parse_hdr_out.seq = seq;
    parse_payload_out = payload;
    parse_payload_len_out = len;
    parse_frame_len_out = PROTO_HDR_LEN + len + PROTO_CRC_LEN;

    uint8_t dummy[128] = {0};
    c->rx.iface->append(c->rx.iface->ctx, dummy, (uint16_t)parse_frame_len_out);
}

/* ---------------------------
 * Setup / teardown
 * --------------------------- */
void setUp(void) {
    memset(&core, 0, sizeof(core));
    ps_core_init(&core);

    fb_reset(&tx_fb);
    fb_reset(&rx_fb);
    make_fb_if(&tx_fb, &tx_if);
    make_fb_if(&rx_fb, &rx_if);
    ps_core_attach_buffers(&core, &tx_if, &rx_if);

    core.now_ms = now_ms_stub;
    core.tx.ctx = (struct ps_tx_ctx_t*)1;
    core.stream.max_payload = PROTO_MAX_PAYLOAD;
    core.stream.period_ms = 100;
    core.sensor_ready = 1;

    last_hdr_type = 0xFF;
    last_hdr_seq = 0;
    last_hdr_ts = 0;
    last_stream_len = 0;
    memset(last_stream_payload, 0, sizeof(last_stream_payload));
    ps_tx_pump_calls = 0;

    parse_returns_frame = false;
    parse_payload_out = NULL;
    parse_payload_len_out = 0;
    parse_frame_len_out = 0;
    parse_hdr_out.type = 0;
    parse_hdr_out.seq = 0;

    now_val = 0;
}

void tearDown(void) {}

/* ---------------------------
 * Tests
 * --------------------------- */

/* START command triggers streaming and sends ACK */
void test_when_start_cmd_received_then_streaming_requested_and_ack_sent(void) {
    static uint8_t payload[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x1111, payload, sizeof(payload));

    core.sensor_ready = 1;
    core.stream.sensor = &sensor_coop;
    core.stream.streaming = false;

    ps_core_tick(&core);

    TEST_ASSERT_EQUAL_UINT8(PROTO_TYPE_ACK, last_hdr_type);
    TEST_ASSERT_TRUE(core.stream.streaming);
}
/* STOP command clears streaming and sends ACK */
void test_when_stop_cmd_received_then_streaming_cleared_and_ack_sent(void) {
    // First, manually request streaming to simulate prior start
    core.stream.streaming = true;
    core.sensor_ready = 1;
    core.stream.sensor = &sensor_coop;

    static uint8_t payload[] = {CMD_STOP};
    inject_frame(&core, PROTO_TYPE_CMD, 0x2222, payload, sizeof(payload));

    ps_core_tick(&core);

    TEST_ASSERT_EQUAL_UINT8(PROTO_TYPE_ACK, last_hdr_type);
    TEST_ASSERT_FALSE(core.stream.streaming);
}

/* Unknown command triggers NACK */
void test_when_unknown_cmd_received_then_nack_sent(void) {
    static uint8_t payload[] = {0xFF};  // invalid opcode
    inject_frame(&core, PROTO_TYPE_CMD, 0x3333, payload, sizeof(payload));

    ps_core_tick(&core);

    TEST_ASSERT_EQUAL_UINT8(PROTO_TYPE_NACK, last_hdr_type);
}

/* Cooperative sensor: start->poll->ready->stream sent */
void test_when_sensor_coop_then_ready_and_stream_sent(void) {
    core.stream.sensor = &sensor_coop;
    core.sensor_ready = 1;

    // Inject START command to trigger streaming
    static uint8_t payload[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x4444, payload, sizeof(payload));

    core.stream.last_emit_ms = now_val - core.stream.period_ms - 1;

    tick_n(&core, 4, 1);

    TEST_ASSERT_EQUAL_INT(CORE_SM_IDLE, (int)core.sm);
    TEST_ASSERT_EQUAL_UINT16(4, last_stream_len);
    TEST_ASSERT_EQUAL_UINT8(0x10, last_stream_payload[0]);
    TEST_ASSERT_TRUE(core.stream.streaming);
}

/* Sensor start error -> ERROR -> recovery to IDLE */
void test_when_sensor_start_error_then_error_and_recover_to_idle(void) {
    core.stream.sensor = &sensor_err;
    core.sensor_ready = 1;

    // Inject START command to trigger streaming
    static uint8_t payload[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x5555, payload, sizeof(payload));

    core.stream.streaming = true;
    core.stream.last_emit_ms = now_val - core.stream.period_ms - 1;

    tick_n(&core, 3, 1);

    TEST_ASSERT_EQUAL_INT(CORE_SM_IDLE, (int)core.sm);
    TEST_ASSERT_FALSE(core.stream.streaming);  // streaming should remain false due to start error
}

/* SENSOR_POLL returns -1 -> ERROR -> recovery to IDLE */
void test_when_sensor_poll_returns_negative_then_error_and_recover_to_idle(void) {
    core.stream.sensor = &sensor_coop_err;
    core.sensor_ready = 1;

    // Inject START command to trigger streaming
    static uint8_t payload[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x6666, payload, sizeof(payload));

    core.stream.streaming = true;
    core.stream.last_emit_ms = now_val - core.stream.period_ms - 1;

    tick_n(&core, 4, 1);
    TEST_ASSERT_EQUAL_INT(CORE_SM_IDLE, (int)core.sm);
    TEST_ASSERT_FALSE(core.stream.streaming);  // streaming should remain false due to poll error
}

/* READY with empty fill() -> no stream sent */
void test_when_ready_and_fill_returns_zero_then_no_stream_sent(void) {
    core.stream.sensor = &sensor_empty;
    core.sensor_ready = 1;

    // Inject START command to trigger streaming
    static uint8_t payload[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x7777, payload, sizeof(payload));

    core.stream.last_emit_ms = now_val - core.stream.period_ms - 1;

    last_stream_len = 0;
    tick_n(&core, 2, 1);
    TEST_ASSERT_EQUAL_UINT16(0, last_stream_len);
    TEST_ASSERT_TRUE(core.stream.streaming);  // streaming requested, but no data sent
}

/* Null / invalid input tests */
void test_null_and_zero_inputs(void) {
    ps_core_tick(NULL);
    TEST_PASS();

    ps_core_t c = core;
    c.now_ms = NULL;
    ps_core_tick(&c);
    TEST_PASS();

    ps_core_on_rx(&core, NULL, 0);                 // null data / zero length
    TEST_ASSERT_EQUAL_UINT16(0, fb_size(&rx_fb));  // nothing appended
}

/* RX processing: parse returns 0 -> pop(1) */
void test_rx_parse_returns_zero_pops_one(void) {
    fb_reset(&rx_fb);  // ensure empty buffer
    parse_returns_frame = false;

    ps_core_tick(&core);

    // size should remain 0, not underflow
    TEST_ASSERT_EQUAL_UINT16(0, fb_size(&rx_fb));
}

/* RX processing: non-CMD frame */
void test_rx_non_cmd_frame_does_not_call_handle_cmd(void) {
    static uint8_t payload[] = {0x12};
    inject_frame(&core, PROTO_TYPE_ACK, 0x1234, payload, sizeof(payload));
    core.stream.sensor = &sensor_coop;
    core.sensor_ready = 1;
    core.stream.streaming = true;
    ps_core_tick(&core);

    TEST_ASSERT_TRUE(core.stream.streaming);  // streaming not affected by ACK
}

/* update_streaming_state: streaming not enabled if one condition false */
void test_update_streaming_state_false_combinations(void) {
    core.sensor_ready = 0;
    core.stream.sensor = &sensor_coop;

    // Inject START command
    static uint8_t payload1[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x8888, payload1, sizeof(payload1));
    ps_core_tick(&core);
    TEST_ASSERT_FALSE(core.stream.streaming);

    core.sensor_ready = 1;
    core.stream.sensor = &sensor_coop;

    // No START command injected
    ps_core_tick(&core);
    TEST_ASSERT_FALSE(core.stream.streaming);

    core.sensor_ready = 1;
    core.stream.sensor = NULL;

    // Inject START command
    static uint8_t payload2[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0x9999, payload2, sizeof(payload2));
    ps_core_tick(&core);
    TEST_ASSERT_FALSE(core.stream.streaming);
}

/* sm_handle_idle: not ready yet */
void test_idle_not_ready_yet(void) {
    core.stream.sensor = &sensor_coop;
    core.sensor_ready = 1;

    // Inject START command
    static uint8_t payload[] = {CMD_START};
    inject_frame(&core, PROTO_TYPE_CMD, 0xAAAA, payload, sizeof(payload));

    core.stream.last_emit_ms = now_val;
    tick_n(&core, 1, 10);

    TEST_ASSERT_EQUAL_INT(CORE_SM_IDLE, (int)core.sm);
    TEST_ASSERT_TRUE(core.stream.streaming);
}

/* tick calls ps_tx_pump when tx.ctx != NULL */
void test_ps_tx_pump_called(void) {
    ps_tx_pump_calls = 0;
    tick_n(&core, 1, 1);
    TEST_ASSERT_EQUAL_INT(1, ps_tx_pump_calls);
}

void test_ps_core_on_rx_basic(void) {
    fb_reset(&rx_fb);
    make_fb_if(&rx_fb, &rx_if);
    core.rx.iface = &rx_if;

    uint8_t data[10];
    for (uint8_t i = 0; i < 10; i++) data[i] = i;

    // Normal append
    ps_core_on_rx(&core, data, 10);
    TEST_ASSERT_EQUAL_UINT16(10, fb_size(&rx_fb));

    uint8_t buf[10];
    fb_copy(&rx_fb, buf, 10);
    for (uint8_t i = 0; i < 10; i++) {
        TEST_ASSERT_EQUAL_UINT8(i, buf[i]);
    }

    // Test n=0 → should not change buffer
    ps_core_on_rx(&core, data, 0);
    TEST_ASSERT_EQUAL_UINT16(10, fb_size(&rx_fb));

    // Test d=NULL → should not change buffer
    ps_core_on_rx(&core, NULL, 5);
    TEST_ASSERT_EQUAL_UINT16(10, fb_size(&rx_fb));

    // Test c=NULL → should not crash
    ps_core_on_rx(NULL, data, 5);

    // Test iface=NULL → should not crash
    core.rx.iface = NULL;
    ps_core_on_rx(&core, data, 5);

    // Test append=NULL → should not crash
    core.rx.iface = &rx_if;
    core.rx.iface->append = NULL;
    ps_core_on_rx(&core, data, 5);
}

void test_ps_core_on_rx_large_n(void) {
    fb_reset(&rx_fb);
    make_fb_if(&rx_fb, &rx_if);
    core.rx.iface = &rx_if;

    static uint8_t dummy[UINT16_MAX + 100] = {0};
    ps_core_on_rx(&core, dummy, UINT16_MAX + 100);

    // Expect the buffer to be filled to its max, FB_CAP
    TEST_ASSERT_EQUAL_UINT16(FB_CAP, fb_size(&rx_fb));
}

/* ---------------------------
 * Main
 * --------------------------- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_when_start_cmd_received_then_streaming_requested_and_ack_sent);
    RUN_TEST(test_when_stop_cmd_received_then_streaming_cleared_and_ack_sent);
    RUN_TEST(test_when_unknown_cmd_received_then_nack_sent);
    RUN_TEST(test_when_sensor_coop_then_ready_and_stream_sent);
    RUN_TEST(test_when_sensor_start_error_then_error_and_recover_to_idle);
    RUN_TEST(test_when_sensor_poll_returns_negative_then_error_and_recover_to_idle);
    RUN_TEST(test_when_ready_and_fill_returns_zero_then_no_stream_sent);
    RUN_TEST(test_null_and_zero_inputs);
    RUN_TEST(test_rx_parse_returns_zero_pops_one);
    RUN_TEST(test_rx_non_cmd_frame_does_not_call_handle_cmd);
    RUN_TEST(test_update_streaming_state_false_combinations);
    RUN_TEST(test_idle_not_ready_yet);
    RUN_TEST(test_ps_tx_pump_called);
    RUN_TEST(test_ps_core_on_rx_basic);
    RUN_TEST(test_ps_core_on_rx_large_n);

    return UNITY_END();
}
