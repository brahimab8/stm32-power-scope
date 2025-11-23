# powerscope/CMakeLists.txt
cmake_minimum_required(VERSION 3.20)

# -----------------------------
# Compiler flags (GCC/Clang)
# -----------------------------
set(C_WARN
  -Wall -Wextra -Wpedantic
  -Wconversion -Wsign-conversion
  -Wshadow -Wformat=2 -Wundef
  -Wstrict-prototypes -Wold-style-definition
  -Wvla
)
set(C_SEC -fstack-protector-strong -D_FORTIFY_SOURCE=2 -fno-common)
set(C_DBG -O0 -g3)

set(C_FLAGS_HOST "")
if (CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
  # Always-on host flags
  list(APPEND C_FLAGS_HOST ${C_WARN} ${C_SEC})

  # Add debug flags for Debug builds
  if (CMAKE_BUILD_TYPE STREQUAL "Debug")
    list(APPEND C_FLAGS_HOST ${C_DBG})
  endif()

  if (ENABLE_WERROR)
    list(APPEND C_FLAGS_HOST -Werror)
  endif()
endif()

# -----------------------------
# Library
# -----------------------------
file(GLOB_RECURSE LIB_SOURCES CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_SOURCE_DIR}/src/*.c
)

# Exclude app/core/adapter ONLY for host unit tests.
if (BUILD_TESTING AND NOT BUILD_FIRMWARE)
  list(FILTER LIB_SOURCES EXCLUDE REGEX ".*/ps_app\\.c$")
  list(FILTER LIB_SOURCES EXCLUDE REGEX ".*/ps_core\\.c$")
  list(FILTER LIB_SOURCES EXCLUDE REGEX ".*/ps_sensor_adapter\\.c$")
endif()

add_library(powerscope STATIC ${LIB_SOURCES})

target_include_directories(powerscope PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Toolchain-specific flags:
# - For native builds: apply strict warnings + hardening (+ debug flags in Debug).
# - For firmware builds: the firmware target applies MCU/ABI flags to powerscope.
if (NOT BUILD_FIRMWARE)
  target_compile_options(powerscope PRIVATE ${C_FLAGS_HOST})
endif()

# Apply coverage instrumentation to the library once (native tests only)
if (BUILD_TESTING AND ENABLE_COVERAGE AND NOT BUILD_FIRMWARE AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(powerscope PRIVATE --coverage)
  target_link_options(powerscope PRIVATE --coverage)
endif()

# -----------------------------
# Tests
# -----------------------------
if (BUILD_TESTING)
  file(GLOB TEST_FILES CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_*.c
  )

  foreach(test_file IN LISTS TEST_FILES)
    get_filename_component(test_name ${test_file} NAME_WE)

    add_executable(${test_name}
      ${test_file}
      ${CMAKE_SOURCE_DIR}/third_party/unity/src/unity.c
    )

    target_include_directories(${test_name} PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/include
      ${CMAKE_SOURCE_DIR}/third_party/unity/src
    )

    target_link_libraries(${test_name} PRIVATE powerscope)

    # Host flags for test executables
    target_compile_options(${test_name} PRIVATE ${C_FLAGS_HOST})

    # Register with CTest
    add_test(NAME ${test_name} COMMAND ${test_name})

    # Coverage flags for test executables
    if (ENABLE_COVERAGE AND NOT BUILD_FIRMWARE AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
      target_compile_options(${test_name} PRIVATE --coverage)
      target_link_options(${test_name} PRIVATE --coverage)
    endif()
  endforeach()
endif()
