/**
 * @file    byteio.h
 * @brief   Little-endian byte read/write helpers.
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Read unsigned integers in little-endian */
static inline uint16_t byteio_rd_u16le(const uint8_t* src) {
    return (uint16_t)src[0] | ((uint16_t)src[1] << 8);
}

static inline uint32_t byteio_rd_u32le(const uint8_t* src) {
    return (uint32_t)src[0] | ((uint32_t)src[1] << 8) | ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static inline int32_t byteio_rd_i32le(const uint8_t* src) {
    return (int32_t)byteio_rd_u32le(src);
}

/* Write unsigned integers in little-endian */
static inline void byteio_wr_u16le(uint8_t* dst, uint16_t v) {
    dst[0] = (uint8_t)(v & 0xFFU);
    dst[1] = (uint8_t)((v >> 8) & 0xFFU);
}

static inline void byteio_wr_u32le(uint8_t* dst, uint32_t v) {
    dst[0] = (uint8_t)(v & 0xFFU);
    dst[1] = (uint8_t)((v >> 8) & 0xFFU);
    dst[2] = (uint8_t)((v >> 16) & 0xFFU);
    dst[3] = (uint8_t)((v >> 24) & 0xFFU);
}

/* Signed writes delegate to unsigned with a well-defined cast */
static inline void byteio_wr_i32le(uint8_t* dst, int32_t v) {
    byteio_wr_u32le(dst, (uint32_t)v);
}

#ifdef __cplusplus
}
#endif
