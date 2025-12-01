# STM32 Firmware – Debugging Guide (OpenOCD + GDB)

This document describes how to **debug the STM32L432 firmware** using
**OpenOCD** and **arm-none-eabi-gdb**.

Basic setup, build, and flashing instructions are covered in the **README**.

---

## Supported Workflows

* **Windows**: PowerShell scripts (recommended)
* **Unix-like systems**: Makefile (Linux / macOS / WSL / CI)

Debug builds follow the same **PS_TARGET / PS_TRANSPORT** selection as normal builds.

---

## Prerequisites

Before debugging, ensure you can:

* install the required toolchain
* set up the firmware build environment
* build the firmware
* flash the firmware to the target device

Follow the **README – Quick Start** before proceeding.

---

## Debug Build

Debugging requires a firmware build with symbols.

### Build Debug Firmware (Windows)

```powershell
.\scripts\env.ps1
.\scripts\build-fw.ps1 -Config Debug
```

Output directory:

```
build-fw/<PS_TARGET>/<PS_TRANSPORT>/Debug/
```

(Default: `build-fw/stm32l432_nucleo/UART/Debug/`)

The Debug configuration:

* uses the same MCU/ABI flags as Release
* enables debug symbols (`-g3`)
* uses debug-friendly optimization (`-Og`)

---

## Debugging Architecture

Debugging is performed using:

* **OpenOCD** — GDB server and SWD interface (via ST-LINK)
* **arm-none-eabi-gdb** — debugger client

The workflow uses **two terminals**:

1. one running the OpenOCD debug server
2. one running the GDB client

---

## Debugging Workflow (Windows)

### Step 1: Start the Debug Server

Open **Terminal 1**:

```powershell
.\scripts\env.ps1
.\scripts\build-fw.ps1 -Config Debug -DebugServer
```

This will:

* build the Debug firmware if needed
* start OpenOCD
* open a GDB server on `localhost:3333`
* block the terminal (expected)

Do **not** close this terminal while debugging.

---

### Step 2: Attach GDB

Open **Terminal 2**:

```powershell
.\scripts\env.ps1
arm-none-eabi-gdb .\build-fw\stm32l432_nucleo\UART\Debug\powerscope-fw
```

Inside GDB:

```gdb
target remote localhost:3333
monitor reset halt
load
continue
```

You can now:

* set breakpoints
* step through code
* inspect variables
* halt, reset, and continue execution

> Flashing during debugging is performed by the `load` command.

---

## Common Debug Workflows

### Build, flash, and debug (most common)

```powershell
.\scripts\build-fw.ps1 -Config Debug -Flash -DebugServer
```

Then attach GDB in a second terminal.

---

### Debug already-flashed firmware

```powershell
.\scripts\build-fw.ps1 -Config Debug -DebugServer
```

Attach GDB and **omit the `load` command**.

---

## Unix / Makefile Debug Workflow

For Linux, macOS, WSL, and CI environments.

> The Arm toolchain and OpenOCD must be installed manually.

### Start Debug Server

```sh
make fw-debug FW_CONFIG=Debug TOOLCHAIN=cmake/arm-none-eabi-toolchain.cmake
```

Attach GDB:

```sh
arm-none-eabi-gdb build-fw/stm32l432_nucleo/UART/Debug/powerscope-fw
```

Inside GDB:

```gdb
target remote localhost:3333
monitor reset halt
continue
```

---

## Notes

* OpenOCD communicates with the target via **ST-LINK (SWD)**
* The debug server listens on `localhost:3333` by default
* Only one GDB client should be attached at a time

