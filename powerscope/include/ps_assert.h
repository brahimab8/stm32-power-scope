/**
 * @file    ps_assert.h
 * @brief   Compile-time assertion helper.
 *
 * Provides a unified macro ::PS_STATIC_ASSERT usable from both C++ and C.
 *
 * This header introduces **no runtime cost**; all checks are compile-time.
 */

#pragma once

/**
 * @def PS_STATIC_ASSERT(cond, msg)
 * @brief Compile-time assertion.
 *
 * @param cond  Constant expression evaluated at compile time. Non-zero passes.
 * @param msg   Diagnostic string shown by the compiler if the assertion fails.
 *
 * Usage example:
 * @code
 * PS_STATIC_ASSERT(sizeof(hdr_t) == 16u, "hdr_t must be 16 bytes");
 * @endcode
 */
#ifdef __cplusplus
#define PS_STATIC_ASSERT(cond, msg) static_assert(cond, msg)
#else
#if defined(__STDC_VERSION__) && (__STDC_VERSION__ >= 201112L)
#define PS_STATIC_ASSERT(cond, msg) _Static_assert(cond, msg)
#else
#define PS_STATIC_ASSERT_GLUE_(a, b) a##b
#define PS_STATIC_ASSERT_GLUE(a, b) PS_STATIC_ASSERT_GLUE_(a, b)
#define PS_STATIC_ASSERT(cond, msg) typedef char PS_STATIC_ASSERT_GLUE(ps_static_assert_line_, __LINE__)[(cond) ? 1 : -1]
#endif
#endif
