$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install -e . pyinstaller numpy
if (-not $?) { python -m pip install -e . pyinstaller numpy }
python -m PyInstaller --noconfirm --clean packaging/OpenAdvisor.spec
Write-Host "EXE: dist/OpenAdvisor.exe"
