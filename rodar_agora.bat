@echo off
echo Rodando a coleta (leva os tres mercados + encartes; pode levar mais de 1 hora)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rodar.ps1"
echo Terminou. O resumo esta na pasta logs.
pause
