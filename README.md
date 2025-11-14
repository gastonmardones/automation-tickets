# Automation Tickets

Scripts de automatización para creación de tickets en NOC, JIRA y Assessment.

## Instalación

### Linux
```bash
# Clonar el repositorio
git clone https://github.com/gastonmardones/automation-tickets.git
cd automation-tickets

# Ejecutar instalador (automático)
chmod +x install.sh
./install.sh

# Si te pide agregar al PATH, ejecutá:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Windows
```batch
# Clonar el repositorio
git clone https://github.com/gastonmardones/automation-tickets.git
cd automation-tickets

# Ejecutar instalador (automático)
install.bat

# Cerrar y reabrir la terminal
```

## ⚙️ Configuración inicial

Después de instalar, configurá tu usuario:

Editá config.json con tu mail

**config.json:**
```json
{
  "noc_user": "tu mail sin @buenosaires.gob.ar",
  "jira_responsable": "ramiro gomez"
}
```

## 📝 Uso

Una vez instalado, podés usar los comandos desde **cualquier directorio**:
```bash
# Crear ticket de deploy en JIRA
jira

# Crear ticket en NOC
noc

# Crear ticket de assessment
ass
```

### Modo interactivo (sin argumentos)
```bash
jira
# Te pedirá: Componente, Versión, Tag, Ticket NOC
```

### Modo rápido (con argumentos)
```bash
jira backend 1.0.0 RC-1 1502048
noc "Titulo del ticket" "Descripción completa"
ass APPUSHESBA
```

## 🗑️ Desinstalar

### Linux
```bash
cd automation-tickets
./uninstall.sh
```

### Windows
```batch
cd automation-tickets
uninstall.bat
```

## 🔧 Actualizar
```bash
cd automation-tickets
git pull
./install.sh  # (o install.bat en Windows)
```

## 📁 Ubicación de los archivos

### Linux
- Scripts: `~/.automation-tickets/`
- Comandos: `~/.local/bin/`

### Windows
- Scripts: `%USERPROFILE%\.automation-tickets\`
- Comandos: `%USERPROFILE%\.local\bin\`

## ⚙️ Cómo funciona

El instalador:
1. Crea un virtualenv aislado en tu home
2. Instala Python, Playwright y dependencias
3. Crea comandos wrapper globales (`jira`, `noc`, `ass`)
4. Los agrega al PATH automáticamente

Así podés usar los comandos desde **cualquier directorio** sin activar virtualenvs manualmente.

## 📞 Soporte

Para reportar bugs o solicitar features: [Issues](https://github.com/gastonmardones/automation-tickets/issues)