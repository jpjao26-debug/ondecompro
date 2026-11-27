@echo off
chcp 65001 >nul
echo Envia o codigo atual dos 3 apps ao GitHub e liga o teste na nuvem.
echo (chaves.env e o login do Instagram NUNCA sao enviados)
echo.
for %%p in (ondecompro ondecompro-maringa ondecompro-pocos) do call :enviar "%~dp0..\%%p" %%p
echo.
echo Pronto! O teste roda sozinho no GitHub (uns 20 a 40 minutos). Pode fechar esta janela.
pause
exit /b 0

:enviar
echo ===== %~2 =====
cd /d "%~1"
rem instala o robo de teste do GitHub (arquivo de configuracao do GitHub Actions)
if not exist ".github\workflows" mkdir ".github\workflows"
copy /y "nuvem\teste_nuvem.yml" ".github\workflows\teste_nuvem.yml" >nul
git add -A
git diff --cached --name-only | findstr /i /l "chaves.env navegador_robo" >nul
if not errorlevel 1 (
  echo ATENCAO: arquivo secreto ia ser enviado - parei este app sem enviar nada.
  git reset -q
  goto :eof
)
git commit -q -m "Codigo atualizado + teste na nuvem"
git push -q
if errorlevel 1 (
  git pull -q --rebase --autostash
  git push -q
)
if errorlevel 1 (echo Nao consegui enviar %~2.) else (echo %~2 enviado.)
goto :eof
