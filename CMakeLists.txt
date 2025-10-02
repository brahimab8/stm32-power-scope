cmake_minimum_required(VERSION 3.20)
project(powerscope_repo LANGUAGES C)

# Global options (visible to subdirs)
option(ENABLE_COVERAGE "Enable coverage" OFF)
option(ENABLE_ANALYSIS "Enable static analysis" OFF)
option(ENABLE_WERROR   "Treat warnings as errors" OFF)

include(CTest)  # enables testing at root

# Build the HAL-free library/tests
add_subdirectory(powerscope)

# TODO: add ARM build
