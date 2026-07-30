# jira_deploy.py
from playwright.sync_api import sync_playwright
import sys
import re
import json
import os
import atexit
from git_url_parser import parsear_url_git

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if not os.path.exists(config_path):
        sys.exit(1)

    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

JIRA_CLOUD_BASE = "https://asi-jira-cloud.atlassian.net"
TIPO_INCIDENCIA = ".ASI Deploy de version (Ch2)"

def crear_ticket_jira(componente, version, tag, ticket_noc):
    campos_pendientes = not (componente and version and tag)

    # Rutas
    base_dir = os.path.dirname(__file__)
    noc_profile = os.path.join(base_dir, 'browser_profile_noc')
    jira_profile = os.path.join(base_dir, 'browser_profile_jira_cloud')
    noc_auth_file = os.path.join(base_dir, 'noc_auth_state.json')

    def normalizar_tag(tag):
        tag_upper = tag.upper().strip()
        if tag_upper == 'RC':
            return 'RC-01'
        if tag_upper in ('HOTFIX', 'FIX'):
            return 'FIX-01'
        # fallback formato viejo: RC-1, RC-01, etc.
        match = re.match(r'([A-Z]+)-?(\d+)', tag_upper)
        if match:
            prefijo = match.group(1)
            numero = int(match.group(2))
            return f"{prefijo}-{numero:02d}"
        return tag

    # Variable para rastrear el contexto activo (para cleanup)
    active_context = [None]  # Lista para poder modificar desde closure

    def cleanup():
        try:
            if active_context[0]:
                active_context[0].close()
        except:
            pass

    atexit.register(cleanup)

    with sync_playwright() as p:
        print("=== PASO 1: Obtener datos del ticket NOC ===\n")

        noc_url = f"https://noc-mesa.buenosaires.gob.ar/WorkOrder.do?woMode=viewWO&woID={ticket_noc}"

        # Intentar primero en modo headless con el perfil persistente
        noc_context = None
        try:
            noc_context = p.chromium.launch_persistent_context(
                user_data_dir=noc_profile,
                headless=True
            )
            # Cargar cookies guardadas si existen
            if os.path.exists(noc_auth_file):
                with open(noc_auth_file, 'r') as f:
                    state = json.load(f)
                    if state.get('cookies'):
                        noc_context.add_cookies(state['cookies'])
            active_context[0] = noc_context
            noc_page = noc_context.new_page()

            noc_page.goto(noc_url, timeout=30000, wait_until='domcontentloaded')
            noc_page.wait_for_selector('#req-desc-body, #username', timeout=8000)
            if noc_page.locator('#username').count() > 0:
                raise Exception("login_required")
            print("Sesión NOC válida")

        except:
            print("Sesión NOC expirada. Abriendo navegador para login...")
            if noc_context:
                noc_context.close()

            noc_context = p.chromium.launch_persistent_context(
                user_data_dir=noc_profile,
                headless=False
            )
            if os.path.exists(noc_auth_file):
                with open(noc_auth_file, 'r') as f:
                    state = json.load(f)
                    if state.get('cookies'):
                        noc_context.add_cookies(state['cookies'])
            active_context[0] = noc_context
            noc_page = noc_context.new_page()

            noc_page.goto(noc_url)
            noc_page.wait_for_load_state('domcontentloaded')

            try:
                noc_page.wait_for_selector('#username', timeout=5000)
                noc_page.locator('#username').click()
                noc_page.keyboard.type(config.get('cuit', ''))
                noc_password = config.get('password', '')
                if noc_password:
                    noc_page.locator('#password').click()
                    noc_page.keyboard.type(noc_password)
                    noc_page.wait_for_timeout(300)
                    noc_page.click('#loginSDPage')
                    print("Credenciales NOC completadas automáticamente.")
                else:
                    print("Usuario NOC completado. Ingresá tu contraseña en el navegador.")
            except:
                print("Completá tus credenciales NOC en el navegador.")

            try:
                noc_page.wait_for_selector('#req-desc-body', timeout=0)
                noc_context.storage_state(path=noc_auth_file)
                print("Sesión NOC guardada.")

                noc_page.goto(noc_url)
                noc_page.wait_for_load_state('domcontentloaded')
            except:
                noc_context.close()
                return

        # Extraer descripción
        try:
            descripcion_elemento = noc_page.locator('#req-desc-body')
            descripcion = descripcion_elemento.inner_text()
        except Exception as e:
            descripcion = f"Deploy {componente} {version}-{tag}"

        # Extraer URL GIT (probar TAG, UPGRADE y CHANGELOG, en ese orden;
        # los 3 apuntan al mismo repo/tag, solo cambia el archivo final)
        CAMPOS_URL_GIT = ['udf_sline_11422', 'udf_sline_11423', 'udf_sline_11420']
        url_git = ""
        datos = None
        for campo in CAMPOS_URL_GIT:
            try:
                elem = noc_page.locator(f'p[data-name="{campo}"]')
                valor = elem.inner_text(timeout=2000).strip()
            except Exception:
                continue
            if not valor or valor == '-':
                continue
            if not url_git:
                url_git = valor
                print(f"URL GIT obtenida: {url_git}")
            intento = parsear_url_git(valor)
            if intento:
                datos = intento
                break

        print("\nDatos extraídos del NOC")

        noc_context.close()

        # Si no vinieron componente/version/tag (modo interactivo con solo ticket NOC),
        # completarlos con lo parseado de alguna de las URLs GIT del ticket.
        if campos_pendientes:
            if datos:
                componente, version, tag = datos
                print(f"Componente: {componente} | Versión: {version} | Tag: {tag}")
            else:
                print("No se pudo interpretar ninguna URL GIT del ticket, completá los campos manualmente.")
                componente = input("Componente: ").strip()
                version = input("Versión (ej: 1.0.0): ").strip()
                tag = input("Tag (RC o HOTFIX): ").strip()

        # PASO 2: Crear ticket en JIRA CLOUD

        # El perfil persistente evita repetir el login SSO/2FA en cada corrida.
        # La primera vez (o cuando expire la sesión de Microsoft), se abre visible
        # para que el usuario complete el login manualmente.
        jira_context = p.chromium.launch_persistent_context(
            user_data_dir=jira_profile,
            headless=False
        )
        active_context[0] = jira_context

        jira_page = jira_context.new_page()
        jira_page.goto(f"{JIRA_CLOUD_BASE}/jira/dashboards/10573")
        jira_page.wait_for_load_state('domcontentloaded')

        create_button = jira_page.get_by_test_id("atlassian-navigation--create-button")

        try:
            create_button.wait_for(timeout=15000)
        except:
            print("No se detectó sesión activa. Completá el login (usuario, Microsoft, 2FA) en el navegador...")
            try:
                create_button.wait_for(timeout=0)
                jira_context.storage_state(path=os.path.join(base_dir, 'jira_cloud_auth_state.json'))
                print("Sesión JIRA Cloud guardada.")
            except:
                jira_context.close()
                return

        create_button.click()

        # === Banner: Proyecto manual ===
        jira_page.evaluate("""
        () => {
            if (document.getElementById('banner-recordatorio')) return;

            const banner = document.createElement('div');
            banner.id = 'banner-recordatorio';
            banner.style.position = 'fixed';
            banner.style.bottom = '30px';
            banner.style.left = '50%';
            banner.style.transform = 'translateX(-50%)';
            banner.style.background = '#2d6cdf';
            banner.style.color = 'white';
            banner.style.padding = '16px 24px';
            banner.style.borderRadius = '8px';
            banner.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            banner.style.zIndex = '999999';
            banner.style.fontFamily = 'system-ui, sans-serif';
            banner.style.fontSize = '15px';
            banner.style.display = 'flex';
            banner.style.alignItems = 'center';
            banner.style.gap = '12px';
            banner.style.animation = 'slideUp 0.3s ease';

            banner.innerHTML = `
                <span style="font-size: 20px;">ℹ️</span>
                <span>Cargá manualmente el <strong>Proyecto</strong></span>
                <button id="cerrar-banner" style="
                    background: rgba(255,255,255,0.2);
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    margin-left: 8px;
                    cursor: pointer;
                    font-size: 18px;
                    line-height: 1;
                ">×</button>
            `;

            document.body.appendChild(banner);

            document.getElementById('cerrar-banner').addEventListener('click', () => {
                banner.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                banner.style.opacity = '0';
                banner.style.transform = 'translateX(-50%) translateY(20px)';
                setTimeout(() => banner.remove(), 300);
            });

            const style = document.createElement('style');
            style.innerHTML = `
                @keyframes slideUp {
                    from {
                        opacity: 0;
                        transform: translateX(-50%) translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(-50%) translateY(0);
                    }
                }
            `;
            document.head.appendChild(style);
        }
        """)

        try:
            jira_page.locator('#summary-field').wait_for(timeout=120000)
        except:
            jira_context.close()
            return

        # === Tipo de incidencia (fijo) ===
        try:
            jira_page.locator('[id^="type-picker-"]').click()
            jira_page.get_by_role("option", name=TIPO_INCIDENCIA).click()
        except Exception as e:
            print(f"No se pudo seleccionar el Tipo de Incidencia automáticamente: {e}")

        # === Resumen ===
        resumen = f"Deploy {componente} {version}-{tag}" if componente else f"Deploy {version}-{tag}"
        jira_page.locator('#summary-field').click()
        jira_page.locator('#summary-field').fill(resumen)

        # === Descripción (editor ProseMirror/ADF) ===
        try:
            jira_page.locator('#ak-editor-textarea').click()
            jira_page.locator('#ak-editor-textarea').fill(descripcion)
        except Exception as e:
            print(f"No se pudo llenar la descripción automáticamente: {e}")

        # === Fix Version ===
        try:
            jira_page.locator('#fixVersions-field').click()
            jira_page.locator('#fixVersions-field').fill(version)
            jira_page.wait_for_selector('[role="option"], [role="listbox"]', timeout=3000)

            # El botón "Crear nueva versión" siempre aparece en el footer del
            # dropdown, exista o no la versión. Solo seleccionar si hay una
            # opción existente cuyo texto coincida exactamente; si no, dejar vacío.
            opcion_existente = jira_page.locator('[role="option"]').filter(has_text=version).first

            if opcion_existente.count() > 0 and opcion_existente.inner_text().strip() == version:
                opcion_existente.click()
            else:
                print(f"Versión '{version}' no existe en Jira. Dejando el campo vacío.")
                jira_page.locator('#fixVersions-field').clear()
                jira_page.keyboard.press('Escape')
        except Exception as e:
            print(f"No se pudo seleccionar versión automáticamente: {e}")

        # === Tag (customfield_10093, label ".Tag-C") ===
        tag_normalizado = normalizar_tag(tag)
        try:
            jira_page.locator('#customfield_10093-field').click()
            jira_page.locator('#customfield_10093-field').fill(tag_normalizado)
            jira_page.wait_for_selector('[role="option"]', timeout=3000)
            jira_page.get_by_role("option", name=tag_normalizado).click()
        except Exception as e:
            print(f"No se pudo seleccionar el Tag '{tag_normalizado}' automáticamente: {e}")

        # === Responsable Referente (customfield_10096, fabric-user-picker) ===
        try:
            jira_page.locator('#customfield_10096-field').click()
            jira_page.locator('#customfield_10096-field').fill(config['jira_responsable'])
            jira_page.wait_for_selector('[role="option"]', timeout=5000)
            jira_page.get_by_role("option").first.click()
        except Exception as e:
            print(f"No se pudo completar Responsable Referente automáticamente: {e}")

        # === Nro Ticket ME (customfield_10099, input numérico simple) ===
        try:
            jira_page.locator('#customfield_10099-field').click()
            jira_page.locator('#customfield_10099-field').fill(ticket_noc)
        except Exception as e:
            print(f"No se pudo completar Nro Ticket ME automáticamente: {e}")

        # === URL GIT (customfield_10108, input de texto simple) ===
        if url_git:
            try:
                jira_page.locator('#customfield_10108-field').click()
                jira_page.locator('#customfield_10108-field').fill(url_git)
            except Exception as e:
                print(f"No se pudo llenar URL GIT: {e}")

        # === Modal recordatorio para completar el componente manualmente ===
        jira_page.evaluate("""
        () => {
            if (document.getElementById('modal-recordatorio')) return;

            const overlay = document.createElement('div');
            overlay.id = 'modal-recordatorio';
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100vw';
            overlay.style.height = '100vh';
            overlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
            overlay.style.display = 'flex';
            overlay.style.alignItems = 'center';
            overlay.style.justifyContent = 'center';
            overlay.style.zIndex = '999999';

            const modal = document.createElement('div');
            modal.style.background = 'white';
            modal.style.borderRadius = '10px';
            modal.style.boxShadow = '0 6px 20px rgba(0,0,0,0.25)';
            modal.style.padding = '20px 28px';
            modal.style.maxWidth = '320px';
            modal.style.textAlign = 'center';
            modal.style.fontFamily = 'system-ui, sans-serif';
            modal.style.animation = 'fadeIn 0.3s ease';

            modal.innerHTML = `
                <p style="font-size:15px; color:#333; margin-bottom:16px; line-height:1.4;">
                No te olvides de seleccionar<br>
                el <strong>componente</strong>.
                </p>
                <button id="cerrar-modal-recordatorio" style="
                background:#2d6cdf;
                color:white;
                border:none;
                border-radius:6px;
                padding:8px 16px;
                font-size:14px;
                cursor:pointer;
                transition:background 0.2s ease;
                ">OK</button>
            `;

            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            document.getElementById('cerrar-modal-recordatorio').addEventListener('click', () => {
                overlay.style.transition = 'opacity 0.3s ease';
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 300);
            });

            const style = document.createElement('style');
            style.innerHTML = `
                @keyframes fadeIn {
                from { transform: scale(0.9); opacity: 0; }
                to { transform: scale(1); opacity: 1; }
                }
            `;
            document.head.appendChild(style);
        }
        """)

        jira_page.wait_for_selector('#modal-recordatorio', state='detached', timeout=300000)

        print("\n[Cerrá el navegador o presioná Enter para finalizar...]")

        # Esperar cierre del navegador o Enter del usuario
        import threading
        closed = threading.Event()

        def on_close():
            closed.set()

        jira_page.on('close', on_close)

        # También permitir cerrar con Enter
        def wait_input():
            try:
                input()
                closed.set()
            except:
                pass

        input_thread = threading.Thread(target=wait_input, daemon=True)
        input_thread.start()

        closed.wait()
        jira_context.close()

def main():

    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('componente')
        parser.add_argument('version')
        parser.add_argument('tag')
        parser.add_argument('ticket_noc')
        args = parser.parse_args()

        crear_ticket_jira(args.componente, args.version, args.tag, args.ticket_noc)
    else:
        print("=== CREAR TICKET DE DEPLOY EN JIRA ===\n")

        ticket_noc = input("Nro Ticket NOC: ").strip()

        # componente/version/tag se completan automáticamente parseando
        # la URL GIT del ticket NOC (ver crear_ticket_jira). Si no se puede,
        # se piden ahí mismo por input.
        crear_ticket_jira(
            componente="",
            version="",
            tag="",
            ticket_noc=ticket_noc
        )

if __name__ == '__main__':
    main()
