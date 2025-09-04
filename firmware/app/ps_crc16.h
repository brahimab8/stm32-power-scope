/**
 * @file ps_crc16.h
 * @brief CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF), little-endian trailer.
 *
 * Use @ref ps_crc16_le() to update a running CRC over a byte buffer.
 * For a one-shot CRC of a whole message, call it with seed = @ref PS_CRC16_INIT.
 *
 * On the wire, append the CRC **little-endian** (low byte first).
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** @brief CRC polynomial for CRC-16/CCITT-FALSE. */
#define PS_CRC16_POLY 0x1021u
/** @brief Initial value for CRC-16/CCITT-FALSE. */
#define PS_CRC16_INIT 0xFFFFu
/** @brief Size of the CRC trailer in bytes. */
#define PS_CRC16_LEN 2u

/**
 * @brief Update CRC-16/CCITT-FALSE over a buffer.
 *
 * @param data Pointer to bytes.
 * @param len  Number of bytes.
 * @param crc  Seed (use @ref PS_CRC16_INIT for a fresh computation; or pass a running CRC to
 * continue).
 * @return Updated CRC value.
 */
static inline uint16_t ps_crc16_le(const void* data, size_t len, uint16_t crc) {
    const uint8_t* p = (const uint8_t*)data;
    while (len--) {
        crc ^= (uint16_t)(*p++) << 8;
        for (int i = 0; i < 8; ++i)
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ PS_CRC16_POLY) : (uint16_t)(crc << 1);
    }
    return crc;
}

#ifdef __cplusplus
}
#endif
