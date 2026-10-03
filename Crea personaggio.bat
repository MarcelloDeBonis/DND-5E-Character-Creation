@echo off
rem Doppio clic qui per aprire la pagina che crea i personaggi di D&D 5e.
rem Apre il browser su http://127.0.0.1:8765 ; questa finestra deve restare aperta.
setlocal
cd /d "%~dp0"
title Creatore di personaggi D^&D 5e

set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY goto nopython

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto oldpython

%PY% -c "import flask, yaml, reportlab, pypdf, PIL" >nul 2>nul
if not errorlevel 1 goto start
echo.
echo  Preparo i programmi che servono: solo la prima volta, serve internet...
echo.
%PY% -m pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 goto pipfail

:start
echo.
echo  Apro il creatore di personaggi nel browser...
echo.
%PY% -m dnd5e web %*
if errorlevel 1 goto crashed
goto end

:nopython
echo.
echo  ============================================================
echo   Python non e' installato su questo computer.
echo   1. Scaricalo da https://www.python.org/downloads/
echo   2. Durante l'installazione spunta "Add python.exe to PATH"
echo   3. Poi fai di nuovo doppio clic su "Crea personaggio.bat"
echo  ============================================================
echo.
pause
goto end

:oldpython
echo.
echo  Python e' troppo vecchio: serve la versione 3.9 o successiva.
echo  Scarica quella nuova da https://www.python.org/downloads/
echo.
pause
goto end

:pipfail
echo.
echo  ============================================================
echo   Non sono riuscito a installare i programmi che servono.
echo   Controlla che il computer sia collegato a internet e riprova.
echo   Se non funziona ancora, manda una foto di questa finestra.
echo  ============================================================
echo.
pause
goto end

:crashed
echo.
echo  ============================================================
echo   Il creatore di personaggi si e' chiuso per un errore.
echo   Leggi il messaggio qui sopra, oppure manda una foto
echo   di questa finestra a chi ti aiuta con il programma.
echo  ============================================================
echo.
pause
goto end

:end
endlocal
