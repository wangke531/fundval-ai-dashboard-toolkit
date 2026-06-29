param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$SnapshotJson,

  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$argsList = @(
  ".\tools\daily_update.py",
  $SnapshotJson
)

if ($DryRun) {
  $argsList += "--dry-run"
}

python @argsList
