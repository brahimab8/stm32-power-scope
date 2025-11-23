# CMakeLists.txt for the entire powerscope repository
cmake_minimum_required(VERSION 3.20)
project(powerscope_repo LANGUAGES C ASM)

# -----------------------------
# Global options (visible to subdirs)
# -----------------------------
option(ENABLE_COVERAGE "Enable coverage" OFF)
option(ENABLE_ANALYSIS "Enable static analysis" OFF)
option(ENABLE_WERROR   "Treat warnings as errors" OFF)

option(BUILD_FIRMWARE  "Build firmware (selected by PS_TARGET)" OFF)
option(FW_DEBUG        "Build firmware with debug symbols" OFF)

# -----------------------------
# Firmware selector knobs
# -----------------------------
set(PS_TARGET "stm32l432_nucleo" CACHE STRING
    "Firmware target under firmware/ (e.g. stm32l432_nucleo)")
set(PS_TRANSPORT "UART" CACHE STRING
    "Firmware transport (UART or USB_CDC)")

# -----------------------------
# Testing support
# -----------------------------
include(CTest)  # enables testing at root

# -----------------------------
# Core library + unit tests (native build)
# -----------------------------
add_subdirectory(powerscope)

# -----------------------------
# Firmware build
# -----------------------------
if (BUILD_FIRMWARE)
  # Disable unit tests in firmware builds
  set(BUILD_TESTING OFF CACHE BOOL "Build unit tests" FORCE)
  add_subdirectory(firmware)
endif()
