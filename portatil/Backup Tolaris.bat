@echo off
title Backup do Tolaris
cd /d "%~dp0"
set TOLARIS_DATABASE_URL=sqlite:///%~dp0dados/tolaris.db
"%~dp0app\python\python.exe" -m tolaris_api.backup criar --destino "%~dp0dados\backups" --manter 30
echo.
echo Copie a pasta "dados\backups" para um pen drive ou para a nuvem: um backup guardado
echo so no mesmo computador nao protege contra perda do computador.
pause
