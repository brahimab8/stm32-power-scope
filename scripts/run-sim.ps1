# scripts/run-sim.ps1
#
# Build and run the simulation firmware target on Windows.
#
# Examples:
#   .\scripts\run-sim.ps1
#   .\scripts\run-sim.ps1 -Config Release

[CmdletBinding()]
param(
  [ValidateSet("Debug", "Release")]
  [string]$Config = "Debug",

  [string]$BuildDir = "build-sim"
)

$ErrorActionPreference = "Stop"

Write-Host "Simulation build"
Write-Host "  Config   : $Config"
Write-Host "  Build dir: $BuildDir"

cmake -S . -B $BuildDir -DBUILD_FIRMWARE=ON -DPS_TARGET=sim -DPS_TRANSPORT=TCP

cmake --build $BuildDir --target powerscope-fw-sim --config $Config --parallel

$exeCandidates = @(
  (Join-Path $BuildDir (Join-Path "firmware/sim/$Config" "powerscope-fw-sim.exe")),
  (Join-Path $BuildDir "firmware/sim/powerscope-fw-sim.exe"),
  (Join-Path $BuildDir "firmware/sim/powerscope-fw-sim")
)

$simExe = $exeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $simExe) {
  throw "Simulation executable not found. Looked in: $($exeCandidates -join ', ')"
}

Write-Host "Starting simulator on TCP 127.0.0.1:9000"
Write-Host "Host CLI example:"
Write-Host "  python -m host.cli status --transport tcp --ip 127.0.0.1 --port 9000"

& $simExe
