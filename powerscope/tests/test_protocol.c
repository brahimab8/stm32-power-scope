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

/* --- Test: writing and parsing a simple frame --- */
void test_write_and_parse_frame(void) {
    const uint8_t test_payload[] = {0xAA, 0xBB, 0xCC};
    size_t written =
        proto_write_frame(buffer, sizeof buffer, 0x42, test_payload, sizeof test_payload, 123, 456);
    TEST_ASSERT_TRUE(written > 0);

    const uint8_t* parsed_payload = NULL;
    size_t parsed = proto_parse_frame(buffer, written, &hdr, &parsed_payload, &payload_len);
    TEST_ASSERT_EQUAL_size_t(written, parsed);
    TEST_ASSERT_EQUAL_UINT8(0x42, hdr.type);
    TEST_ASSERT_EQUAL_UINT16(sizeof test_payload, payload_len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(test_payload, parsed_payload, payload_len);
}

/* --- Test: frame too small or invalid magic/version --- */
void test_parse_invalid_frame(void) {
    // invalid magic
    buffer[0] = (uint8_t)(PROTO_MAGIC & 0xFF);
    buffer[1] = (uint8_t)((PROTO_MAGIC >> 8) & 0xFF);
    buffer[2] = PROTO_VERSION;
    const uint8_t* parsed_payload = NULL;
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
    size_t written = proto_write_frame(buffer, sizeof buffer, 0x01, NULL, 0, 0, 0);
    TEST_ASSERT_TRUE(written > 0);

    const uint8_t* parsed_payload = NULL;
    // remove last byte to simulate incomplete frame
    size_t parsed = proto_parse_frame(buffer, written - 1, &hdr, &parsed_payload, &payload_len);
    TEST_ASSERT_EQUAL_size_t(0, parsed);
}

/* --- Test: proto_apply_commands --- */
void test_apply_commands(void) {
    uint8_t streaming = 0;

    uint8_t cmds[] = {PROTO_CMD_START, 0x00, PROTO_CMD_STOP};
    proto_apply_commands(cmds, sizeof cmds, &streaming);
    TEST_ASSERT_EQUAL_UINT8(0, streaming);  // last command STOP sets to 0

    cmds[0] = PROTO_CMD_START;
    proto_apply_commands(cmds, 1, &streaming);
    TEST_ASSERT_EQUAL_UINT8(1, streaming);
}

/* --- Test: payload length clipping --- */
void test_write_frame_max_payload(void) {
    uint8_t test_payload_buf[PROTO_MAX_PAYLOAD + 10];
    memset(test_payload_buf, 0x55, sizeof test_payload_buf);

    size_t written = proto_write_frame(buffer, sizeof buffer, 0x01, test_payload_buf,
                                       sizeof test_payload_buf, 0, 0);
    // proto_write_frame should clip payload to PROTO_MAX_PAYLOAD
    TEST_ASSERT_EQUAL_size_t(PROTO_MAX_PAYLOAD + PROTO_HDR_LEN + PROTO_CRC_LEN, written);

    const uint8_t* parsed_payload = NULL;
    (void)proto_parse_frame(buffer, written, &hdr, &parsed_payload, &payload_len);
    TEST_ASSERT_EQUAL_UINT16(PROTO_MAX_PAYLOAD, payload_len);
}

/* --- Main --- */
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_write_and_parse_frame);
    RUN_TEST(test_parse_invalid_frame);
    RUN_TEST(test_parse_incomplete_frame);
    RUN_TEST(test_apply_commands);
    RUN_TEST(test_write_frame_max_payload);
    return UNITY_END();
}
