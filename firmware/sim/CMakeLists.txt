cmake_minimum_required(VERSION 3.20)
project(powerscope_fw_sim LANGUAGES C)

set(FW_TARGET powerscope-fw-sim)

option(PS_SIM_VERBOSE "Enable simulator TCP debug logs" OFF)

file(GLOB_RECURSE SIM_SRCS CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_SOURCE_DIR}/*.c
)

add_executable(${FW_TARGET}
  ${SIM_SRCS}
)

target_include_directories(${FW_TARGET} PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${CMAKE_CURRENT_SOURCE_DIR}/sensors
  ${CMAKE_CURRENT_SOURCE_DIR}/sensors/ina219
  ${CMAKE_SOURCE_DIR}/powerscope/include
  ${CMAKE_SOURCE_DIR}
)

target_compile_definitions(${FW_TARGET} PRIVATE
  PS_USE_TCP=1
  $<$<BOOL:${PS_SIM_VERBOSE}>:PS_SIM_VERBOSE=1>
)

target_link_libraries(${FW_TARGET} PRIVATE
  powerscope
  drivers
)

if (WIN32)
  target_link_libraries(${FW_TARGET} PRIVATE ws2_32)
endif()
