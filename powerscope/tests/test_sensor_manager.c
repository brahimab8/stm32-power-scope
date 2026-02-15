/**
 * @file    test_sensor_manager.c
 * @brief   Unit tests for sensor/manager.c
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "sensor/manager.h"
#include "unity.h"

/* --- Mock sensor --- */
static bool mock_sample_success(void* hw_ctx, void* out) {
    (void)hw_ctx;
    uint8_t* buf = (uint8_t*)out;
    buf[0] = 0xAA;
    buf[1] = 0x55;
    return true;
}

static bool mock_sample_fail(void* hw_ctx, void* out) {
    (void)hw_ctx;
    (void)out;
    return false;
}

/* --- Timestamp control --- */
static uint32_t t;

static uint32_t mock_now_ms(void) {
    return t += 100;  // increments by 100ms every call
}

/* --- Fixtures --- */
static sensor_mgr_ctx_t ctx;
static uint8_t sample_buf[2];
static sensor_iface_t iface;

void setUp(void) {
    memset(&ctx, 0, sizeof(ctx));
    memset(sample_buf, 0, sizeof(sample_buf));
    ctx.last_sample = sample_buf;
    t = 1000;

    iface.hw_ctx = NULL;
    iface.read_sample = mock_sample_success;
    iface.sample_size = sizeof(sample_buf);
}

void tearDown(void) {}

/* --- Tests --- */

void test_init_deinit(void) {
    bool ok = sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms);
    TEST_ASSERT_TRUE(ok);
    TEST_ASSERT_EQUAL_UINT32(iface.sample_size, ctx.iface.sample_size);
    TEST_ASSERT_EQUAL_PTR(iface.read_sample, ctx.iface.read_sample);
    TEST_ASSERT_EQUAL_PTR(iface.hw_ctx, ctx.iface.hw_ctx);
    TEST_ASSERT_EQUAL_UINT8(0, ctx.last_sample[0]);
    TEST_ASSERT_EQUAL_UINT8(0, ctx.last_sample[1]);
    TEST_ASSERT_EQUAL(IDLE, ctx.state);

    /* Null params should fail */
    TEST_ASSERT_FALSE(sensor_mgr_init(NULL, iface, sample_buf, mock_now_ms));
    TEST_ASSERT_FALSE(sensor_mgr_init(&ctx, iface, NULL, mock_now_ms));
    iface.read_sample = NULL;
    TEST_ASSERT_FALSE(sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms));
    iface.read_sample = mock_sample_success;
    iface.sample_size = 0;
    TEST_ASSERT_FALSE(sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms));

    sensor_mgr_deinit(&ctx);
    TEST_ASSERT_EQUAL(IDLE, ctx.state);
    sensor_mgr_deinit(NULL);
}

void test_sample_blocking(void) {
    sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms);

    /* Success path */
    bool ok = sensor_mgr_sample_blocking(&ctx);
    TEST_ASSERT_TRUE(ok);
    TEST_ASSERT_EQUAL(READY, ctx.state);
    TEST_ASSERT_EQUAL_INT(SENSOR_MGR_ERR_NONE, ctx.last_err);
    TEST_ASSERT_EQUAL_UINT32(1100, ctx.last_sample_ms);
    TEST_ASSERT_EQUAL_UINT8(0xAA, sample_buf[0]);
    TEST_ASSERT_EQUAL_UINT8(0x55, sample_buf[1]);

    /* Fail path */
    ctx.iface.read_sample = mock_sample_fail;
    ctx.state = REQUESTED;
    ok = sensor_mgr_sample_blocking(&ctx);
    TEST_ASSERT_FALSE(ok);
    TEST_ASSERT_EQUAL(ERROR, ctx.state);
    TEST_ASSERT_EQUAL_INT(SENSOR_MGR_ERR_READ_FAIL, ctx.last_err);

    TEST_ASSERT_FALSE(sensor_mgr_sample_blocking(NULL));
}

void test_cooperative_start_poll(void) {
    sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms);

    int res = sensor_mgr_start(&ctx);
    TEST_ASSERT_EQUAL(SENSOR_MGR_BUSY, res);
    TEST_ASSERT_EQUAL(REQUESTED, ctx.state);

    res = sensor_mgr_poll(&ctx);
    TEST_ASSERT_EQUAL(SENSOR_MGR_READY, res);
    TEST_ASSERT_EQUAL(READY, ctx.state);

    ctx.state = ERROR;
    TEST_ASSERT_EQUAL(SENSOR_MGR_ERROR, sensor_mgr_poll(&ctx));

    ctx.state = IDLE;
    TEST_ASSERT_EQUAL(SENSOR_MGR_READY, sensor_mgr_poll(&ctx));

    TEST_ASSERT_EQUAL(SENSOR_MGR_ERROR, sensor_mgr_start(NULL));
    TEST_ASSERT_EQUAL(SENSOR_MGR_ERROR, sensor_mgr_poll(NULL));
}

void test_fill_last_sample(void) {
    sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms);
    sensor_mgr_sample_blocking(&ctx);

    uint8_t dst[2] = {0};
    size_t n = sensor_mgr_fill(&ctx, dst, sizeof(dst));
    TEST_ASSERT_EQUAL(2, n);
    TEST_ASSERT_EQUAL_UINT8(0xAA, dst[0]);
    TEST_ASSERT_EQUAL_UINT8(0x55, dst[1]);

    n = sensor_mgr_fill(&ctx, dst, 1);  // too small
    TEST_ASSERT_EQUAL(0, n);

    ctx.state = ERROR;
    n = sensor_mgr_fill(&ctx, dst, sizeof(dst));
    TEST_ASSERT_EQUAL(0, n);

    n = sensor_mgr_fill(NULL, dst, sizeof(dst));
    TEST_ASSERT_EQUAL(0, n);
    n = sensor_mgr_fill(&ctx, NULL, sizeof(dst));
    TEST_ASSERT_EQUAL(0, n);
}

void test_last_error_and_timestamp(void) {
    sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms);
    sensor_mgr_sample_blocking(&ctx);
    TEST_ASSERT_EQUAL_INT(SENSOR_MGR_ERR_NONE, sensor_mgr_last_error(&ctx));
    TEST_ASSERT_EQUAL_UINT32(1100, sensor_mgr_last_sample_ms(&ctx));

    TEST_ASSERT_EQUAL_INT(SENSOR_MGR_ERR_INVALID_CTX, sensor_mgr_last_error(NULL));
    TEST_ASSERT_EQUAL_UINT32(0, sensor_mgr_last_sample_ms(NULL));
}

void test_as_adapter(void) {
    sensor_mgr_init(&ctx, iface, sample_buf, mock_now_ms);
    ps_sensor_adapter_t adapter = sensor_mgr_as_adapter(&ctx);

    int start_res = adapter.start(adapter.ctx);
    TEST_ASSERT_EQUAL(SENSOR_MGR_BUSY, start_res);
    int poll_res = adapter.poll(adapter.ctx);
    TEST_ASSERT_EQUAL(SENSOR_MGR_READY, poll_res);

    uint8_t dst[2] = {0};
    size_t n = adapter.fill(adapter.ctx, dst, sizeof(dst));
    TEST_ASSERT_EQUAL(2, n);
    TEST_ASSERT_EQUAL_UINT8(0xAA, dst[0]);
    TEST_ASSERT_EQUAL_UINT8(0x55, dst[1]);
}

/* --- main --- */
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_deinit);
    RUN_TEST(test_sample_blocking);
    RUN_TEST(test_cooperative_start_poll);
    RUN_TEST(test_fill_last_sample);
    RUN_TEST(test_last_error_and_timestamp);
    RUN_TEST(test_as_adapter);
    return UNITY_END();
}
