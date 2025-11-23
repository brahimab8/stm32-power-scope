# firmware/CMakeLists.txt for the powerscope repository

cmake_minimum_required(VERSION 3.20)

if (NOT DEFINED PS_TARGET OR PS_TARGET STREQUAL "")
  message(FATAL_ERROR "PS_TARGET is not set. Example: -DPS_TARGET=stm32l432_nucleo -DPS_TRANSPORT=UART")
endif()

set(_ps_target_dir "${CMAKE_CURRENT_SOURCE_DIR}/${PS_TARGET}")

if (NOT EXISTS "${_ps_target_dir}/CMakeLists.txt")
  file(GLOB _children LIST_DIRECTORIES true RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}"
       "${CMAKE_CURRENT_SOURCE_DIR}/*")

  set(_targets "")
  foreach(_c IN LISTS _children)
    if (IS_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/${_c}" AND
        EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_c}/CMakeLists.txt")
      list(APPEND _targets "${_c}")
    endif()
  endforeach()

  list(SORT _targets)
  string(REPLACE ";" ", " _targets_str "${_targets}")

  message(FATAL_ERROR
    "Unknown PS_TARGET='${PS_TARGET}'. Available targets: ${_targets_str}\n"
    "Example: -DPS_TARGET=stm32l432_nucleo -DPS_TRANSPORT=UART"
  )
endif()

add_subdirectory("${PS_TARGET}")
