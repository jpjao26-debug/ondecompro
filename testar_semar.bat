@echo off
cd /d "%~dp0"
echo Testando so o Semar (1 pagina de cada departamento, uns 2 minutos)...
py -3 -c "from coletor import semar; ps = semar.coletar(limite_paginas=1); print(); print('Semar OK:', len(ps), 'produtos'); print(ps[0]['nome'], ps[0]['preco']) if ps else None"
echo.
pause
