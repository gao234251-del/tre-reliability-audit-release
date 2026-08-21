param(
    [Parameter(Mandatory = $true)]
    [string]$Workbook,
    [string]$Python = 'python',
    [string]$OutputJson = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path -LiteralPath $Python -PathType Leaf) {
    $PythonExe = (Resolve-Path -LiteralPath $Python).Path
} else {
    $PythonCommand = Get-Command $Python -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw "Python not found: $Python. Install the environment listed in requirements.txt, add python to PATH, or pass -Python with the absolute interpreter path."
    }
    $PythonExe = $PythonCommand.Source
}
if (-not (Test-Path -LiteralPath $Workbook)) { throw "Workbook not found: $Workbook" }
if ([string]::IsNullOrWhiteSpace($OutputJson)) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $OutputJson = Join-Path $root "outputs\frozen_audit_$stamp.json"
}

& $PythonExe (Join-Path $root 'code\verify_reference_bundle.py') --package-root $root
if ($LASTEXITCODE -ne 0) { throw 'Static-file audit failed.' }
& $PythonExe (Join-Path $root 'code\verify_frozen_baseline.py') `
    --workbook $Workbook `
    --candidate-csv (Join-Path $root 'inputs\physical_dem_candidates_48470.csv') `
    --locked-folds (Join-Path $root 'inputs\journal_spatial_folds_locked.xlsx') `
    --old-artifact (Join-Path $root 'inputs\frozen_xiongan_tre_ensemble.joblib') `
    --reference-grid (Join-Path $root 'reference_outputs\locked_fold_grid_comparison_reconstructed_v15.csv') `
    --output-json $OutputJson
if ($LASTEXITCODE -ne 0) { throw 'Frozen-model audit failed.' }
Write-Host "Audit report written to: $OutputJson"
