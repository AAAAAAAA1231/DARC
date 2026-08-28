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
@"
python312.zip
.
Lib\site-packages
import site
"@ | Set-Content -Path $Pth.FullName -Encoding ascii

New-Item -ItemType Directory -Path (Join-Path $Out "Lib\site-packages") -Force | Out-Null
python -m pip install --upgrade pip
python -m pip install --target (Join-Path $Out "Lib\site-packages") numpy tzdata
Copy-Item -Recurse (Join-Path $Root "src\market_advisor") (Join-Path $Out "Lib\site-packages\market_advisor")
Copy-Item (Join-Path $Root "packaging\OpenAdvisor.bat") (Join-Path $Out "开盘建议.bat")
Copy-Item (Join-Path $Root "packaging\OpenAdvisor.vbs") (Join-Path $Out "开盘建议.vbs")
@"
开盘建议（便携版，不会被当成 PyInstaller 病毒）

1. 解压整个文件夹，不要只拷其中一个文件
2. 双击「开盘建议.bat」
3. 浏览器会打开，按交易场所列出每只股票的建议
4. 第一次可能要等几十秒拉行情

这是量化研究工具，不是投资建议。
"@ | Set-Content -Path (Join-Path $Out "使用说明.txt") -Encoding utf8

$Zip = Join-Path $Root "dist\OpenAdvisor-portable.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Zip
Write-Host "ZIP: $Zip"
