cmake_minimum_required(VERSION 3.20)
project(powerscope_fw_stm32l432_nucleo_usb_cdc LANGUAGES C ASM)

set(FW_TARGET powerscope-fw)
get_filename_component(BOARD_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(CUBE_ROOT ${BOARD_ROOT}/cube)
include(${BOARD_ROOT}/cmake/stm32l432_toolchain.cmake)
include(${BOARD_ROOT}/cmake/stm32l432_openocd.cmake)
include(${BOARD_ROOT}/cmake/stm32l432_target_setup.cmake)

ps_stm32l432_add_mcu_flags()
ps_stm32l432_configure_openocd_cache()

# -----------------------------
# Linker script + startup
# -----------------------------
set(LINKER_SCRIPT ${CUBE_ROOT}/STM32L432KCUX_FLASH.ld)
set(CORE_EXCLUDE_REGEX
  ".*/(main|ps_app|board_stm32l4|stm32l4xx_it|comm_uart|comm_usb_cdc)\\.c$|.*/sensors/.*\\.c$"
)
ps_stm32l432_collect_sources("${CUBE_ROOT}" "${CORE_EXCLUDE_REGEX}" STARTUP_ASM CORE_SRCS HAL_SRCS)

file(GLOB_RECURSE VARIANT_SRCS CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_LIST_DIR}/src/*.c
)

add_executable(${FW_TARGET}
  ${STARTUP_ASM}
  ${CORE_SRCS}
  ${HAL_SRCS}
  ${VARIANT_SRCS}
)

file(GLOB_RECURSE USB_DEVICE_SRCS CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_LIST_DIR}/USB_DEVICE/*.c
)
file(GLOB_RECURSE USB_MW_CORE_SRCS CONFIGURE_DEPENDS
  ${CUBE_ROOT}/Middlewares/ST/STM32_USB_Device_Library/Core/Src/*.c
)
file(GLOB_RECURSE USB_MW_CDC_SRCS CONFIGURE_DEPENDS
  ${CUBE_ROOT}/Middlewares/ST/STM32_USB_Device_Library/Class/CDC/Src/*.c
)

target_sources(${FW_TARGET} PRIVATE
  ${USB_DEVICE_SRCS}
  ${USB_MW_CORE_SRCS}
  ${USB_MW_CDC_SRCS}
)

target_include_directories(${FW_TARGET} PRIVATE
  ${CMAKE_CURRENT_LIST_DIR}/include
  ${CMAKE_CURRENT_LIST_DIR}/USB_DEVICE/App
  ${CMAKE_CURRENT_LIST_DIR}/USB_DEVICE/Target
  ${CUBE_ROOT}/Middlewares/ST/STM32_USB_Device_Library/Core/Inc
  ${CUBE_ROOT}/Middlewares/ST/STM32_USB_Device_Library/Class/CDC/Inc
)

# -----------------------------
# Compile definitions
# -----------------------------
target_compile_definitions(${FW_TARGET} PRIVATE
  PS_USE_USB_CDC=1
)

ps_stm32l432_apply_target_base(${FW_TARGET} "${LINKER_SCRIPT}")
ps_stm32l432_apply_cmsis_layer(${FW_TARGET} "${BOARD_ROOT}")
ps_stm32l432_apply_hal_layer(${FW_TARGET} "${CUBE_ROOT}")
ps_stm32l432_link_project_libs(${FW_TARGET})
ps_stm32l432_add_openocd_targets(${FW_TARGET})
