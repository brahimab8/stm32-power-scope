# scripts/run-sim.ps1
#
# Build and run the simulation firmware target on Windows.
#
# Examples:
#   .\scripts\run-sim.ps1
#   .\scripts\run-sim.ps1 -Config Release
#   .\scripts\run-sim.ps1 -SimVerbose

[CmdletBinding()]
param(
  [ValidateSet("Debug", "Release")]
  [string]$Config = "Debug",

  [string]$BuildDir = "build-sim",

  [ValidateRange(1, 65535)]
  [int]$SimPort = 9000,

  [switch]$SimVerbose
)

$ErrorActionPreference = "Stop"

Write-Host "Simulation build"
Write-Host "  Config   : $Config"
Write-Host "  Build dir: $BuildDir"
Write-Host "  SimPort  : $SimPort"
Write-Host "  SimVerbose: $SimVerbose"

$simVerboseCMake = if ($SimVerbose) { "ON" } else { "OFF" }

cmake -S . -B $BuildDir -DBUILD_FIRMWARE=ON -DPS_TARGET=sim -DPS_SIM_VERBOSE=$simVerboseCMake

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

Write-Host "Starting simulator on TCP 127.0.0.1:$SimPort"
Write-Host ""
Write-Host "In another terminal, run daemon + ctl:"
Write-Host "  python -m host.daemon --host 127.0.0.1 --port 8765"
Write-Host "  python -m host.clients.ctl --daemon-url http://127.0.0.1:8765 boards connect --board-id sim1 --transport tcp --transport-arg ip 127.0.0.1 --transport-arg port $SimPort"
Write-Host "  python -m host.clients.ctl --daemon-url http://127.0.0.1:8765 board sim1 sensors"
Write-Host "  python -m host.clients.ctl --daemon-url http://127.0.0.1:8765 board sim1 start --sensor 1"
Write-Host "  python -m host.clients.ctl --daemon-url http://127.0.0.1:8765 board sim1 stop --sensor 1"

& $simExe --port $SimPort
