# firmware/CMakeLists.txt for the powerscope repository

cmake_minimum_required(VERSION 3.20)

if (NOT DEFINED PS_TARGET OR PS_TARGET STREQUAL "")
  message(FATAL_ERROR "PS_TARGET is not set. Example: -DPS_TARGET=stm32l432_nucleo/cube/uart")
endif()

set(_ps_target "${PS_TARGET}")

set(_ps_target_dir "${CMAKE_CURRENT_SOURCE_DIR}/${_ps_target}")

if (NOT EXISTS "${_ps_target_dir}/CMakeLists.txt")
  file(GLOB_RECURSE _target_cmakelists RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}"
       "${CMAKE_CURRENT_SOURCE_DIR}/*/CMakeLists.txt")

  set(_targets "")
  foreach(_cmake_file IN LISTS _target_cmakelists)
    get_filename_component(_target_dir "${_cmake_file}" DIRECTORY)
    if (NOT _target_dir STREQUAL "")
      list(APPEND _targets "${_target_dir}")
    endif()
  endforeach()

  list(REMOVE_DUPLICATES _targets)
  list(SORT _targets)
  string(REPLACE ";" ", " _targets_str "${_targets}")

  message(FATAL_ERROR
    "Unknown PS_TARGET='${PS_TARGET}'. Available targets: ${_targets_str}\n"
    "Example: -DPS_TARGET=stm32l432_nucleo/cube/uart"
  )
endif()

add_subdirectory("${_ps_target}")
