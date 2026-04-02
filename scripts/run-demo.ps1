# scripts/run-demo.ps1
#
# Windows demo launcher for simulator + daemon + UI.
#
# This script is Dash-only:
# - starts simulator
# - starts daemon
# - starts Dash UI
#
# Process modes:
# - NewWindow  (default): each long-running process opens in its own PowerShell window with live logs.
# - Background: detached processes, stdout/stderr redirected to logs/demo/*.log.
#
# Examples:
#   .\scripts\run-demo.ps1
#   .\scripts\run-demo.ps1 -ProcessMode NewWindow
#   .\scripts\run-demo.ps1 -ProcessMode Background

[CmdletBinding()]
param(
  [ValidateSet("NewWindow", "Background")]
  [string]$ProcessMode = "NewWindow",

  [ValidateRange(1, 65535)]
  [int]$DaemonPort = 8765,

  [ValidateRange(1, 65535)]
  [int]$SimPort = 9000,

  [ValidateRange(1, 65535)]
  [int]$DashPort = 8050,

  [ValidateSet("Debug", "Release")]
  [string]$SimConfig = "Debug",

  [switch]$DashDebug
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$daemonUrl = "http://127.0.0.1:$DaemonPort"
$logDir = Join-Path $repoRoot "logs/demo"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Start-NewWindowProcess {
  param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$CommandLine
  )

  $command = "`$Host.UI.RawUI.WindowTitle='$Title'; Set-Location '$repoRoot'; $CommandLine"
  Start-Process powershell -ArgumentList @("-NoExit", "-Command", $command) | Out-Null
}

function Start-BackgroundProcess {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $false)][string[]]$ArgumentList
  )

  $outLog = Join-Path $logDir "$Name.out.log"
  $errLog = Join-Path $logDir "$Name.err.log"

  $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog

  Write-Host "[$Name] PID=$($proc.Id)"
  Write-Host "  stdout: $outLog"
  Write-Host "  stderr: $errLog"
}

function Start-Simulator {
  $simScript = Join-Path $repoRoot "scripts/run-sim.ps1"
  $simCmd = "& '$simScript' -Config $SimConfig -SimPort $SimPort"

  switch ($ProcessMode) {
    "NewWindow" {
      Start-NewWindowProcess -Title "PowerScope Simulator" -CommandLine $simCmd
    }
    "Background" {
      $psArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $simScript, "-Config", $SimConfig, "-SimPort", "$SimPort")
      Start-BackgroundProcess -Name "sim" -FilePath "powershell" -ArgumentList $psArgs
    }
  }
}

function Start-Daemon {
  switch ($ProcessMode) {
    "NewWindow" {
      Start-NewWindowProcess -Title "PowerScope Daemon" -CommandLine "python -m host.daemon --host 127.0.0.1 --port $DaemonPort"
    }
    "Background" {
      Start-BackgroundProcess -Name "daemon" -FilePath "python" -ArgumentList @("-m", "host.daemon", "--host", "127.0.0.1", "--port", "$DaemonPort")
    }
    default {
      throw "Inline mode is only supported for simulator. Use NewWindow or Background for daemon."
    }
  }
}

function Start-Dash {
  $dashArgs = @("-m", "host.clients.dash", "--host", "127.0.0.1", "--port", "$DashPort", "--daemon-url", $daemonUrl)
  if ($DashDebug) {
    $dashArgs += "--debug"
  }

  switch ($ProcessMode) {
    "NewWindow" {
      $dashCmd = "python " + ($dashArgs -join " ")
      Start-NewWindowProcess -Title "PowerScope Dash" -CommandLine $dashCmd
      Write-Host "Dash UI: http://127.0.0.1:$DashPort"
    }
    "Background" {
      Start-BackgroundProcess -Name "dash" -FilePath "python" -ArgumentList $dashArgs
      Write-Host "Dash UI: http://127.0.0.1:$DashPort"
    }
    default {
      throw "Inline mode is not supported for Dash in this demo script."
    }
  }
}

Write-Host "PowerScope demo"
Write-Host "  ProcessMode: $ProcessMode"
Write-Host "  Daemon URL : $daemonUrl"
Write-Host "  Sim Port   : $SimPort"

Start-Simulator
Start-Sleep -Seconds 1

Start-Daemon
Start-Sleep -Seconds 1

Start-Dash

Write-Host ""
if ($ProcessMode -eq "Background") {
  Write-Host "Background mode enabled: logs are written to logs/demo/*.log"
  Write-Host "Tip: tail logs with: Get-Content .\logs\demo\daemon.out.log -Wait"
} elseif ($ProcessMode -eq "NewWindow") {
  Write-Host "Each process runs in its own PowerShell window with live logs."
}
