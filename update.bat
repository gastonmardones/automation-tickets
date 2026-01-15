@echo off
REM Script de actualización para Windows

cd /d "%~dp0"

echo === Actualizando automation-tickets ===
echo.

REM Actualizar desde el repositorio
echo Descargando actualizaciones...
git pull origin main

if %ERRORLEVEL% neq 0 (
    echo.
    echo Error al actualizar. Verifica tu conexion o si hay conflictos.
    pause
    exit /b 1
)

REM Actualizar dependencias
echo.
echo Actualizando dependencias...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    echo Advertencia: No se encontro venv. Ejecuta: pip install -r requirements.txt
)

echo.
echo === Actualizacion completada ===
pause
