#!/bin/bash
set -e

echo "==================================================="
echo "  Instalador"
echo "==================================================="
echo ""

# Detectar directorio de instalación
INSTALL_DIR="$HOME/.automation-tickets"
BIN_DIR="$HOME/.local/bin"

# Crear directorios
echo "Creando directorios..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Copiar archivos
echo "Copiando archivos..."
cp jira_deploy.py "$INSTALL_DIR/"
cp noc_deploy.py "$INSTALL_DIR/"
cp assessment.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Crear virtualenv
echo "Creando entorno virtual..."
cd "$INSTALL_DIR"
python3 -m venv venv

# Activar e instalar dependencias
echo "Instalando dependencias..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

echo "Creando comandos globales..."

# Crear wrapper para jira
cat > "$BIN_DIR/jira" << 'EOF'
#!/bin/bash
source "$HOME/.automation-tickets/venv/bin/activate"
python "$HOME/.automation-tickets/jira_deploy.py" "$@"
EOF
chmod +x "$BIN_DIR/jira"

# Crear wrapper para noc
cat > "$BIN_DIR/noc" << 'EOF'
#!/bin/bash
source "$HOME/.automation-tickets/venv/bin/activate"
python "$HOME/.automation-tickets/noc_deploy.py" "$@"
EOF
chmod +x "$BIN_DIR/noc"

# Crear wrapper para ass
cat > "$BIN_DIR/ass" << 'EOF'
#!/bin/bash
source "$HOME/.automation-tickets/venv/bin/activate"
python "$HOME/.automation-tickets/assessment.py" "$@"
EOF
chmod +x "$BIN_DIR/ass"

# Verificar PATH
echo ""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "IMPORTANTE: Agregá esta línea a tu ~/.bashrc o ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Luego ejecutá: source ~/.bashrc  (o source ~/.zshrc)"
else
    echo "PATH configurado correctamente"
fi

echo ""
echo "==================================================="
echo "  Instalación completada!"
echo "==================================================="
echo ""
echo "Comandos disponibles:"
echo "  jira  - Crear ticket de deploy en JIRA"
echo "  noc   - Crear ticket en NOC"
echo "  ass   - Crear ticket de assessment"
echo ""