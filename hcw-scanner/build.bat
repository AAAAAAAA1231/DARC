@echo off
REM Rebuild the Windows exe on a machine with Go installed.
cd /d %~dp0
go test ./...
go build -ldflags="-H windowsgui -s -w" -o dist\HCWRadar.exe .
echo Built dist\HCWRadar.exe
