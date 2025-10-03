/**
 * @file    test_ring_buffer.c
 * @brief   Unit tests for rb_t SPSC ring buffer.
 */

#include <string.h>

#include "ring_buffer.h"
#include "unity.h"

#define BUF_SIZE 8 /* Must be a power of two */
static uint8_t buf[BUF_SIZE];
static rb_t rb;

void setUp(void) {
    rb_init(&rb, buf, BUF_SIZE);
}

void tearDown(void) {
    rb_clear(&rb);
}

/* --- Initial state --- */
void test_initial_state(void) {
    TEST_ASSERT_EQUAL_UINT16(0, rb_used(&rb));
    TEST_ASSERT_EQUAL_UINT16(BUF_SIZE, rb_capacity(&rb));
    TEST_ASSERT_EQUAL_UINT16(BUF_SIZE - 1, rb_free(&rb));
    TEST_ASSERT_EQUAL_UINT32(0, rb_reject_count(&rb));
    TEST_ASSERT_EQUAL_UINT16(0, rb_highwater(&rb));
}

/* --- Peek linear --- */
void test_peek_linear(void) {
    const uint8_t* ptr;
    uint16_t lin = rb_peek_linear(&rb, &ptr);
    TEST_ASSERT_EQUAL_UINT16(0, lin);
    TEST_ASSERT_NULL(ptr);

    uint8_t data[] = {10, 20, 30};
    rb_write_try(&rb, data, 3);

    lin = rb_peek_linear(&rb, &ptr);
    TEST_ASSERT_EQUAL_UINT16(3, lin);
    TEST_ASSERT_EQUAL_UINT8(10, ptr[0]);
    TEST_ASSERT_EQUAL_UINT8(20, ptr[1]);
    TEST_ASSERT_EQUAL_UINT8(30, ptr[2]);

    rb_pop(&rb, 2);
    lin = rb_peek_linear(&rb, &ptr);
    TEST_ASSERT_EQUAL_UINT16(1, lin);
    TEST_ASSERT_EQUAL_UINT8(30, ptr[0]);

    uint8_t data2[] = {40, 50, 60, 70, 80};
    rb_write_try(&rb, data2, 5);
    lin = rb_peek_linear(&rb, &ptr);
    TEST_ASSERT_EQUAL_UINT16(6, lin);
    TEST_ASSERT_EQUAL_UINT8(30, ptr[0]);
}

/* Peek with null pointer */
void test_peek_linear_null(void) {
    rb_clear(&rb);
    TEST_ASSERT_EQUAL_UINT16(0, rb_peek_linear(&rb, NULL));
}

/* --- Copy from tail --- */
void test_copy_from_tail_null(void) {
    uint16_t copied = rb_copy_from_tail(&rb, NULL, 5);
    TEST_ASSERT_EQUAL_UINT16(0, copied);
}

/* --- Write/Read using try --- */
void test_write_try_success(void) {
    uint8_t data[3] = {1, 2, 3};
    uint16_t written = rb_write_try(&rb, data, 3);
    TEST_ASSERT_EQUAL_UINT16(3, written);
    TEST_ASSERT_EQUAL_UINT16(3, rb_used(&rb));
    TEST_ASSERT_EQUAL_UINT16(BUF_SIZE - 1 - 3, rb_free(&rb));
    TEST_ASSERT_EQUAL_UINT16(3, rb_highwater(&rb));
}

/* Reject when len > usable */
void test_write_try_len_too_large(void) {
    uint8_t data[BUF_SIZE] = {0};
    uint16_t written = rb_write_try(&rb, data, BUF_SIZE);
    TEST_ASSERT_EQUAL_UINT16(0, written);
    TEST_ASSERT_EQUAL_UINT32(BUF_SIZE, rb_reject_count(&rb));
}

/* Reject when free < len but len <= usable */
void test_write_try_insufficient(void) {
    uint8_t data1[BUF_SIZE - 2] = {0};
    uint8_t data2[3] = {1, 2, 3};
    rb_write_try(&rb, data1, BUF_SIZE - 2);
    uint16_t written = rb_write_try(&rb, data2, 3);
    TEST_ASSERT_EQUAL_UINT16(0, written);
    TEST_ASSERT_EQUAL_UINT32(3, rb_reject_count(&rb));
}

/* --- Wrap-around --- */
void test_wrap_around(void) {
    uint8_t data[5] = {1, 2, 3, 4, 5};
    rb_write_try(&rb, data, 5);
    rb_pop(&rb, 3);
    uint8_t data2[4] = {6, 7, 8, 9};
    rb_write_try(&rb, data2, 4);
    uint8_t out[BUF_SIZE] = {0};
    uint16_t copied = rb_copy_from_tail(&rb, out, BUF_SIZE);
    TEST_ASSERT_EQUAL_UINT16(6, copied);
    uint8_t expected[] = {4, 5, 6, 7, 8, 9};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(expected, out, 6);
}

/* --- Pop and copy --- */
void test_rb_pop_and_copy(void) {
    uint8_t data[4] = {10, 20, 30, 40};
    rb_write_try(&rb, data, 4);
    uint8_t out[4] = {0};
    uint16_t copied = rb_copy_from_tail(&rb, out, 2);
    TEST_ASSERT_EQUAL_UINT16(2, copied);
    TEST_ASSERT_EQUAL_UINT8(10, out[0]);
    TEST_ASSERT_EQUAL_UINT8(20, out[1]);
    rb_pop(&rb, 2);
    TEST_ASSERT_EQUAL_UINT16(2, rb_used(&rb));
}

/* --- Highwater --- */
void test_highwater_update(void) {
    uint8_t data1[3] = {1, 2, 3};
    uint8_t data2[2] = {4, 5};
    rb_write_try(&rb, data1, 3);
    TEST_ASSERT_EQUAL_UINT16(3, rb_highwater(&rb));
    rb_write_try(&rb, data2, 2);
    TEST_ASSERT_EQUAL_UINT16(5, rb_highwater(&rb));
}

/* --- Zero-length writes --- */
void test_zero_length_write(void) {
    uint8_t data[1] = {0};
    TEST_ASSERT_EQUAL_UINT16(0, rb_write_try(&rb, data, 0));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_initial_state);
    RUN_TEST(test_peek_linear);
    RUN_TEST(test_peek_linear_null);
    RUN_TEST(test_copy_from_tail_null);
    RUN_TEST(test_write_try_success);
    RUN_TEST(test_write_try_len_too_large);
    RUN_TEST(test_write_try_insufficient);
    RUN_TEST(test_wrap_around);
    RUN_TEST(test_rb_pop_and_copy);
    RUN_TEST(test_highwater_update);
    RUN_TEST(test_zero_length_write);
    return UNITY_END();
}
