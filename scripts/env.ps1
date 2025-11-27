# scripts/env.ps1

# Session-only environment setup for Windows builds.
#
# Current scope:
# - Assumes ARM/Cortex-M firmware builds using Arm GNU Toolchain (arm-none-eabi-*)
# - Tries to locate OpenOCD (only needed if the selected firmware target uses flash/debug-server)
# - Also locates CMake + Ninja
#
# Run:  .\scripts\env.ps1


# --- Helper: prepend a directory to PATH ---
function Prepend-Path([string]$dir) {
  if (-not $dir -or -not (Test-Path -LiteralPath $dir)) { return }

  # Canonicalize and normalize
  $n = (Resolve-Path -LiteralPath $dir).Path.TrimEnd('\','/')

  # Compare PATH entries exactly
  $entries = ($env:Path -split ';') | ForEach-Object { $_.Trim('"').TrimEnd('\','/') }
  if ($entries -notcontains $n) {
    $env:Path = "$n;$env:Path"
  }
}

function Find-First([string[]]$candidates) {
  foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c)) { return $c }
  }
  return $null
}

# --- winget shims (common for cmake/ninja/arm toolchain) ---
Prepend-Path "$env:LOCALAPPDATA\Microsoft\WinGet\Links"

# --- Toolchain: GNU Arm ---
if (-not (Get-Command arm-none-eabi-gcc -ErrorAction SilentlyContinue)) {
  # Arm GNU Toolchain (winget/manual installer layout):
  $armBases = @(
    "${env:ProgramFiles(x86)}\Arm GNU Toolchain arm-none-eabi",
    "$env:ProgramFiles\Arm GNU Toolchain arm-none-eabi"
  )

  foreach ($base in $armBases) {
    if (Test-Path -LiteralPath $base) {
      $bin = Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
             ForEach-Object { Join-Path $_.FullName "bin" } |
             Where-Object { Test-Path -LiteralPath $_ } |
             Sort-Object -Descending |
             Select-Object -First 1

      if ($bin) {
        Prepend-Path $bin
        break
      }
    }
  }
}

# Warn if not found
if (-not (Get-Command arm-none-eabi-gcc -ErrorAction SilentlyContinue)) {
  Write-Warning "arm-none-eabi-gcc not found. Install the Arm GNU Toolchain via winget and re-run this script."
}

# --- CMake (discovery; only if not already on PATH) ---
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
  $cmakeBin = Find-First @(
    "C:\Program Files\CMake\bin",
    "C:\Program Files (x86)\CMake\bin"
  )
  if ($cmakeBin) { Prepend-Path $cmakeBin }
}

# --- Ninja (discovery; only if not already on PATH) ---
if (-not (Get-Command ninja -ErrorAction SilentlyContinue)) {
  $ninjaBin = Find-First @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Ninja-build.Ninja_Microsoft.Winget.Source_8wekyb3d8bbwe",
    "$env:LOCALAPPDATA\Programs\Ninja",
    "C:\ProgramData\chocolatey\bin"
  )
  if ($ninjaBin) { Prepend-Path $ninjaBin }
}

# --- OpenOCD (discovery; only if not already on PATH) ---
if (-not (Get-Command openocd -ErrorAction SilentlyContinue)) {
  $openocdBin = Find-First @(
    "C:\msys64\ucrt64\bin",
    "C:\msys64\mingw64\bin",
    "C:\msys64\usr\bin"
  )
  if ($openocdBin) { Prepend-Path $openocdBin }
}

# --- Verification summary ---
Write-Host "Environment ready (session-only). Verifying tools..." -ForegroundColor Green

$tools = @("arm-none-eabi-gcc","cmake","ninja","openocd")
foreach ($t in $tools) {
  if (Get-Command $t -ErrorAction SilentlyContinue) {
    Write-Host "  OK: $t"
  } else {
    Write-Warning "  MISSING: $t"
  }
}

# Optional: show versions quickly
if (Get-Command arm-none-eabi-gcc -ErrorAction SilentlyContinue) { arm-none-eabi-gcc --version | Select-Object -First 1 }
if (Get-Command cmake -ErrorAction SilentlyContinue)            { cmake --version | Select-Object -First 1 }
if (Get-Command ninja -ErrorAction SilentlyContinue)            { ninja --version }
if (Get-Command openocd -ErrorAction SilentlyContinue)          { openocd --version | Select-Object -First 1 }
