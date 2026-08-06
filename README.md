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

# Ver/editar la base local de DNS
dns list
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
**Tags válidos para `jira`:** `RC` → selecciona `RC-01` en el desplegable | `HOTFIX` o `FIX` → selecciona `FIX-01`

Los tags numerados también se entienden, tanto en el argumento como en la URL git:
`FIX2` → `FIX-02`, `RC-3` → `RC-03`, `HOTFIX02` → `FIX-02`.

## 🌐 Base de DNS

`noc` y `ass` recuerdan el DNS (URL del componente) que cargaste, por componente y
por ambiente, en una base SQLite local: `~/.automation-tickets/dns.db`. No se sube
al repo ni se comparte: es tuya.

La primera vez que cargás el DNS de un componente en un ambiente, queda guardado.
Las siguientes veces aparece precargado y solo tenés que dar Enter:

```bash
noc
# URL git: .../miba-login-api/-/tags/v1.0.0-RC
# Ambiente: qa
# DNS guardado para miba-login-api [qa]: https://qa.miba.example.gob.ar
# URL del componente (Enter para usar el guardado, '-' para omitir):
```

- **Enter** → usa el DNS guardado
- **escribir otro** → lo usa y actualiza el guardado
- **`-`** → omite el DNS en este ticket, sin borrar el guardado

En modo rápido funciona igual: si no pasás la URL, se toma la guardada; si la pasás,
queda guardada.

```bash
noc miba-login-api 1.0.0-RC qa                                   # usa el DNS guardado
noc miba-login-api 1.0.0-RC qa https://qa.miba.example.gob.ar    # lo usa y lo guarda
```

**Ambientes:** `prd`, `prod-int` y `prod-ext` comparten un único DNS de producción.
`dev`, `qa` y `hml` son independientes.

### Comando `dns`

```bash
dns list                              # todos los DNS guardados
dns list miba-login                   # busca por coincidencia parcial
dns set miba-login-api qa https://qa.miba.example.gob.ar
dns del miba-login-api qa             # borra un ambiente
dns del miba-login-api                # borra todos los del componente
```

En el listado, `*` marca las entradas cargadas a mano y `~` las derivadas (ver abajo);
el resto vino de OpenShift.

### Importar desde OpenShift

Los DNS de `dev` y `qa` son las routes de OCP, así que se pueden cargar todas de
una. Logueado en el cluster:

```bash
oc get routes -A -o json > routes.json
```

```bash
dns import routes.json --dry-run
```

El `--dry-run` muestra qué haría sin guardar nada. Sin el flag, importa.

El ambiente sale del sufijo del namespace (`-dev` / `-qa`) y el componente del
nombre de la route. Cuando un componente tiene varias routes en el mismo ambiente
(nombres genéricos tipo `test` o `solr`, o variantes `pre-qa`), se descartan las
pre-productivas y se prefiere el dominio corto `gcba.gob.ar` por sobre el interno
`.apps.ocp4-*`; si aún así queda ambiguo, **se omite y se reporta** en vez de
adivinar. Esos pocos se cargan a mano con `dns set`.

**Lo cargado a mano no se pisa.** Un re-import actualiza solo lo que ya venía de
OpenShift; para forzar el resto está `--force`.

`hml` y `prd` no salen de este import: viven en otros clusters y, en el caso de
producción, el DNS del ticket suele ser el público (`buenosaires.gob.ar`) y no la
route.

### Derivar un ambiente

Cuando el DNS de un ambiente es el de otro con el sufijo cambiado
(`<algo>-qa.gcba.gob.ar` → `<algo>-hml.gcba.gob.ar`), se puede generar en masa:

```bash
dns derivar hml --dry-run
```

Toma el DNS de `qa` (o de `dev` si no hay qa) y le cambia el sufijo. Solo aplica al
patrón corto `.gcba.gob.ar`: los hosts `.apps.ocp4-dev...` no se derivan porque ese
`ocp4-dev` es el nombre del **cluster**, no el ambiente. Nunca pisa un ambiente que
ya tenga DNS.

> ⚠️ Los DNS derivados son **inferidos, no verificados** contra ningún cluster. Si un
> componente no existe en ese ambiente, o su host no sigue la convención, el valor va
> a estar mal. Aparecen con `~` en `dns list`, y un `dns import` real del cluster
> correspondiente los pisa con el dato verdadero.


## 🔧 Actualizar
```bash
cd automation-tickets
./update.sh  # (o update.bat en Windows)
```

`update` hace `git pull` y actualiza las dependencias. Si además se agregaron comandos
nuevos (por ejemplo `dns`), corré el instalador para que se creen los wrappers:

```bash
./install.sh  # (o install.bat en Windows)
```

## 📁 Ubicación de los archivos

### Linux
- Scripts: `~/.automation-tickets/`
- Comandos: `~/.local/bin/`
- Base de DNS: `~/.automation-tickets/dns.db`

### Windows
- Scripts: `%USERPROFILE%\.automation-tickets\`
- Comandos: `%USERPROFILE%\.local\bin\`
- Base de DNS: `%USERPROFILE%\.automation-tickets\dns.db`

`dns.db` y `config.json` son tuyos: no se versionan ni los pisa el instalador.

## ⚙️ Cómo funciona

El instalador:
1. Crea un virtualenv aislado en tu home
2. Instala Python, Playwright y dependencias
3. Crea comandos wrapper globales (`jira`, `noc`, `ass`, `dns`)
4. Los agrega al PATH automáticamente

Así podés usar los comandos desde **cualquier directorio** sin activar virtualenvs manualmente.
