/**
 * @file    test_protocol.c
 * @brief   Unit tests for protocol framing/parsing and command application.
 */
#include <string.h>

#include "protocol_defs.h"
#include "unity.h"

static uint8_t buffer[256];
static proto_hdr_t hdr;
static uint16_t payload_len;

/* --- Setup/teardown --- */
void setUp(void) {
    memset(buffer, 0, sizeof buffer);
}
void tearDown(void) {}

/* --- Test: writing and parsing a simple CMD frame --- */
void test_write_and_parse_frame(void) {
    const uint8_t test_payload[] = {0xAA, 0xBB, 0xCC};

    size_t written = proto_write_frame(buffer, sizeof buffer, PROTO_TYPE_CMD,  /* type */
                                       0x42,                                   /* cmd_id */
                                       test_payload, sizeof test_payload, 123, /* seq */
                                       456);                                   /* ts_ms */

    TEST_ASSERT_TRUE(written > 0);

    const uint8_t* parsed_payload = NULL;
    size_t parsed = proto_parse_frame(buffer, written, &hdr, &parsed_payload, &payload_len);

    TEST_ASSERT_EQUAL_size_t(written, parsed);
    TEST_ASSERT_EQUAL_UINT8(PROTO_TYPE_CMD, hdr.type);
    TEST_ASSERT_EQUAL_UINT8(0x42, hdr.cmd_id);
    TEST_ASSERT_EQUAL_UINT16(sizeof test_payload, payload_len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(test_payload, parsed_payload, payload_len);
}

/* --- Test: frame too small or invalid magic/version --- */
void test_parse_invalid_frame(void) {
    const uint8_t* parsed_payload = NULL;

    // invalid magic, but size >= header+crc so parsing will proceed and fail
    buffer[0] = 0x00;
    buffer[1] = 0x00;
    buffer[2] = PROTO_VERSION;

    size_t parsed = proto_parse_frame(buffer, sizeof buffer, &hdr, &parsed_payload, &payload_len);
    TEST_ASSERT_EQUAL_size_t(0, parsed);

    // valid magic but wrong version
    buffer[0] = (uint8_t)(PROTO_MAGIC & 0xFF);
    buffer[1] = (uint8_t)((PROTO_MAGIC >> 8) & 0xFF);
    buffer[2] = 0xFF;  // wrong version

    parsed = proto_parse_frame(buffer, sizeof buffer, &hdr, &parsed_payload, &payload_len);
    TEST_ASSERT_EQUAL_size_t(0, parsed);
}

/* --- Test: incomplete frame --- */
void test_parse_incomplete_frame(void) {
    size_t written = proto_write_frame(buffer, sizeof buffer, PROTO_TYPE_CMD, 0x01, NULL, 0, 0, 0);
    TEST_ASSERT_TRUE(written > 0);

    const uint8_t* parsed_payload = NULL;

    // remove last byte to simulate incomplete frame
    size_t parsed = proto_parse_frame(buffer, written - 1, &hdr, &parsed_payload, &payload_len);
    TEST_ASSERT_EQUAL_size_t(0, parsed);
}

/* --- Test: parse edge cases --- */
void test_parse_frame_edge_cases(void) {
    const uint8_t payload[] = {0x01, 0x02};
    proto_hdr_t tmp_hdr;
    const uint8_t* p = NULL;
    uint16_t len_out;

    // null buffer
    TEST_ASSERT_EQUAL_size_t(0, proto_parse_frame(NULL, 10, &tmp_hdr, &p, &len_out));

    // too short to even contain header + crc
    TEST_ASSERT_EQUAL_size_t(
        0, proto_parse_frame(payload, PROTO_HDR_LEN + PROTO_CRC_LEN - 1, &tmp_hdr, &p, &len_out));

    // valid frame but manually force length > max
    uint8_t buf[PROTO_HDR_LEN + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN];

    size_t n =
        proto_write_frame(buf, sizeof buf, PROTO_TYPE_CMD, 0x01, payload, PROTO_MAX_PAYLOAD, 0, 0);
    TEST_ASSERT_TRUE(n > 0);

    // corrupt len field to exceed max
    buf[4] = 0xFF;
    buf[5] = 0xFF;

    TEST_ASSERT_EQUAL_size_t(0, proto_parse_frame(buf, n, &tmp_hdr, &p, &len_out));

    // CRC mismatch
    buf[4] = (uint8_t)PROTO_MAX_PAYLOAD;
    buf[5] = 0x00;

    buf[n - 1] ^= 0xFF;  // corrupt CRC
    TEST_ASSERT_EQUAL_size_t(0, proto_parse_frame(buf, n, &tmp_hdr, &p, &len_out));

    // null optional outputs
    n = proto_write_frame(buf, sizeof buf, PROTO_TYPE_CMD, 0x01, payload, 2, 0, 0);
    TEST_ASSERT_TRUE(n > 0);

    TEST_ASSERT_EQUAL_size_t(n, proto_parse_frame(buf, n, NULL, NULL, NULL));
}

/* --- Test: payload length clipping --- */
void test_write_frame_max_payload(void) {
    uint8_t test_payload_buf[PROTO_MAX_PAYLOAD + 10];
    memset(test_payload_buf, 0x55, sizeof test_payload_buf);

    size_t written = proto_write_frame(buffer, sizeof buffer, PROTO_TYPE_CMD, 0x01,
                                       test_payload_buf, sizeof test_payload_buf, 0, 0);

    TEST_ASSERT_EQUAL_size_t(PROTO_HDR_LEN + PROTO_MAX_PAYLOAD + PROTO_CRC_LEN, written);

    const uint8_t* parsed_payload = NULL;
    (void)proto_parse_frame(buffer, written, &hdr, &parsed_payload, &payload_len);

    TEST_ASSERT_EQUAL_UINT16(PROTO_MAX_PAYLOAD, payload_len);
}

/* --- Test: proto_write_frame null out / insufficient buffer / payload clipping --- */
void test_write_frame_edge_cases(void) {
    uint8_t buf[10];
    uint8_t payload[100] = {0};

    // null output
    TEST_ASSERT_EQUAL_size_t(
        0, proto_write_frame(NULL, sizeof buf, PROTO_TYPE_CMD, 0x01, payload, 10, 0, 0));

    // insufficient capacity
    TEST_ASSERT_EQUAL_size_t(0, proto_write_frame(buf, 1, PROTO_TYPE_CMD, 0x01, payload, 2, 0, 0));

    // payload clipped to PROTO_MAX_PAYLOAD, but still must fit buffer size
    size_t n = proto_write_frame(buf, sizeof buf, PROTO_TYPE_CMD, 0x01, payload,
                                 PROTO_MAX_PAYLOAD + 10, 0, 0);

    TEST_ASSERT_TRUE(n <= sizeof buf);
}

/* --- Main --- */
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_write_and_parse_frame);
    RUN_TEST(test_parse_invalid_frame);
    RUN_TEST(test_parse_incomplete_frame);
    RUN_TEST(test_parse_frame_edge_cases);
    RUN_TEST(test_write_frame_max_payload);
    RUN_TEST(test_write_frame_edge_cases);
    return UNITY_END();
}
