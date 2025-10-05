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

/* Control knobs */
static int g_append_fail_count;  /* fail append N times */
static int g_tx_write_limit;     /* return partial tx write length */
static uint16_t g_peek_limit;    /* non-contiguous peek limit */
static int g_mock_cleared_count; /* count of clear() calls */

/* ps_buffer_if_t-compatible mock functions */

static uint16_t mock_capacity(void* ctx) {
    (void)ctx;
    return (uint16_t)sizeof(g_mock_buf.buf);
}

/* capacity that reports zero (to test early return) */
static uint16_t mock_capacity_zero(void* ctx) {
    (void)ctx;
    return 0;
}

/* small capacity to simulate tiny buffer for early-reject tests */
static uint16_t mock_capacity_small_fn(void* ctx) {
    (void)ctx;
    return 4; /* deliberately small */
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
    if (g_append_fail_count > 0) {
        g_append_fail_count--;
        return false;
    }
    if (len == 0) return true;
    if (len > mock_space(ctx)) return false;
    memcpy(&g_mock_buf.buf[g_mock_buf.used], data, len);
    g_mock_buf.used += len;
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
    memmove(g_mock_buf.buf, &g_mock_buf.buf[len], g_mock_buf.used - len);
    g_mock_buf.used -= len;
}

/* clear: drop all data */
static void mock_clear(void* ctx) {
    (void)ctx;
    g_mock_buf.used = 0;
    g_mock_cleared_count++;
}

/* force "no space" condition so enqueue enters the make-room loop */
static uint16_t mock_space_zero(void* ctx) {
    (void)ctx;
    return 0;
}

/* peek_contiguous: return pointer to contiguous region starting at head and its length */
static uint16_t mock_peek_contiguous(void* ctx, const uint8_t** out) {
    (void)ctx;
    if (g_mock_buf.used == 0) {
        if (out) {
            *out = NULL;
        }
        return 0;
    }
    if (out) {
        *out = g_mock_buf.buf;
    }
    return g_peek_limit > 0 ? g_peek_limit : g_mock_buf.used;
}

/* --- Mock transport --- */
static int g_tx_sent_len;
static uint8_t g_tx_sent[1024];

static int mock_tx_write(const uint8_t* buf, uint16_t len) {
    if (len == 0) return 0;
    if ((size_t)len > sizeof(g_tx_sent)) return -1;
    if (g_tx_write_limit >= 0) return g_tx_write_limit;
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
static uint16_t mock_best_chunk_small(void) {
    return 4;
}  // for best_chunk limit test

/* --- Test fixtures --- */
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
    seq = 1000;
    g_mock_cleared_count = 0;

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

/* Test ps_tx_enqueue_frame call buf->clear() */
void test_ps_tx_enqueue_truncated_header_triggers_clear(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* clean start */
    mock_clear(&g_mock_buf);
    g_mock_cleared_count = 0;

    /* Build a valid full frame then append only its header bytes (simulate truncated header) */
    uint8_t tmp_full[PROTO_FRAME_MAX_BYTES];
    uint8_t some_payload[16];
    memset(some_payload, 0xAB, sizeof(some_payload));
    size_t full_n = proto_write_stream_frame(tmp_full, sizeof(tmp_full), some_payload,
                                             (uint16_t)sizeof(some_payload), 0, 0);
    TEST_ASSERT_TRUE(full_n > 0);

    /* Append only header bytes (no payload, no CRC) so used < frame_len for that header */
    TEST_ASSERT_TRUE(buf_if.append(buf_if.ctx, tmp_full, (uint16_t)PROTO_HDR_LEN));
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= PROTO_HDR_LEN);

    /* Prepare a new frame to enqueue (size is not important because we'll force space() result) */
    uint8_t new_frame[32];
    size_t new_n =
        proto_write_stream_frame(new_frame, sizeof(new_frame), (uint8_t*)"\x01\x02", 2, 0, 0);
    TEST_ASSERT_TRUE(new_n > 0);
    uint16_t new_len = (uint16_t)new_n;

    /* Temporarily override space() so ps_tx_enqueue_frame sees insufficient space and enters loop
     */
    uint16_t (*orig_space_fn)(void*) = buf_if.space;
    buf_if.space = mock_space_zero;

    ps_tx_enqueue_frame(&tx_ctx, new_frame, new_len);

    /* restore original space() implementation */
    buf_if.space = orig_space_fn;

    /* Verify the clear path executed */
    TEST_ASSERT_TRUE_MESSAGE(g_mock_cleared_count > 0, "buf->clear() was not called");
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

void test_ps_tx_enqueue_clears_on_incomplete_then_send_hdr(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* Simulate existing truncated frame by appending only header bytes */
    mock_clear(&g_mock_buf);
    uint8_t full_frame[PROTO_FRAME_MAX_BYTES];
    size_t full_n =
        proto_write_stream_frame(full_frame, sizeof(full_frame), (uint8_t*)"\xAA\xBB\xCC", 3, 0, 0);
    TEST_ASSERT_TRUE(full_n > 0);

    /* append only the header bytes (simulate truncated/incomplete frame) */
    TEST_ASSERT_TRUE(buf_if.append(buf_if.ctx, full_frame, (uint16_t)PROTO_HDR_LEN));
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= PROTO_HDR_LEN);

    /* Now send a header-only frame; enqueue should clear truncated data and append header frame */
    ps_tx_send_hdr(&tx_ctx, PROTO_TYPE_ACK, 77, 88);

    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= (PROTO_HDR_LEN + PROTO_CRC_LEN));

    /* Pump should send that header-only frame */
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_TRUE(g_tx_sent_len >= (int)(PROTO_HDR_LEN + PROTO_CRC_LEN));
}

void test_ps_tx_enqueue_clears_on_incomplete_then_append_large(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* Append only truncated header so drop_one_frame_buf will return 0 */
    mock_clear(&g_mock_buf);
    uint8_t truncated_hdr[PROTO_HDR_LEN];
    memset(truncated_hdr, 0, sizeof(truncated_hdr));
    TEST_ASSERT_TRUE(buf_if.append(buf_if.ctx, truncated_hdr, (uint16_t)PROTO_HDR_LEN));
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= PROTO_HDR_LEN);

    /* Build a larger stream frame to enqueue */
    uint8_t big_frame[64];
    size_t big_n =
        proto_write_stream_frame(big_frame, sizeof(big_frame), (uint8_t*)"\x01\x02", 2, 0, 0);
    TEST_ASSERT_TRUE(big_n > PROTO_HDR_LEN);
    uint16_t big_len = (uint16_t)big_n;

    /* Make buffer almost full so available space is < big_len.
       Append filler bytes until the space is strictly less than big_len. */
    while (buf_if.space(buf_if.ctx) >= big_len) {
        /* append a single filler byte — mock_append will succeed until full */
        uint8_t f = 0xFF;
        bool ok = buf_if.append(buf_if.ctx, &f, 1);
        TEST_ASSERT_TRUE_MESSAGE(ok, "failed to append filler byte while preparing buffer");
        /* guard: avoid infinite loop (shouldn't happen with our mock), but keep sanity */
        if (mock_size(buf_if.ctx) >= sizeof(g_mock_buf.buf)) break;
    }

    /* Now we should have insufficient space and will enter the make-room loop */
    TEST_ASSERT_TRUE_MESSAGE(buf_if.space(buf_if.ctx) < big_len,
                             "failed to create low-space condition for enqueue test");

    /* Enqueue: should clear buffer (because drop_one_frame_buf returns 0 on truncated header)
       then append new big frame */
    ps_tx_enqueue_frame(&tx_ctx, big_frame, big_len);

    /* After enqueue, buffer should contain the newly appended full frame */
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) >= big_len);
}

void test_ps_tx_enqueue_early_return_invalid_args(void) {
    /* init normally */
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    uint8_t dummy[4] = {0, 1, 2, 3};
    mock_clear(&g_mock_buf);

    /* null ctx -> no crash and nothing appended */
    ps_tx_enqueue_frame(NULL, dummy, (uint16_t)sizeof(dummy));
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));

    /* null frame -> no crash and nothing appended */
    ps_tx_enqueue_frame(&tx_ctx, NULL, (uint16_t)sizeof(dummy));
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));

    /* len == 0 -> no crash nothing appended */
    ps_tx_enqueue_frame(&tx_ctx, dummy, 0);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));
}

void test_ps_tx_enqueue_capacity_and_size_rejections(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));
    uint8_t dummy[8] = {0, 1, 2, 3, 4, 5, 6, 7};
    mock_clear(&g_mock_buf);

    /* capacity == 0: nothing appended */
    buf_if.capacity = mock_capacity_zero;
    ps_tx_enqueue_frame(&tx_ctx, dummy, (uint16_t)sizeof(dummy));
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));

    /* capacity too small: len > cap - 1 -> nothing appended */
    buf_if.capacity = mock_capacity_small_fn;
    mock_clear(&g_mock_buf);
    uint16_t too_big = 10; /* bigger than capacity 4 - 1 */
    ps_tx_enqueue_frame(&tx_ctx, dummy, too_big);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));

    /* restore */
    buf_if.capacity = mock_capacity;
}

void test_ps_tx_drop_one_frame_buf(void) {
    int dropped;

    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));

    /* --- Empty buffer → nothing dropped --- */
    mock_clear(&g_mock_buf);
    dropped = drop_one_frame_buf(&buf_if);
    TEST_ASSERT_EQUAL_INT(0, dropped);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(&g_mock_buf));

    /* --- Garbage in buffer → pops 1 byte (resync) --- */
    mock_clear(&g_mock_buf);
    uint8_t garbage[PROTO_HDR_LEN + PROTO_CRC_LEN] = {0xFF};  // invalid header bytes
    buf_if.append(buf_if.ctx, garbage, sizeof(garbage));
    TEST_ASSERT_EQUAL_UINT16(sizeof(garbage), mock_size(&g_mock_buf));

    dropped = drop_one_frame_buf(&buf_if);
    TEST_ASSERT_EQUAL_INT(1, dropped);
    TEST_ASSERT_EQUAL_UINT16(sizeof(garbage) - 1, mock_size(&g_mock_buf));

    /* --- Incomplete frame header → returns 0, buffer unchanged --- */
    mock_clear(&g_mock_buf);
    uint8_t incomplete_header[PROTO_HDR_LEN - 1] = {0};
    buf_if.append(buf_if.ctx, incomplete_header, sizeof(incomplete_header));
    TEST_ASSERT_EQUAL_UINT16(sizeof(incomplete_header), mock_size(&g_mock_buf));

    dropped = drop_one_frame_buf(&buf_if);
    TEST_ASSERT_EQUAL_INT(0, dropped);
    TEST_ASSERT_EQUAL_UINT16(sizeof(incomplete_header), mock_size(&g_mock_buf));

    /* --- Valid full frame → drops entire frame --- */
    mock_clear(&g_mock_buf);
    uint8_t payload[3] = {0x11, 0x22, 0x33};
    uint8_t full_frame[PROTO_FRAME_MAX_BYTES];
    size_t n =
        proto_write_stream_frame(full_frame, sizeof(full_frame), payload, sizeof(payload), 0, 0);
    TEST_ASSERT_TRUE(n > 0);

    buf_if.append(buf_if.ctx, full_frame, (uint16_t)n);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)n, mock_size(&g_mock_buf));

    dropped = drop_one_frame_buf(&buf_if);
    TEST_ASSERT_EQUAL_INT(1, dropped);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(&g_mock_buf));
}

/* Test ps_tx_pump forces copy path (non-contiguous peek) */
void test_ps_tx_pump_non_contiguous(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 0));
    uint8_t payload[2] = {0xAA, 0xBB};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    g_peek_limit = 2;  // less than full frame size, force copy path
    ps_tx_pump(&tx_ctx);
    TEST_ASSERT_EQUAL_UINT16(0, mock_size(buf_if.ctx));
    TEST_ASSERT_TRUE(g_tx_sent_len > 0);
}

/* Test ps_tx_pump with partial write (tx_write < frame_len) */
void test_ps_tx_pump_partial_write(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, &seq, 0));
    uint8_t payload[2] = {0x11, 0x22};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    g_tx_write_limit = 1;  // partial write
    uint16_t buf_before = mock_size(buf_if.ctx);
    ps_tx_pump(&tx_ctx);
    // buffer should still contain the frame since write incomplete
    TEST_ASSERT_EQUAL_UINT16(buf_before, mock_size(buf_if.ctx));
}

/* Test ps_tx_pump respects best_chunk limit */
void test_ps_tx_pump_best_chunk_limit(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_small, &seq, 0));
    uint8_t payload[6] = {1, 2, 3, 4, 5, 6};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    uint16_t buf_before = mock_size(buf_if.ctx);
    ps_tx_pump(&tx_ctx);
    // frame too large for best_chunk_small, should not send
    TEST_ASSERT_EQUAL_UINT16(buf_before, mock_size(buf_if.ctx));
    TEST_ASSERT_EQUAL_INT(0, g_tx_sent_len);
}

/* Test ps_tx_send_stream with seq_ptr = NULL */
void test_ps_tx_send_stream_no_seq_ptr(void) {
    TEST_ASSERT_TRUE(ps_tx_init(&tx_ctx, &buf_if, mock_tx_write, mock_link_ready_true,
                                mock_best_chunk_large, NULL, 0));
    uint8_t payload[2] = {0xAA, 0xBB};
    ps_tx_send_stream(&tx_ctx, payload, sizeof(payload), 0);
    // buffer should contain frame, seq_ptr not used
    TEST_ASSERT_TRUE(mock_size(buf_if.ctx) > 0);
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
    RUN_TEST(test_ps_tx_enqueue_clears_on_incomplete_then_send_hdr);
    RUN_TEST(test_ps_tx_enqueue_clears_on_incomplete_then_append_large);
    RUN_TEST(test_ps_tx_enqueue_early_return_invalid_args);
    RUN_TEST(test_ps_tx_enqueue_truncated_header_triggers_clear);
    RUN_TEST(test_ps_tx_enqueue_capacity_and_size_rejections);
    RUN_TEST(test_ps_tx_drop_one_frame_buf);
    RUN_TEST(test_ps_tx_pump_non_contiguous);
    RUN_TEST(test_ps_tx_pump_partial_write);
    RUN_TEST(test_ps_tx_pump_best_chunk_limit);
    RUN_TEST(test_ps_tx_send_stream_no_seq_ptr);

    return UNITY_END();
}
