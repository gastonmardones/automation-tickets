@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Instalador de Automation Tickets
echo ===================================================
echo.
echo IMPORTANTE: Si abriste esto con doble click, la ventana
echo se cerrara al terminar. Para ver los errores, abri un CMD
echo y ejecuta: install.bat
echo.
echo Iniciando en 3 segundos...
timeout /t 3 /nobreak > nul
echo.

set "INSTALL_DIR=%USERPROFILE%\.automation-tickets"
set "BIN_DIR=%USERPROFILE%\.local\bin"

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

echo.
echo Verificando Python...
py --version > nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON=py"
    echo Python encontrado (launcher py).
) else (
    python --version > nul 2>&1
    if %errorlevel% == 0 (
        set "PYTHON=python"
        echo Python encontrado.
    ) else (
        echo ERROR: Python no encontrado.
        echo Instala Python desde https://www.python.org/downloads/
        echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
        pause
        exit /b 1
    )
)

echo.
echo Creando entorno virtual...
cd /d "%INSTALL_DIR%"
%PYTHON% -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: No se pudo crear el entorno virtual.
    pause
    exit /b 1
)

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

echo.
echo Configurando PATH...
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $p = [Environment]::GetEnvironmentVariable('PATH','User'); if (-not $p) { $p = '' }; if ($p -notlike '*\.local\bin*') { [Environment]::SetEnvironmentVariable('PATH', $p + ';%BIN_DIR%', 'User'); Write-Host 'PATH actualizado.' } else { Write-Host 'PATH ya estaba configurado.' } }"

echo.
echo ===================================================
echo   Instalacion completada!
echo ===================================================
echo.
echo Comandos disponibles:
echo   jira  - Crear ticket de deploy en JIRA
echo   noc   - Crear ticket en NOC
echo   ass   - Crear ticket de assessment
echo.
echo IMPORTANTE: Abre una NUEVA terminal para usar los comandos.
echo.
echo Verificando archivos instalados:
if exist "%BIN_DIR%\noc.bat" (echo   OK: noc.bat) else (echo   ERROR: noc.bat no encontrado)
if exist "%BIN_DIR%\jira.bat" (echo   OK: jira.bat) else (echo   ERROR: jira.bat no encontrado)
if exist "%BIN_DIR%\ass.bat" (echo   OK: ass.bat) else (echo   ERROR: ass.bat no encontrado)
if exist "%INSTALL_DIR%\venv\Scripts\python.exe" (echo   OK: virtualenv) else (echo   ERROR: virtualenv no encontrado)
echo.
pause
