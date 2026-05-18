@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Instalador de Automation Tickets
echo ===================================================
echo.

set "INSTALL_DIR=%USERPROFILE%\.automation-tickets"
set "BIN_DIR=%USERPROFILE%\.local\bin"

REM === PASO 1: PATH (siempre, independiente de lo que pase despues) ===
echo Configurando PATH...
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $p = [Environment]::GetEnvironmentVariable('PATH','User'); if (-not $p) { $p = '' }; if ($p -notlike '*\.local\bin*') { [Environment]::SetEnvironmentVariable('PATH', $p + ';%BIN_DIR%', 'User'); Write-Host '  PATH actualizado.' } else { Write-Host '  PATH ya estaba configurado.' } }"

REM === PASO 2: Directorios y archivos ===
echo Creando directorios...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

echo Copiando archivos...
copy /Y jira_deploy.py "%INSTALL_DIR%\" > nul
copy /Y noc_deploy.py "%INSTALL_DIR%\" > nul
copy /Y assessment.py "%INSTALL_DIR%\" > nul
copy /Y requirements.txt "%INSTALL_DIR%\" > nul

if exist config.json (
    copy /Y config.json "%INSTALL_DIR%\" > nul
) else (
    copy /Y config.example.json "%INSTALL_DIR%\config.json" > nul
    echo IMPORTANTE: Edita %INSTALL_DIR%\config.json con tus datos
)

REM === PASO 3: Detectar Python ===
echo.
echo Verificando Python...
set "PYTHON="

REM Intentar py launcher (el mas confiable en Windows)
py -3 --version > nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON=py -3"
    py -3 --version
    goto :python_ok
)

REM Intentar python directo
python --version > nul 2>&1
if %errorlevel% == 0 (
    REM Verificar que no es el alias del Microsoft Store
    python -c "import sys; sys.exit(0)" > nul 2>&1
    if %errorlevel% == 0 (
        set "PYTHON=python"
        python --version
        goto :python_ok
    )
)

REM Intentar python3
python3 --version > nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON=python3"
    python3 --version
    goto :python_ok
)

echo.
echo ERROR: Python no encontrado o es el alias del Microsoft Store.
echo.
echo Soluciones:
echo   1. Instala Python desde https://www.python.org/downloads/
echo      (marca "Add Python to PATH" durante la instalacion)
echo   2. O ve a Configuracion ^> Aplicaciones ^> Alias de ejecucion
echo      y desactiva los alias de python.exe y python3.exe
echo.
pause
exit /b 1

:python_ok
REM Verificar version de Python (necesitamos 3.9-3.13)
for /f "tokens=2 delims=." %%a in ('%PYTHON% --version 2^>^&1') do set "PY_MINOR=%%a"
if %PY_MINOR% GEQ 14 (
    echo.
    echo ADVERTENCIA: Python 3.%PY_MINOR% es muy nuevo, algunos paquetes pueden no tener
    echo compatibilidad todavia. Se recomienda Python 3.12 para mayor estabilidad.
    echo Descargalo desde: https://www.python.org/downloads/release/python-3127/
    echo.
    echo Presiona una tecla para continuar igual o Ctrl+C para cancelar...
    pause > nul
)
echo.

REM === PASO 4: Virtualenv ===
echo Creando entorno virtual...
cd /d "%INSTALL_DIR%"
%PYTHON% -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: No se pudo crear el entorno virtual.
    pause
    exit /b 1
)

REM === PASO 5: Dependencias ===
echo Instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

echo Instalando Chromium...
playwright install chromium
if %errorlevel% neq 0 (
    echo ERROR: No se pudo instalar Chromium.
    pause
    exit /b 1
)

REM === PASO 6: Comandos globales ===
echo.
echo Creando comandos globales...

(
echo @echo off
echo call "%INSTALL_DIR%\venv\Scripts\activate.bat"
echo python "%INSTALL_DIR%\jira_deploy.py" %%*
) > "%BIN_DIR%\jira.bat"

(
echo @echo off
echo call "%INSTALL_DIR%\venv\Scripts\activate.bat"
echo python "%INSTALL_DIR%\noc_deploy.py" %%*
) > "%BIN_DIR%\noc.bat"

(
echo @echo off
echo call "%INSTALL_DIR%\venv\Scripts\activate.bat"
echo python "%INSTALL_DIR%\assessment.py" %%*
) > "%BIN_DIR%\ass.bat"

REM === RESULTADO ===
echo.
echo ===================================================
echo   Instalacion completada!
echo ===================================================
echo.
echo Verificacion:
if exist "%BIN_DIR%\noc.bat"               (echo   OK: noc.bat)     else (echo   ERROR: noc.bat)
if exist "%BIN_DIR%\jira.bat"              (echo   OK: jira.bat)    else (echo   ERROR: jira.bat)
if exist "%BIN_DIR%\ass.bat"               (echo   OK: ass.bat)     else (echo   ERROR: ass.bat)
if exist "%INSTALL_DIR%\venv\Scripts\python.exe" (echo   OK: virtualenv) else (echo   ERROR: virtualenv)
echo.
echo Comandos: jira / noc / ass
echo IMPORTANTE: Abre una NUEVA terminal para usarlos.
echo.
pause
