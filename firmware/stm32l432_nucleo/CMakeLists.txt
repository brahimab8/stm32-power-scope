# Firmware CMakeLists.txt for STM32L432 Nucleo board
cmake_minimum_required(VERSION 3.20)
project(powerscope_fw LANGUAGES C ASM)

set(FW_TARGET powerscope-fw)

# -----------------------------
# Transport validation
# -----------------------------
if (NOT DEFINED PS_TRANSPORT OR PS_TRANSPORT STREQUAL "")
  set(PS_TRANSPORT "UART" CACHE STRING "Firmware transport (UART or USB_CDC)" FORCE)
endif()

if (NOT (PS_TRANSPORT STREQUAL "UART" OR PS_TRANSPORT STREQUAL "USB_CDC"))
  message(FATAL_ERROR "Invalid PS_TRANSPORT='${PS_TRANSPORT}'. Use UART or USB_CDC.")
endif()

# -----------------------------
# MCU/ABI flags (STM32L432 = Cortex-M4F hard-float)
# -----------------------------
add_library(ps_mcu_flags INTERFACE)
target_compile_options(ps_mcu_flags INTERFACE
  -mcpu=cortex-m4
  -mthumb
  -mfpu=fpv4-sp-d16
  -mfloat-abi=hard
)
target_link_options(ps_mcu_flags INTERFACE
  -mcpu=cortex-m4
  -mthumb
  -mfpu=fpv4-sp-d16
  -mfloat-abi=hard
)

# -----------------------------
# Target configuration options
# -----------------------------
option(ENABLE_OPENOCD_TARGETS "Enable OpenOCD flash/debug targets" ON)
set(OPENOCD_INTERFACE_CFG "interface/stlink.cfg" CACHE STRING "OpenOCD interface cfg")
set(OPENOCD_TARGET_CFG    "target/stm32l4x.cfg"  CACHE STRING "OpenOCD target cfg")
set(OPENOCD_ADAPTER_SPEED "4000"                 CACHE STRING "OpenOCD adapter speed (kHz)")

# -----------------------------
# Linker script + startup
# -----------------------------
set(LINKER_SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/STM32L432KCUX_FLASH.ld)

file(GLOB STARTUP_ASM ${CMAKE_CURRENT_SOURCE_DIR}/Core/Startup/startup_*.s)
if (STARTUP_ASM STREQUAL "")
  message(FATAL_ERROR "No startup_*.s found in ${CMAKE_CURRENT_SOURCE_DIR}/Core/Startup")
endif()

# -----------------------------
# Sources
# -----------------------------
file(GLOB_RECURSE CORE_SRCS CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_SOURCE_DIR}/Core/Src/*.c
)

# -----------------------------
# Transport-specific sources
# -----------------------------
if (NOT PS_TRANSPORT STREQUAL "USB_CDC")
  list(FILTER CORE_SRCS EXCLUDE REGEX ".*/comm_usb_cdc\\.c$")
endif()

if (NOT PS_TRANSPORT STREQUAL "UART")
  list(FILTER CORE_SRCS EXCLUDE REGEX ".*/comm_uart\\.c$")
endif()

file(GLOB_RECURSE HAL_SRCS CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/STM32L4xx_HAL_Driver/Src/*.c
)

add_executable(${FW_TARGET}
  ${STARTUP_ASM}
  ${CORE_SRCS}
  ${HAL_SRCS}
)

# USB sources (only when using USB CDC transport)
if (PS_TRANSPORT STREQUAL "USB_CDC")
  file(GLOB_RECURSE USB_DEVICE_SRCS CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/USB_DEVICE/*.c
  )

  file(GLOB_RECURSE USB_MW_CORE_SRCS CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Device_Library/Core/Src/*.c
  )
  file(GLOB_RECURSE USB_MW_CDC_SRCS CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Device_Library/Class/CDC/Src/*.c
  )

  target_sources(${FW_TARGET} PRIVATE
    ${USB_DEVICE_SRCS}
    ${USB_MW_CORE_SRCS}
    ${USB_MW_CDC_SRCS}
  )
endif()

# -----------------------------
# Include directories
# -----------------------------
target_include_directories(${FW_TARGET} PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/Core/Inc

  # HAL directory
  ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/STM32L4xx_HAL_Driver/Inc
  ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/STM32L4xx_HAL_Driver/Inc/Legacy

  # CMSIS directories
  ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/CMSIS/Include
  ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/CMSIS/Device/ST/STM32L4xx/Include

  # powerscope headers
  ${CMAKE_SOURCE_DIR}/powerscope/include
)

if (PS_TRANSPORT STREQUAL "USB_CDC")
  target_include_directories(${FW_TARGET} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/USB_DEVICE/App
    ${CMAKE_CURRENT_SOURCE_DIR}/USB_DEVICE/Target
    ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Device_Library/Core/Inc
    ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Device_Library/Class/CDC/Inc
  )
endif()

# -----------------------------
# Compile definitions
# -----------------------------
target_compile_definitions(${FW_TARGET} PRIVATE
  USE_HAL_DRIVER
  STM32L432xx
)

if (PS_TRANSPORT STREQUAL "UART")
  target_compile_definitions(${FW_TARGET} PRIVATE PS_USE_UART=1)
elseif (PS_TRANSPORT STREQUAL "USB_CDC")
  target_compile_definitions(${FW_TARGET} PRIVATE PS_USE_USB_CDC=1)
else()
  message(FATAL_ERROR "Invalid PS_TRANSPORT='${PS_TRANSPORT}'. Use UART or USB_CDC.")
endif()

# -----------------------------
# Compile + link options
# -----------------------------
target_compile_options(${FW_TARGET} PRIVATE
  -ffunction-sections -fdata-sections
)

target_link_options(${FW_TARGET} PRIVATE
  -T${LINKER_SCRIPT}
  -Wl,--gc-sections
  -Wl,-Map=${FW_TARGET}.map
)

if (FW_DEBUG)
  target_compile_options(${FW_TARGET} PRIVATE -Og -g3)
  target_link_options(${FW_TARGET} PRIVATE -g3)
endif()

# Apply CPU/ABI flags to the firmware and to the powerscope library
target_link_libraries(${FW_TARGET} PRIVATE ps_mcu_flags powerscope)

target_compile_options(powerscope PRIVATE
  $<TARGET_PROPERTY:ps_mcu_flags,INTERFACE_COMPILE_OPTIONS>
)

# -----------------------------
# Post-build artifacts
# -----------------------------
add_custom_command(TARGET ${FW_TARGET} POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary
          $<TARGET_FILE:${FW_TARGET}>
          $<TARGET_FILE_DIR:${FW_TARGET}>/${FW_TARGET}.bin
  COMMENT "Generating ${FW_TARGET}.bin"
)

add_custom_command(TARGET ${FW_TARGET} POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O ihex
          $<TARGET_FILE:${FW_TARGET}>
          $<TARGET_FILE_DIR:${FW_TARGET}>/${FW_TARGET}.hex
  COMMENT "Generating ${FW_TARGET}.hex"
)

# -----------------------------
# OpenOCD helper targets (optional)
# -----------------------------
find_program(OPENOCD_EXE openocd)

if (ENABLE_OPENOCD_TARGETS AND OPENOCD_EXE)
  add_custom_target(flash
    DEPENDS ${FW_TARGET}
    COMMAND ${OPENOCD_EXE}
      -f ${OPENOCD_INTERFACE_CFG}
      -c "transport select hla_swd"
      -c "adapter speed ${OPENOCD_ADAPTER_SPEED}"
      -c "gdb_port disabled"
      -f ${OPENOCD_TARGET_CFG}
      -c "program $<TARGET_FILE:${FW_TARGET}> verify reset exit"
    COMMENT "Flashing ${FW_TARGET} via OpenOCD"
  )

  add_custom_target(debug-server
    COMMAND ${OPENOCD_EXE}
      -f ${OPENOCD_INTERFACE_CFG}
      -c "transport select hla_swd"
      -c "adapter speed ${OPENOCD_ADAPTER_SPEED}"
      -f ${OPENOCD_TARGET_CFG}
    COMMENT "Starting OpenOCD GDB server on port 3333 (Ctrl+C to stop)"
    USES_TERMINAL
  )
else()
  message(STATUS "OpenOCD not found or disabled; flash/debug-server targets will not be available.")
endif()
