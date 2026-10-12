@echo off
title Tolaris Contabil
cd /d "%~dp0"
"%~dp0app\python\python.exe" "%~dp0app\iniciar.py" %*
echo.
pause
