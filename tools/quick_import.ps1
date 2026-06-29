param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$SnapshotJson,

  [string]$Out = ".\imports\last_import_report.json",
  [string]$Account = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$argsList = @(
  ".\tools\import_alipay_snapshot.py",
  $SnapshotJson,
  "--replace",
  "--out",
  $Out
)

if (-not $DryRun) {
  $argsList += @(
    "--update-nav",
    "--update-estimate",
    "--estimate-source",
    "yangjibao"
  )
}

if ($Account) {
  $argsList += @("--account", $Account)
}

if ($DryRun) {
  $argsList += "--dry-run"
}

python @argsList
