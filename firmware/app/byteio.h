/**
 * @file    byteio.h
 * @brief   Little-endian byte writers for protocol serialization.
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Write unsigned integers in little-endian */
static inline void byteio_wr_u16le(uint8_t *dst, uint16_t v)
{
    dst[0] = (uint8_t)(v & 0xFFu);
    dst[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static inline void byteio_wr_u32le(uint8_t *dst, uint32_t v)
{
    dst[0] = (uint8_t)(v & 0xFFu);
    dst[1] = (uint8_t)((v >> 8) & 0xFFu);
    dst[2] = (uint8_t)((v >> 16) & 0xFFu);
    dst[3] = (uint8_t)((v >> 24) & 0xFFu);
}

/* Signed writes delegate to unsigned with a well-defined cast */
static inline void byteio_wr_i32le(uint8_t *dst, int32_t v)
{
    byteio_wr_u32le(dst, (uint32_t)v);
}

#ifdef __cplusplus
}
#endif
