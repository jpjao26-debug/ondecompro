@echo off
echo Vai abrir o Edge do robo na pagina de login do Instagram.
echo Entre com a SUA conta. O robo nao ve nem guarda a senha, so a sessao (fica nesta pasta, fora do GitHub).
echo Depois de entrar, ele testa sozinho abrindo o perfil do Conde.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m coletor.conde --entrar) else (python -m coletor.conde --entrar)
pause
