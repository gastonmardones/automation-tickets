@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Instalador de Automation Tickets
echo ===================================================
echo.

REM Detectar directorio de instalación
set "INSTALL_DIR=%USERPROFILE%\.automation-tickets"
set "BIN_DIR=%USERPROFILE%\.local\bin"

REM Crear directorios
echo 📁 Creando directorios...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

REM Copiar archivos
echo 📦 Copiando archivos...
copy /Y jira_deploy.py "%INSTALL_DIR%\"
copy /Y noc_deploy.py "%INSTALL_DIR%\"
copy /Y assessment.py "%INSTALL_DIR%\"
copy /Y requirements.txt "%INSTALL_DIR%\"

if exist config.json (
    copy /Y config.json "%INSTALL_DIR%\"
) else (
    copy /Y config.example.json "%INSTALL_DIR%\config.json"
    echo IMPORTANTE: Edita %INSTALL_DIR%\config.json con tus datos
)

REM Crear virtualenv
echo 🐍 Creando entorno virtual...
cd /d "%INSTALL_DIR%"
python -m venv venv

REM Activar e instalar dependencias
echo 📥 Instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

echo 🔗 Creando comandos globales...

REM Crear wrapper para jira
(
echo @echo off
echo call "%INSTALL_DIR%\venv\Scripts\activate.bat"
echo python "%INSTALL_DIR%\jira_deploy.py" %%*
) > "%BIN_DIR%\jira.bat"

REM Crear wrapper para noc
(
echo @echo off
echo call "%INSTALL_DIR%\venv\Scripts\activate.bat"
echo python "%INSTALL_DIR%\noc_deploy.py" %%*
) > "%BIN_DIR%\noc.bat"

REM Crear wrapper para ass
(
echo @echo off
echo call "%INSTALL_DIR%\venv\Scripts\activate.bat"
echo python "%INSTALL_DIR%\assessment.py" %%*
) > "%BIN_DIR%\ass.bat"

REM Agregar al PATH si no está
echo.
echo Verificando PATH...
set "PATH_TO_ADD=%BIN_DIR%"
echo %PATH% | findstr /C:"%PATH_TO_ADD%" >nul
if errorlevel 1 (
    echo ⚠️  IMPORTANTE: Agregando al PATH del usuario...
    setx PATH "%PATH%;%PATH_TO_ADD%"
    echo.
    echo ⚠️  Cerrá y reabrí la terminal para que los comandos funcionen
) else (
    echo ✅ PATH configurado correctamente
)

echo.
echo ===================================================
echo   ✅ Instalación completada!
echo ===================================================
echo.
echo Comandos disponibles:
echo   jira  - Crear ticket de deploy en JIRA
echo   noc   - Crear ticket en NOC
echo   ass   - Crear ticket de assessment
echo.
echo IMPORTANTE: Cerrá y reabrí la terminal para usar los comandos
echo.
pause
