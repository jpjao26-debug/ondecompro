@echo off
echo Rodando a coleta (leva uns 40 a 60 minutos)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rodar.ps1"
echo Terminou. O resumo esta na pasta logs.
pause
