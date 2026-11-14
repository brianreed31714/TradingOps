# Read-only local observation; does not install agents or change trading processes.
# Run from any PowerShell location after cloning TradingOps alongside both projects.
param(
    [string] $GitRoot = "",
    [string] $OutputPath = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TradingOpsRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($GitRoot)) {
    $GitRoot = Split-Path -Parent $TradingOpsRoot
}
$StockRoot = Join-Path $GitRoot 'StockTracker'
$CryptoRoot = Join-Path $GitRoot 'CryptoTracker'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $env:TEMP 'tradingops-host-observation.json'
}
foreach ($reg in @(
    (Join-Path $StockRoot 'infrastructure\registry.json'),
    (Join-Path $CryptoRoot 'infrastructure\registry.json')
)) {
    if (-not (Test-Path -LiteralPath $reg -PathType Leaf)) {
        throw "Expected existing paper-trader registry missing. Nothing executed."
    }
}
$Python = (Get-Command 'python.exe' -ErrorAction Stop).Source
Push-Location $TradingOpsRoot
try {
    & $Python -m tradingops.host_inventory --stock-root $StockRoot --crypto-root $CryptoRoot --output $OutputPath
    if ($LASTEXITCODE -ne 0) {
        throw "Read-only host inventory failed ($LASTEXITCODE)"
    }
} finally {
    Pop-Location
}
Write-Host 'Host observation complete. No processes, tasks, or trading configuration changed.'
Write-Host "Local report: $OutputPath"
