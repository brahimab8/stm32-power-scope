# scripts/build-fw.ps1
#
# Build firmware on Windows (multi-target, target-path selected).
#
# Examples:
#   .\scripts\build-fw.ps1
#   .\scripts\build-fw.ps1 -Config Debug
#   .\scripts\build-fw.ps1 -Target stm32l432_nucleo/cube/uart
#   .\scripts\build-fw.ps1 -Target stm32l432_nucleo/cube/usb_cdc -DebugServer
#   .\scripts\build-fw.ps1 -Flash
#
# Notes:
# - flash/debug-server are target-defined CMake targets and typically require OpenOCD in PATH.

[CmdletBinding()]
param(
  [ValidateSet("Debug","Release")]
  [string]$Config = "Release",

  [string]$Target = "stm32l432_nucleo/cube/uart",

  [string]$Toolchain = "cmake/arm-none-eabi-toolchain.cmake",

  [switch]$Flash,
  [switch]$DebugServer
)

$ErrorActionPreference = "Stop"

# Ensure environment is set up (CMake/Ninja/Arm GNU tools/OpenOCD in PATH)
. "$PSScriptRoot\env.ps1"

# Build directory per target + config
$buildDir = Join-Path "build-fw" (Join-Path $Target $Config)

# Firmware debug flag
$fwDebug = if ($Config -eq "Debug") { "ON" } else { "OFF" }

Write-Host "==> Firmware build" -ForegroundColor Green
Write-Host "    Target    : $Target"
Write-Host "    Config    : $Config"
Write-Host "    Toolchain : $Toolchain"
Write-Host "    Build dir : $buildDir"

# Configure
cmake -S . -B $buildDir -G Ninja `
  --fresh `
  --toolchain $Toolchain `
  "-DCMAKE_BUILD_TYPE=$($Config)" `
  "-DBUILD_FIRMWARE=ON" `
  "-DPS_TARGET=$($Target)" `
  "-DFW_DEBUG=$($fwDebug)" `
  "-DBUILD_TESTING=OFF"

# Build
cmake --build $buildDir --parallel

# Optional: Flash / Debug server
if ($Flash -or $DebugServer) {
  if (-not (Test-Path (Join-Path $buildDir "build.ninja"))) {
    throw "Build directory missing or not configured: $buildDir"
  }
}

if ($Flash) {
  Write-Host "==> Flashing firmware ($Target / $Config)..." -ForegroundColor Cyan
  cmake --build $buildDir --target flash
}

if ($DebugServer) {
  Write-Host "==> Starting debug server ($Target / $Config)..." -ForegroundColor Cyan
  cmake --build $buildDir --target debug-server
}
