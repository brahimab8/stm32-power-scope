include_guard(GLOBAL)

# Collect the CubeMX-generated startup, Core, and HAL sources from the cube folder.
function(ps_stm32l432_collect_sources CUBE_ROOT EXCLUDE_CORE_REGEX OUT_STARTUP OUT_CORE OUT_HAL)
  file(GLOB STARTUP_ASM ${CUBE_ROOT}/Core/Startup/startup_*.s)
  if (STARTUP_ASM STREQUAL "")
    message(FATAL_ERROR "No startup_*.s found in ${CUBE_ROOT}/Core/Startup")
  endif()

  file(GLOB_RECURSE CORE_SRCS CONFIGURE_DEPENDS
    ${CUBE_ROOT}/Core/Src/*.c
  )

  if (NOT "${EXCLUDE_CORE_REGEX}" STREQUAL "")
    list(FILTER CORE_SRCS EXCLUDE REGEX "${EXCLUDE_CORE_REGEX}")
  endif()

  file(GLOB_RECURSE HAL_SRCS CONFIGURE_DEPENDS
    ${CUBE_ROOT}/Drivers/STM32L4xx_HAL_Driver/Src/*.c
  )

  set(${OUT_STARTUP} ${STARTUP_ASM} PARENT_SCOPE)
  set(${OUT_CORE} ${CORE_SRCS} PARENT_SCOPE)
  set(${OUT_HAL} ${HAL_SRCS} PARENT_SCOPE)
endfunction()

# Apply linker and section options shared by all STM32L432 firmware targets.
function(ps_stm32l432_apply_target_base FW_TARGET LINKER_SCRIPT)
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

  target_link_libraries(${FW_TARGET} PRIVATE ps_mcu_flags)

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
endfunction()

# Apply the CMSIS include paths and MCU symbol shared by HAL and bare-metal variants.
function(ps_stm32l432_apply_cmsis_layer FW_TARGET BOARD_ROOT)
  target_include_directories(${FW_TARGET} PRIVATE
    ${BOARD_ROOT}/cmsis/Include
    ${BOARD_ROOT}/cmsis/Device/ST/STM32L4xx/Include
  )

  target_compile_definitions(${FW_TARGET} PRIVATE
    STM32L432xx
  )
endfunction()

# Apply STM32 HAL include paths and compile definition.
function(ps_stm32l432_apply_hal_layer FW_TARGET CUBE_ROOT)
  target_include_directories(${FW_TARGET} PRIVATE
    ${CUBE_ROOT}/Drivers/STM32L4xx_HAL_Driver/Inc
    ${CUBE_ROOT}/Drivers/STM32L4xx_HAL_Driver/Inc/Legacy
  )

  target_compile_definitions(${FW_TARGET} PRIVATE
    USE_HAL_DRIVER
  )
endfunction()

# Link shared project libraries and align their compile flags with the MCU ABI options.
function(ps_stm32l432_link_project_libs FW_TARGET)
  target_include_directories(${FW_TARGET} PRIVATE
    ${CMAKE_SOURCE_DIR}/powerscope/include
    ${CMAKE_SOURCE_DIR}
  )

  target_link_libraries(${FW_TARGET} PRIVATE powerscope drivers)

  target_compile_options(powerscope PRIVATE
    $<TARGET_PROPERTY:ps_mcu_flags,INTERFACE_COMPILE_OPTIONS>
  )

  target_compile_options(drivers PRIVATE
    $<TARGET_PROPERTY:ps_mcu_flags,INTERFACE_COMPILE_OPTIONS>
  )
endfunction()
