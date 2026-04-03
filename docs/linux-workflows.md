# Linux Workflows (Build, Flash, Test)

This page documents Linux-first workflows for this repository.
It focuses on `make` targets from the root `Makefile`.

## Prerequisites

Install the tools you need for your workflow:

- CMake 3.20+
- Ninja
- GCC/Clang (host-native builds)
- Python 3.10+ (for host tests and daemon/CLI)
- `arm-none-eabi-*` toolchain (for STM32 firmware targets)
- OpenOCD (for `fw-flash` and `fw-debug`)

Optional host setup:

```sh
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Native C Core Build and Test

Build native libraries and test binaries:

```sh
make build
```

Run CTest suite:

```sh
make test
```

Coverage build (requires `gcovr`):

```sh
make coverage
```

## Firmware Simulator (Host-Native)

Build simulator target:

```sh
make sim-build
```

Run simulator:

```sh
make sim-run
```

This uses the native compiler and does not require the ARM toolchain.

## STM32 Firmware Build (Cross-Compile)

Default STM32 target (`stm32l432_nucleo/cube/uart`):

```sh
make fw-build
```

Build USB CDC variant:

```sh
make fw-build PS_TARGET=stm32l432_nucleo/cube/usb_cdc
```

Debug firmware build:

```sh
make fw-build FW_CONFIG=Debug FW_DEBUG=ON
```

Output path pattern:

```text
build-fw/<PS_TARGET>/<FW_CONFIG>/firmware/<PS_TARGET>/
```

## Flash and Debug (STM32)

Flash firmware to board:

```sh
make fw-flash PS_TARGET=stm32l432_nucleo/cube/uart
```

Start OpenOCD debug server:

```sh
make fw-debug PS_TARGET=stm32l432_nucleo/cube/uart FW_CONFIG=Debug
```

For GDB attachment flow, see `docs/firmware-debug.md`.

## Toolchain Selection Notes

- ARM firmware targets use `cmake/arm-none-eabi-toolchain.cmake` by default.
- Non-ARM firmware targets listed in `NON_ARM_TARGETS` skip cross-toolchain usage.
- Default `NON_ARM_TARGETS` is `sim`.

Example for a custom host-native firmware target:

```sh
make fw-build PS_TARGET=host/foo NON_ARM_TARGETS="sim host/foo"
```

## Cleaning

Clean native build:

```sh
make clean
```

Clean current firmware build output:

```sh
make fw-clean
```

Clean all firmware outputs:

```sh
make fw-clean-all
```

Clean simulator build output:

```sh
make sim-clean
```
