param(
  [string]$BaseUrl = "http://localhost:21345"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

python .\tools\archive_local_pnl.py --base-url $BaseUrl
