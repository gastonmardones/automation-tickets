#!/bin/bash
# Script de actualización para Linux/Mac

cd "$(dirname "$0")"

echo "=== Actualizando automation-tickets ==="
echo ""

# Guardar cambios locales si los hay
if [[ -n $(git status --porcelain) ]]; then
    echo "Guardando cambios locales..."
    git stash
    STASHED=1
fi

# Actualizar desde el repositorio
echo "Descargando actualizaciones..."
git pull origin main

if [ $? -ne 0 ]; then
    echo ""
    echo "Error al actualizar. Verificá tu conexión o si hay conflictos."
    exit 1
fi

# Restaurar cambios locales si los había
if [ "$STASHED" = "1" ]; then
    echo "Restaurando cambios locales..."
    git stash pop
fi

# Actualizar dependencias si cambió requirements.txt
if git diff HEAD@{1} --name-only 2>/dev/null | grep -q "requirements.txt"; then
    echo ""
    echo "Actualizando dependencias..."
    if [ -d "venv" ]; then
        source venv/bin/activate
        pip install -r requirements.txt
    else
        echo "Advertencia: No se encontró venv. Ejecutá: pip install -r requirements.txt"
    fi
fi

echo ""
echo "=== Actualización completada ==="
