$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Out = Join-Path $Root "dist\OpenAdvisor-portable"
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Path $Out | Out-Null

$PyVer = "3.12.10"
$Embed = Join-Path $env:TEMP "python-embed.zip"
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $Embed
Expand-Archive -Path $Embed -DestinationPath $Out -Force

$Pth = Get-ChildItem $Out -Filter "python*._pth" | Select-Object -First 1
if (-not $Pth) { throw "python ._pth not found in embed zip" }
Set-Content -Path $Pth.FullName -Encoding ascii -Value @(
    "python312.zip",
    ".",
    "Lib\site-packages",
    "import site"
)

New-Item -ItemType Directory -Path (Join-Path $Out "Lib\site-packages") -Force | Out-Null
python -m pip install --upgrade pip
python -m pip install --target (Join-Path $Out "Lib\site-packages") numpy tzdata
Copy-Item -Recurse (Join-Path $Root "src\market_advisor") (Join-Path $Out "Lib\site-packages\market_advisor")
Copy-Item (Join-Path $Root "packaging\OpenAdvisor.bat") (Join-Path $Out "OpenAdvisor.bat")
Copy-Item (Join-Path $Root "packaging\OpenAdvisor.vbs") (Join-Path $Out "OpenAdvisor.vbs")
Set-Content -Path (Join-Path $Out "README.txt") -Encoding utf8 -Value @(
    "KaiPan JianYi portable build",
    "1. Unzip the whole folder.",
    "2. Double-click OpenAdvisor.bat",
    "3. The browser opens with per-stock advice by venue.",
    "4. First run may take tens of seconds.",
    "Not investment advice."
)

$Zip = Join-Path $Root "dist\OpenAdvisor-portable.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Zip
Write-Host "ZIP $Zip"
