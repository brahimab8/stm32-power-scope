# scripts/install-tools.ps1
#
# Optional convenience helper to install common tooling on Windows via winget.
# Intended for ARM/Cortex-M firmware development.
#
# Installs:
# - Arm GNU toolchain (arm-none-eabi-*)
# - CMake + Ninja
# - MSYS2 (used as an easy way to get OpenOCD)
#
# Notes:
# - OpenOCD is NOT installed by winget here; the script prints MSYS2 pacman steps if missing.
# - You can skip this script if you already have the tools installed.
#
# Run:  .\scripts\install-tools.ps1


$ErrorActionPreference = "Stop"

# --- Ensure winget is available ---
$windowsApps = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
if ((Test-Path "$windowsApps\winget.exe") -and ($env:Path -notlike "*WindowsApps*")) {
  $env:Path = "$windowsApps;$env:Path"
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw "winget not found. Install/repair 'App Installer' from Microsoft Store, then re-run."
}

function Install-Winget([string]$id) {
  Write-Host "==> $id" -ForegroundColor Cyan

  # winget list returns exit code 0 even if empty sometimes, so parse output.
  $installed = winget list --id $id --exact 2>$null | Out-String
  if ($installed -match [regex]::Escape($id)) {
    Write-Host "    already installed (skipping)" -ForegroundColor DarkGray
    return
  }

  winget install --id $id --exact --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    throw "winget install failed for $id (exit code $LASTEXITCODE)"
  }
}

Write-Host "Installing tools via winget..." -ForegroundColor Green

# --- GNU Arm toolchain ---
Install-Winget "Arm.GnuArmEmbeddedToolchain"

# --- Build tools ---
Install-Winget "Kitware.CMake"
Install-Winget "Ninja-build.Ninja"

# --- MSYS2 ---
Install-Winget "MSYS2.MSYS2"

# --- OpenOCD detection ---
$openocdFound = $false

if (Get-Command openocd -ErrorAction SilentlyContinue) {
  $openocdFound = $true
} else {
  foreach ($p in @(
    "C:\msys64\ucrt64\bin\openocd.exe",
    "C:\msys64\mingw64\bin\openocd.exe",
    "C:\msys64\usr\bin\openocd.exe"
  )) {
    if (Test-Path -LiteralPath $p) {
      $openocdFound = $true
      break
    }
  }
}

if ($openocdFound) {
  Write-Host "`nOpenOCD detected." -ForegroundColor Green
} else {
  Write-Host "`nNext step (once): install OpenOCD inside MSYS2 UCRT64:" -ForegroundColor Yellow
  Write-Host @"
1) Open **MSYS2 UCRT64** terminal
2) Run:
   pacman -Syu
   pacman -S mingw-w64-ucrt-x86_64-openocd
3) Verify:
   openocd --version
"@
}

Write-Host "`nDone. Then run: .\scripts\env.ps1" -ForegroundColor Green
