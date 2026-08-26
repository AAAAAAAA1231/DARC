# Build a double-click Windows EXE. Run in PowerShell from the ashare-quant folder:
#   powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip install -U pip
python -m pip install -e ".[packaging]"
python -m PyInstaller --noconfirm --clean AShareQuant.spec

$exe = Join-Path (Get-Location) "dist\AShareQuant.exe"
if (-not (Test-Path $exe)) { throw "EXE not found: $exe" }
Write-Host "OK: $exe"
Write-Host "Double-click AShareQuant.exe. Data is written to AShareQuant_data next to the EXE."
