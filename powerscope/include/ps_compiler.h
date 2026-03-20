/**
 * @file    ps_compiler.h
 * @brief   Compiler portability helpers.
 */

#pragma once

#if defined(_MSC_VER)
  #define PS_PACKED_BEGIN __pragma(pack(push, 1))
  #define PS_PACKED
  #define PS_PACKED_END __pragma(pack(pop))
#else
  #define PS_PACKED_BEGIN
  #define PS_PACKED __attribute__((packed))
  #define PS_PACKED_END
#endif
