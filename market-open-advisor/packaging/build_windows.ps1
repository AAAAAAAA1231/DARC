$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install -e . pyinstaller numpy tzdata
if (-not $?) { python -m pip install -e . pyinstaller numpy tzdata }
python -m PyInstaller --noconfirm --clean packaging/OpenAdvisor.spec
Write-Host "EXE: dist/OpenAdvisor.exe"
