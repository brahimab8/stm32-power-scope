include_guard(GLOBAL)

# Store the OpenOCD defaults in the cache so flash and debug targets can share one board configuration.
function(ps_stm32l432_configure_openocd_cache)
  option(ENABLE_OPENOCD_TARGETS "Enable OpenOCD flash/debug targets" ON)
  set(OPENOCD_INTERFACE_CFG "interface/stlink.cfg" CACHE STRING "OpenOCD interface cfg")
  set(OPENOCD_TARGET_CFG    "target/stm32l4x.cfg"  CACHE STRING "OpenOCD target cfg")
  set(OPENOCD_ADAPTER_SPEED "4000"                 CACHE STRING "OpenOCD adapter speed (kHz)")
endfunction()

# Create the optional flash and debug-server targets when OpenOCD is available.
function(ps_stm32l432_add_openocd_targets FW_TARGET)
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
endfunction()
