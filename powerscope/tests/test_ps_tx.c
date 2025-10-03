/**
 * @file    test_ps_tx.c
 * @brief   Unit tests for ps_tx.c, mocking ps_buffer_if_t and transport functions.
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "protocol_defs.h" /* for PROTO_* constants and proto_write helpers */
#include "ps_tx.h"
#include "unity.h"

/* --- Mock buffer implementation (simple linear buffer for tests) --- */
typedef struct {
    uint8_t buf[512];
    uint16_t used;
} mock_buf_ctx_t;

static mock_buf_ctx_t g_mock_buf;

/* ps_buffer_if_t-compatible mock functions */

static uint16_t mock_capacity(void* ctx) {
    (void)ctx;
    return (uint16_t)sizeof(g_mock_buf.buf);
}

static uint16_t mock_size(void* ctx) {
    (void)ctx;
    return g_mock_buf.used;
}

static uint16_t mock_space(void* ctx) {
    (void)ctx;
    return (uint16_t)(sizeof(g_mock_buf.buf) - g_mock_buf.used);
}

/* append returns true on success (all bytes appended), false otherwise */
static bool mock_append(void* ctx, const uint8_t* data, uint16_t len) {
    (void)ctx;
    if (len == 0) return true;
    if (len > mock_space(ctx)) return false;
    memcpy(&g_mock_buf.buf[g_mock_buf.used], data, len);
    g_mock_buf.used = (uint16_t)(g_mock_buf.used + len);
    return true;
}

/* copy: copy up to len bytes from head (does not pop) */
static void mock_copy(void* ctx, void* dst, uint16_t len) {
    (void)ctx;
    if (dst == NULL || len == 0) return;
    if (len > g_mock_buf.used) len = g_mock_buf.used;
    memcpy(dst, g_mock_buf.buf, len);
}

/* pop: remove len bytes from head (clamp to used) */
static void mock_pop(void* ctx, uint16_t len) {
    (void)ctx;
    if (len == 0) return;
    if (len >= g_mock_buf.used) {
        g_mock_buf.used = 0;
        return;
    }
    memmove(g_mock_buf.buf, &g_mock_buf.buf[len], (size_t)(g_mock_buf.used - len));
    g_mock_buf.used = (uint16_t)(g_mock_buf.used - len);
}

/* clear: drop all data */
static void mock_clear(void* ctx) {
    (void)ctx;
    g_mock_buf.used = 0;
}

/* peek_contiguous: return pointer to contiguous region starting at head and its length */
static uint16_t mock_peek_contiguous(void* ctx, const uint8_t** out) {
    (void)ctx;
    if (g_mock_buf.used == 0) {
        if (out) *out = NULL;
        return 0;
    }
    if (out) *out = g_mock_buf.buf;
    return g_mock_buf.used;
}

/* --- Mock transport --- */
static int g_tx_sent_len;
static uint8_t g_tx_sent[1024];

static int mock_tx_write(const uint8_t* buf, uint16_t len) {
    if (len == 0) return 0;
    if ((size_t)len > sizeof(g_tx_sent)) return -1;
    memcpy(g_tx_sent, buf, len);
    g_tx_sent_len = len;
    return (int)len;
}

static bool mock_link_ready_true(void) {
    return true;
}
static bool mock_link_ready_false(void) {
    return false;
}

static uint16_t mock_best_chunk_large(void) {
    return 1024;
}

/* --- Test fixtures --- */
static ps_tx_ctx_t tx_ctx;
static ps_buffer_if_t buf_if;
static uint32_t seq;

void setUp(void) {
    memset(&g_mock_buf, 0, sizeof(g_mock_buf));
    memset(&tx_ctx, 0, sizeof(tx_ctx));
    memset(g_tx_sent, 0, sizeof(g_tx_sent));
    g_tx_sent_len = 0;
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

/* --- Tests --- */

void test_ps_tx_init_valid_and_invalid(void) {
    /* valid init */
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 128));
    TEST_ASSERT_EQUAL_PTR(&buf_if, tx_ctx.tx_buf);
    TEST_ASSERT_EQUAL_PTR(mock_tx_write, tx_ctx.tx_write);
    TEST_ASSERT_EQUAL_PTR(mock_link_ready_true, tx_ctx.link_ready);
    TEST_ASSERT_EQUAL_PTR(mock_best_chunk_large, tx_ctx.best_chunk);
    TEST_ASSERT_EQUAL_PTR(&seq, tx_ctx.seq_ptr);
    TEST_ASSERT_EQUAL_UINT16(128, tx_ctx.max_payload);

    /* invalid args */
    TEST_ASSERT_FALSE(ps_tx_init(NULL, &buf_if, mock_tx_write, mock_link_ready_true,
                                 mock_best_chunk_large, &seq, 0));
    TEST_ASSERT_FALSE(ps_tx_init(&tx_ctx, NULL, mock_tx_write, mock_link_ready_true,
                                 mock_best_chunk_large, &seq, 0));
    TEST_ASSERT_FALSE(
        ps_tx_init(&tx_ctx, &buf_if, NULL, mock_link_ready_true, mock_best_chunk_large, &seq, 0));
    TEST_ASSERT_FALSE(
        ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, NULL, mock_best_chunk_large, &seq, 0));
    TEST_ASSERT_FALSE(
        ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true, NULL, &seq, 0));
}

/* Use ps_tx_send_hdr to create a valid frame, then pump and verify it's sent */
void test_ps_tx_enqueue_and_pump_basic(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 0));

    /* Use ps_tx_send_hdr to generate a properly formatted frame */
    ps_tx_send_hdr(&tx_ctx, PROTO_TYPE_ACK, 123, 456);

    /* buffer must now contain at least header+crc */
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN));

    /* Pump should send the whole frame (transport mock returns full length) */
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_TRUE(g_tx_sent_len >= (int)(PROTO_HDR_LEN + PROTO_CRC_LEN));
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx)); /* popped */
}

/* ps_tx_pump respects link_ready == false (no send) */
void test_ps_tx_pump_respects_link_ready(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_false,
                                mock_best_chunk_large, &seq, 0));
    uint8_t frame[4] = {(uint8_t)(PROTO_MAGIC & 0xFF),         // low byte
                        (uint8_t)((PROTO_MAGIC >> 8) & 0xFF),  // high byte
                        PROTO_VERSION, 0x00};
    ps_tx_enqueue_frame(&tx_ctx, frame, sizeof(frame));
    TEST_ASSERT_EQUAL_UINT16(4, mock_size(buf_if.ctx));
    /* pump should do nothing because link not ready */
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_EQUAL_UINT16(4, mock_size(buf_if.ctx));
    TEST_ASSERT_EQUAL_INT(0, g_tx_sent_len);
}

/* Test ps_tx_send_stream increments seq and enqueues frame */
void test_ps_tx_send_stream_and_seq_increment(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 64));
    uint32_t before = seq;
    uint8_t payload[3] = {1, 2, 3};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    /* seq should be incremented by 1 because seq_ptr provided */
    TEST_ASSERT_EQUAL_UINT32(before + 1, seq);
    /* buffer should contain at least header+payload+crc */
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >=
                     (PROTO_HDR_LEN + (uint16_t)sizeof(payload) + PROTO_CRC_LEN));
}

/* Test ps_tx_send_hdr enqueues a header-only frame */
void test_ps_tx_send_hdr_enqueue(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));
    /* send a header-only frame (ACK/NACK type) */
    ps_tx_send_hdr(&tx_ctx, 0xFE, 12345, 9876);
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN));
}

/* Test dropping garbage in buffer via enqueue path */
void test_ps_tx_enqueue_drops_garbage_frame(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* Insert garbage bytes (not matching proto header) */
    uint8_t garbage[3] = {0xFF, 0xFF, 0xFF};
    ps_tx_enqueue_frame(&tx_ctx, garbage, sizeof(garbage));
    TEST_ASSERT_EQUAL_UINT16(3, mock_size(buf_if.ctx));

    /* Now append a valid-looking small frame */
    ps_tx_send_hdr(&tx_ctx, PROTO_TYPE_ACK, 1, 2);
    uint16_t before = mock_size(buf_if.ctx);
    TEST_ASSERT_TRUE(before >= 3);

    /* Pump: should resync/pop garbage (size decreases) */
    ps_tx_pump(&tx_ctx);

    uint16_t after = mock_size(buf_if.ctx);
    TEST_ASSERT_TRUE(after < before);
}

/* Attempt to send a frame larger than allowed max_payload (should be rejected) */
void test_ps_tx_send_stream_respects_max_payload(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 2));
    uint8_t payload[4] = {1, 2, 3, 4};
    ps_tx_send_stream(&tx_ctx, payload, (uint16_t)sizeof(payload), 0);
    /* payload too large for max_payload, nothing enqueued */
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));
}

/*    If the buffer contains an incomplete valid header (header says payload N but not enough
 * bytes), drop_one_frame_buf should return 0 and ps_tx_enqueue_frame will clear the buffer
 * (fallback).
 */
void test_ps_tx_enqueue_clears_on_incomplete_frame_header(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* Produce a full valid frame, then append only its header bytes to simulate a truncated frame
     */
    uint8_t full_frame[PROTO_FRAME_MAX_BYTES];
    size_t full_n =
        proto_write_stream_frame(full_frame, sizeof(full_frame), (uint8_t*)"\xAA\xBB\xCC", 3, 0, 0);
    TEST_ASSERT_TRUE(full_n > 0);

    /* Append only the header bytes (simulate truncated/incomplete frame in buffer) */
    TEST_ASSERT_TRUE(buf_if.append(buf_if.ctx, full_frame, (uint16_t)PROTO_HDR_LEN));
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= PROTO_HDR_LEN);

    /* Attempt to enqueue a new valid header-only frame.
     * drop_one_frame_buf will return 0 (incomplete)
     * -> enqueue will clear buffer and append new frame.
     */
    ps_tx_send_hdr(&tx_ctx, PROTO_TYPE_ACK, 77, 88);

    /* After enqueue, buffer should contain at least the newly-enqueued header+CRC */
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN));

    /* Pump should send the newly enqueued frame */
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_TRUE(g_tx_sent_len >= (int)(PROTO_HDR_LEN + PROTO_CRC_LEN));
}

void test_ps_tx_drop_one_frame_buf(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* --- Buffer empty → nothing dropped --- */
    mock_clear(&g_mock_buf);
    ps_tx_enqueue_frame(&tx_ctx, NULL, 0);  // nothing to enqueue
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(&g_mock_buf));

    /* --- Garbage in buffer → pops bytes until valid frame fits --- */
    mock_clear(&g_mock_buf);
    uint8_t garbage[3] = {0xFF, 0xFF, 0xFF};
    buf_if.append(buf_if.ctx, garbage, sizeof(garbage));
    TEST_ASSERT_EQUAL_UINT16(3, mock_size(&g_mock_buf));

    /* enqueue a valid header-only frame */
    ps_tx_send_hdr(&tx_ctx, PROTO_TYPE_ACK, 1, 2);
    uint16_t sz_after = mock_size(&g_mock_buf);

    /* Garbage bytes should be removed, buffer contains only new valid frame */
    TEST_ASSERT_TRUE(sz_after >= PROTO_HDR_LEN + PROTO_CRC_LEN);
    TEST_ASSERT_TRUE(sz_after < 512);  // still fits in buffer

    /* --- Incomplete frame header → buffer cleared --- */
    mock_clear(&g_mock_buf);
    uint8_t incomplete_header[PROTO_HDR_LEN - 1] = {0};  // less than header
    buf_if.append(buf_if.ctx, incomplete_header, sizeof(incomplete_header));
    TEST_ASSERT_EQUAL_UINT16(sizeof(incomplete_header), mock_size(&g_mock_buf));

    /* enqueue a valid frame → triggers buf->clear internally */
    ps_tx_send_hdr(&tx_ctx, PROTO_TYPE_ACK, 77, 88);
    uint16_t sz_after_incomplete = mock_size(&g_mock_buf);
    TEST_ASSERT_TRUE(sz_after_incomplete >= PROTO_HDR_LEN + PROTO_CRC_LEN);

    /* --- Valid full frame → pops entire frame after pump --- */
    mock_clear(&g_mock_buf);
    uint8_t payload[3] = {1, 2, 3};
    uint8_t full_frame[PROTO_FRAME_MAX_BYTES];
    size_t n =
        proto_write_stream_frame(full_frame, sizeof(full_frame), payload, sizeof(payload), 0, 0);
    TEST_ASSERT_TRUE(n > 0);
    buf_if.append(buf_if.ctx, full_frame, (uint16_t)n);
    /* pump should send the frame and pop it from buffer */
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(&g_mock_buf));
    TEST_ASSERT_EQUAL_INT((int)n, g_tx_sent_len);
}

/* --- main --- */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_ps_tx_init_valid_and_invalid);
    RUN_TEST(test_ps_tx_enqueue_and_pump_basic);
    RUN_TEST(test_ps_tx_pump_respects_link_ready);
    RUN_TEST(test_ps_tx_send_stream_and_seq_increment);
    RUN_TEST(test_ps_tx_send_hdr_enqueue);
    RUN_TEST(test_ps_tx_enqueue_drops_garbage_frame);
    RUN_TEST(test_ps_tx_send_stream_respects_max_payload);
    RUN_TEST(test_ps_tx_enqueue_clears_on_incomplete_frame_header);
    RUN_TEST(test_ps_tx_drop_one_frame_buf);

    return UNITY_END();
}
