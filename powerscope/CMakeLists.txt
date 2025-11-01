# powerscope/CMakeLists.txt
cmake_minimum_required(VERSION 3.20)

# Compiler flags (GCC/Clang)
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
  list(APPEND C_FLAGS_HOST ${C_WARN} ${C_SEC} ${C_DBG})
  if (ENABLE_WERROR)
    list(APPEND C_FLAGS_HOST -Werror)
  endif()
endif()

# ===== Library =====

file(GLOB_RECURSE LIB_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/*.c)

# Exclude ps_app.c, ps_core.c, ps_sensor_adapter.c
list(FILTER LIB_SOURCES EXCLUDE REGEX ".*/ps_app\\.c$")
list(FILTER LIB_SOURCES EXCLUDE REGEX ".*/ps_core\\.c$")
list(FILTER LIB_SOURCES EXCLUDE REGEX ".*/ps_sensor_adapter\\.c$")

add_library(powerscope STATIC ${LIB_SOURCES})

target_include_directories(powerscope PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_compile_options(powerscope PRIVATE ${C_FLAGS_HOST})
set_target_properties(powerscope PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON)

# ===== Tests =====
if (BUILD_TESTING)
    file(GLOB TEST_FILES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_*.c)

    foreach(test_file IN LISTS TEST_FILES)
        # Extract filename without extension
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
        target_compile_options(${test_name} PRIVATE ${C_FLAGS_HOST})

        # Add CTest entry
        add_test(NAME ${test_name} COMMAND ${test_name})

        # Coverage flags
        if (ENABLE_COVERAGE AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
            # Only instrument library files except excluded ones
            target_compile_options(powerscope PRIVATE --coverage)
            target_link_options(powerscope PRIVATE --coverage)

            # Test executables coverage
            target_compile_options(${test_name} PRIVATE --coverage)
            target_link_options(${test_name} PRIVATE --coverage)
        endif()
    endforeach()
endif()
