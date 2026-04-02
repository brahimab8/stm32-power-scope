include_guard(GLOBAL)

# Define the Cortex-M4 ABI flags once so every STM32 firmware target uses the same compiler and linker settings.
function(ps_stm32l432_add_mcu_flags)
  if (NOT TARGET ps_mcu_flags)
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
  endif()
endfunction()
