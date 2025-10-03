/**
 * @file    test_ring_buffer_adapter.c
 * @brief   Unit tests for ps_ring_buffer_t adapter.
 */

#include <stdint.h>
#include <string.h>

#include "ring_buffer_adapter.h"
#include "unity.h"

static ps_ring_buffer_t buf;
static ps_buffer_if_t iface;
static uint8_t mem[16];

void setUp(void) {
    memset(mem, 0, sizeof(mem));
    memset(&buf, 0, sizeof(buf));
    memset(&iface, 0, sizeof(iface));

    ps_ring_buffer_init(&buf, mem, sizeof(mem), &iface);
}

void tearDown(void) {}

void test_ps_ring_buffer_init_null_params(void) {
    ps_ring_buffer_t local_buf;
    uint8_t local_mem[16];
    ps_buffer_if_t local_iface;

    /* Each NULL case */
    ps_ring_buffer_init(NULL, local_mem, 16, &local_iface);
    ps_ring_buffer_init(&local_buf, NULL, 16, &local_iface);
    ps_ring_buffer_init(&local_buf, local_mem, 16, NULL);

    /* Also test all NULL */
    ps_ring_buffer_init(NULL, NULL, 16, NULL);
}

/* Test all adapter functions */
void test_ring_buffer_adapter(void) {
    uint8_t data[4] = {1, 2, 3, 4};
    uint8_t copybuf[4];
    const uint8_t* peek_ptr;

    /* append */
    TEST_ASSERT_TRUE(iface.append(iface.ctx, data, 4));
    TEST_ASSERT_EQUAL_UINT16(4, iface.size(iface.ctx));
    TEST_ASSERT_EQUAL_UINT16(11, iface.space(iface.ctx)); /* usable = cap-1 - used */

    /* capacity */
    TEST_ASSERT_EQUAL_UINT16(16, iface.capacity(iface.ctx));

    /* pop */
    iface.pop(iface.ctx, 2);
    TEST_ASSERT_EQUAL_UINT16(2, iface.size(iface.ctx));

    /* copy */
    iface.copy(iface.ctx, copybuf, 2);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(data + 2, copybuf, 2);

    /* peek contiguous */
    uint16_t peek_len = iface.peek_contiguous(iface.ctx, &peek_ptr);
    TEST_ASSERT_EQUAL_UINT16(2, peek_len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(data + 2, peek_ptr, 2);

    /* clear */
    iface.clear(iface.ctx);
    TEST_ASSERT_EQUAL_UINT16(0, iface.size(iface.ctx));
    TEST_ASSERT_EQUAL_UINT16(15, iface.space(iface.ctx)); /* usable space = cap-1 */
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_ps_ring_buffer_init_null_params);
    RUN_TEST(test_ring_buffer_adapter);
    return UNITY_END();
}
