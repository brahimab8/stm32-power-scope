/**
 * @file    test_ps_tx.c
 * @brief   Unit tests for ps_tx.c using Unity, with setup/teardown and mocks.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "protocol_defs.h"
#include "ps_tx.h"
#include "unity.h"

/* -------------------- Mock buffer -------------------- */
typedef struct {
    uint8_t buf[512];
    uint16_t used;
} mock_buf_ctx_t;

static mock_buf_ctx_t g_mock_buf;
static int g_append_fail_count;
static int g_tx_write_limit;
static uint16_t g_peek_limit;
static int g_mock_cleared_count;

static uint16_t mock_capacity(void* ctx) {
    (void)ctx;
    return sizeof(g_mock_buf.buf);
}
static uint16_t mock_size(void* ctx) {
    (void)ctx;
    return g_mock_buf.used;
}
static uint16_t mock_space(void* ctx) {
    (void)ctx;
    return sizeof(g_mock_buf.buf) - g_mock_buf.used;
}
static bool mock_append(void* ctx, const uint8_t* data, uint16_t len) {
    (void)ctx;
    if (g_append_fail_count > 0) {
        g_append_fail_count--;
        return false;
    }
    if (len > mock_space(ctx)) return false;
    memcpy(&g_mock_buf.buf[g_mock_buf.used], data, len);
    g_mock_buf.used += len;
    return true;
}
static void mock_copy(void* ctx, void* dst, uint16_t len) {
    (void)ctx;
    if (len > g_mock_buf.used) len = g_mock_buf.used;
    memcpy(dst, g_mock_buf.buf, len);
}
static void mock_pop(void* ctx, uint16_t len) {
    (void)ctx;
    if (len >= g_mock_buf.used) {
        g_mock_buf.used = 0;
        return;
    }
    memmove(g_mock_buf.buf, &g_mock_buf.buf[len], g_mock_buf.used - len);
    g_mock_buf.used -= len;
}
static void mock_clear(void* ctx) {
    (void)ctx;
    g_mock_buf.used = 0;
    g_mock_cleared_count++;
}
static uint16_t mock_peek_contiguous(void* ctx, const uint8_t** out) {
    (void)ctx;
    if (g_mock_buf.used == 0) {
        if (out) *out = NULL;
        return 0;
    }
    if (out) *out = g_mock_buf.buf;
    return g_peek_limit > 0 ? g_peek_limit : g_mock_buf.used;
}

/* -------------------- Mock transport -------------------- */
static uint8_t g_tx_sent[1024];
static int g_tx_sent_len;
static int mock_tx_write(const uint8_t* buf, uint16_t len) {
    if (g_tx_write_limit >= 0) return g_tx_write_limit;
    memcpy(g_tx_sent, buf, len);
    g_tx_sent_len = len;
    return (int)len;
}
static bool mock_link_ready_true(void) {
    return true;
}
static uint16_t mock_best_chunk_large(void) {
    return 1024;
}
static uint16_t mock_best_chunk_small(void) {
    return 4;
}

/* -------------------- Test fixtures -------------------- */
static ps_tx_ctx_t tx_ctx;
static ps_buffer_if_t buf_if;
static uint32_t seq;

void setUp(void) {
    memset(&g_mock_buf, 0, sizeof(g_mock_buf));
    memset(&tx_ctx, 0, sizeof(tx_ctx));
    memset(g_tx_sent, 0, sizeof(g_tx_sent));
    g_tx_sent_len = 0;
    g_append_fail_count = 0;
    g_tx_write_limit = -1;
    g_peek_limit = 0;
    g_mock_cleared_count = 0;
    seq = 1000;

    buf_if.ctx = &g_mock_buf;
    buf_if.capacity = mock_capacity;
    buf_if.size = mock_size;
    buf_if.space = mock_space;
    buf_if.append = mock_append;
    buf_if.copy = mock_copy;
    buf_if.pop = mock_pop;
    buf_if.clear = mock_clear;
    buf_if.peek_contiguous = mock_peek_contiguous;
}

void tearDown(void) {}

/* -------------------- Tests -------------------- */
void test_ps_tx_init(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 128));
    TEST_ASSERT_FALSE(ps_tx_init(NULL, &buf_if, mock_tx_write, mock_link_ready_true,
                                 mock_best_chunk_large, &seq, 128));
    TEST_ASSERT_FALSE(ps_tx_init(&tx_ctx, NULL, mock_tx_write, mock_link_ready_true,
                                 mock_best_chunk_large, &seq, 128));
    TEST_ASSERT_FALSE(
        ps_tx_init(&tx_ctx, &buf_if, NULL, mock_link_ready_true, mock_best_chunk_large, &seq, 128));
    TEST_ASSERT_FALSE(
        ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, NULL, mock_best_chunk_large, &seq, 128));
    TEST_ASSERT_FALSE(
        ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true, NULL, &seq, 128));
}

void test_ps_tx_enqueue_and_pump_basic(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 0));
    ps_tx_send_response(&tx_ctx, PROTO_TYPE_ACK, 0, 123, 456);
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN));

    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));
    TEST_ASSERT_TRUE(g_tx_sent_len >= (int)(PROTO_HDR_LEN + PROTO_CRC_LEN));
}

void test_ps_tx_enqueue_frame_len_zero(void) {
    ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true, mock_best_chunk_large, &seq,
               128);
    ps_tx_enqueue_frame(&tx_ctx, NULL, 0);  // should return without crash
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));
}

void test_ps_tx_send_stream_seq_increment(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 64));
    uint32_t before = seq;
    uint8_t payload[3] = {1, 2, 3};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    TEST_ASSERT_EQUAL_UINT32(before + 1, seq);
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= (PROTO_HDR_LEN + sizeof(payload) + PROTO_CRC_LEN));
}

void test_ps_tx_send_stream_over_max_payload(void) {
    ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true, mock_best_chunk_large, &seq,
               2);  // max_payload = 2
    uint8_t payload[3] = {1, 2, 3};
    ps_tx_send_stream(&tx_ctx, payload, 3, 0);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));  // frame not enqueued
}

void test_ps_tx_pump_best_chunk_limit(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_small, &seq, 0));
    uint8_t payload[6] = {1, 2, 3, 4, 5, 6};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    uint16_t before = mock_size(buf_if.ctx);
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_EQUAL_UINT16(before, mock_size(buf_if.ctx));
    TEST_ASSERT_EQUAL_INT(0, g_tx_sent_len);
}

void test_ps_tx_pump_fallback_path(void) {
    g_peek_limit = 1;  // force peek_contiguous < frame_len
    ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true, mock_best_chunk_large, &seq,
               128);
    uint8_t payload[6] = {1, 2, 3, 4, 5, 6};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    ps_tx_pump(&tx_ctx);  // triggers fallback copy path
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));
}

static bool mock_link_ready_false(void) {
    return false;
}
void test_ps_tx_pump_link_not_ready(void) {
    ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_false, mock_best_chunk_large, &seq,
               128);
    uint8_t payload[1] = {0xAA};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    ps_tx_pump(&tx_ctx);                          // should return early
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) > 0);  // still in buffer
}

void test_ps_tx_drop_one_frame_buf(void) {
    int dropped;

    mock_clear(&g_mock_buf);
    dropped = drop_one_frame_buf(&buf_if);
    TEST_ASSERT_EQUAL_INT(0, dropped);

    /* garbage: pop 1 byte */
    uint8_t garbage[PROTO_HDR_LEN + PROTO_CRC_LEN] = {0xFF};
    buf_if.append(buf_if.ctx, garbage, sizeof(garbage));
    dropped = drop_one_frame_buf(&buf_if);
    TEST_ASSERT_EQUAL_INT(1, dropped);
    TEST_ASSERT_EQUAL_UINT16(sizeof(garbage) - 1, mock_size(buf_if.ctx));
}

void test_drop_one_frame_buf_garbage(void) {
    mock_clear(&g_mock_buf);
    uint8_t garbage[PROTO_HDR_LEN + PROTO_CRC_LEN] = {0xFF};
    buf_if.append(buf_if.ctx, garbage, sizeof(garbage));
    int dropped = drop_one_frame_buf(&buf_if);  // triggers pop 1 byte
    TEST_ASSERT_EQUAL_INT(1, dropped);
    TEST_ASSERT_EQUAL_UINT16(sizeof(garbage) - 1, mock_size(buf_if.ctx));
}

/* -------------------- Main -------------------- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_ps_tx_init);
    RUN_TEST(test_ps_tx_enqueue_and_pump_basic);
    RUN_TEST(test_ps_tx_enqueue_frame_len_zero);
    RUN_TEST(test_ps_tx_send_stream_seq_increment);
    RUN_TEST(test_ps_tx_send_stream_over_max_payload);
    RUN_TEST(test_ps_tx_pump_fallback_path);
    RUN_TEST(test_ps_tx_pump_link_not_ready);
    RUN_TEST(test_ps_tx_pump_best_chunk_limit);
    RUN_TEST(test_ps_tx_drop_one_frame_buf);
    RUN_TEST(test_drop_one_frame_buf_garbage);

    return UNITY_END();
}
