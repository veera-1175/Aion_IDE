@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\aion.exe" (
    echo Run scripts\setup.ps1 first.
    exit /b 1
)
call .venv\Scripts\activate.bat
aion serve %*
