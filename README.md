# Automation Tickets

Scripts de automatización para creación de tickets en NOC, JIRA y Assessment.



## Instalación

### Instalar Python
**Linux:**
```bash
sudo apt update
sudo apt install python3 python3-pip
```

**Windows:**
Descargar desde https://www.python.org/downloads/

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

Editá `~/.automation-tickets/config.json` con tus datos:

```json
{
  "user": "tu_usuario",
  "cuit": "20XXXXXXXXX0",
  "password": "",
  "jira_responsable": "nombre apellido"
}
```

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `user` | Sí | Tu usuario NOC (usado para el campo Solicitante en los tickets) |
| `cuit` | Sí | CUIT — se usa como usuario al hacer login en NOC y JIRA |
| `password` | No | Contraseña de NOC/JIRA. Si está vacío, el browser la pide manualmente. **Guardarla acá es conveniente pero menos seguro.** |
| `jira_responsable` | Sí | Nombre del responsable referente en JIRA |

### Sesiones

Los scripts guardan las sesiones de NOC y JIRA en el disco. Mientras la sesión sea válida (el servidor no la expire), el login es automático. Cuando expira:
- Si `noc_password` está configurado → login automático completo
- Si no → el browser se abre con el usuario pre-completado y solo tenés que escribir la contraseña

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
jira miba-login-api 1.0.0 RC 1502048
noc miba-login-api 1.0.0-RC prd
ass miba-login-api 1.0.0-RC qa
```

**Ambientes válidos para `noc` y `ass`:** `dev`, `qa`, `hml`, `prd`
**Tags válidos para `jira`:** `RC` → selecciona `RC-1` en el desplegable | `HOTFIX` → selecciona `FIX-1`


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
