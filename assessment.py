from playwright.sync_api import sync_playwright
import sys
import json
import os
import atexit

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if not os.path.exists(config_path):
        sys.exit(1)
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

def crear_ticket_assessment(componente, version, ambiente, url=""):
    IP_NODO_MAP = {
        'qa': ['10.9.10.75', '10.9.10.76', '10.9.10.116', '10.9.10.156', '10.9.10.157', '10.9.11.188', '10.9.11.187'],
        'dev': ['10.9.10.75', '10.9.10.76', '10.9.10.116', '10.9.10.156', '10.9.10.157', '10.9.11.188', '10.9.11.187'],
        'hml': ['10.12.0.26', '10.12.0.27', '10.12.0.21', '10.12.2.173', '10.12.2.203', '10.12.2.204', '10.12.2.205', '10.12.2.206'],
        'prod-int': ['10.10.4.106', '10.10.4.105', '10.10.4.104'],
        'prod-ext': ['10.20.0.237', '10.20.0.238', '10.20.0.239']
    }

    base_dir = os.path.dirname(__file__)
    browser_profile = os.path.join(base_dir, 'browser_profile_noc')
    auth_state_file = os.path.join(base_dir, 'noc_auth_state.json')

    def seleccionar_select2(label, valor, esperar_sugerencia=False):
        selector = f'[data-fname="{label}"] .select2-choice'
        page.click(selector)
        page.keyboard.type(valor, delay=0)
        timeout = 30000 if esperar_sugerencia else 2000
        try:
            page.wait_for_selector('.select2-results li.select2-result-selectable', timeout=timeout)
        except:
            if not esperar_sugerencia:
                page.wait_for_timeout(50)
        page.keyboard.press('Enter')

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=browser_profile,
            headless=False,
            slow_mo=0
        )

        if os.path.exists(auth_state_file):
            with open(auth_state_file, 'r') as f:
                state = json.load(f)
                if state.get('cookies'):
                    context.add_cookies(state['cookies'])

        def cleanup():
            try:
                context.close()
            except:
                pass

        atexit.register(cleanup)

        page = context.new_page()
        page.goto("https://noc-mesa.buenosaires.gob.ar/WorkOrder.do?woMode=newWO&reqTemplate=4201")
        page.wait_for_load_state('domcontentloaded')

        page.wait_for_selector('[data-fname="requester"], #username', timeout=10000)

        if page.locator('#username').count() > 0:
            print("Sesión expirada. Iniciando login...")
            page.locator('#username').click()
            page.keyboard.type(config.get('cuit', ''))

            noc_password = config.get('password', '')
            if noc_password:
                page.locator('#password').click()
                page.keyboard.type(noc_password)
                page.wait_for_timeout(300)
                page.click('#loginSDPage')
                print("Credenciales completadas automáticamente.")
            else:
                print("Usuario completado. Ingresá tu contraseña en el navegador.")

            try:
                page.wait_for_selector('[data-fname="requester"]', timeout=0)
                context.storage_state(path=auth_state_file)
                print("Sesión guardada.")
            except:
                print("No hubo login")
                context.close()
                return

        page.wait_for_timeout(500)

        # === SOLICITANTE ===
        seleccionar_select2('requester', config['user'], esperar_sugerencia=True)

        # === MINISTERIO/REPARTICION ===
        seleccionar_select2('level', 'ASI')

        # === DIRECCIÓN ===
        seleccionar_select2('udf_fields.udf_pick_915', 'DGISIS')

        # === UBICACION DEL PAQUETE INSTALABLE ===
        page.fill('#for_udf_fields\\.udf_sline_916', '-')

        # === IP NODOS ===
        ips_ambiente = IP_NODO_MAP[ambiente]
        page.fill('#for_udf_fields\\.udf_sline_603', ', '.join(ips_ambiente))

        # === SUBCATEGORIA ===
        seleccionar_select2('subcategory', 'ASSESSMENT')

        # === APLICACION ===
        page.fill('#for_udf_fields\\.udf_sline_914', componente)

        # === VERSION ===
        page.fill('#for_udf_fields\\.udf_sline_902', version)

        # === ASUNTO ===
        page.fill('#for_subject', f"Assessment sobre {componente} v{version}")

        # === DESCRIPCION ===
        url_linea = f'<br><br><a href="{url}" target="_blank">{url}</a><br><br>' if url else ''
        descripcion = f'<div>Buen día,<br><br>Por favor realizar el assessment del componente {componente} v{version}{url_linea}Adjunto manual de usuario y collection postman.<br><br>Quedo atento, gracias<br><br></div>'

        description_frame = page.frame_locator('iframe.ze_area').first
        description_frame.locator('body').evaluate(f'''
            (body) => {{
                body.innerHTML = `{descripcion}`;
            }}
        ''')

        page.evaluate("""
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
                <h2 style="margin:0 0 10px; color:#2d6cdf; font-size:22px;">📎</h2>
                <p style="font-size:15px; color:#333; margin-bottom:16px; line-height:1.4;">
                No te olvides de adjuntar la<br>
                <strong>collection de Postman</strong><br>
                y el <strong>manual de usuario</strong>.
                </p>
                <button id="cerrar-modal-recordatorio" style="
                background:#2d6cdf;
                color:white;
                border:none;
                border-radius:6px;
                padding:8px 16px;
                font-size:14px;
                cursor:pointer;
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

        print("\n[Cerrá el navegador o presioná Enter para finalizar...]")

        import threading
        closed = threading.Event()

        def on_close():
            closed.set()

        page.on('close', on_close)

        def wait_input():
            try:
                input()
                closed.set()
            except:
                pass

        input_thread = threading.Thread(target=wait_input, daemon=True)
        input_thread.start()

        closed.wait()
        context.close()

def main():
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('componente')
        parser.add_argument('version')
        parser.add_argument('ambiente', choices=['qa', 'dev', 'hml', 'prod-int', 'prod-ext'])
        parser.add_argument('url', nargs='?', default='')
        args = parser.parse_args()

        crear_ticket_assessment(args.componente, args.version, args.ambiente, args.url)
    else:
        print("=== CREAR TICKET DE ASSESSMENT ===\n")

        componente = input("Componente: ").strip()
        version = input("Versión: ").strip()

        print("\nAmbientes disponibles: qa, dev, hml, prod-int, prod-ext")
        ambiente = input("Ambiente: ").strip().lower()
        while ambiente not in ['qa', 'dev', 'hml', 'prod-int', 'prod-ext']:
            print("Ambiente inválido. Usá: qa, dev, hml, prod-int o prod-ext")
            ambiente = input("Ambiente: ").strip().lower()

        url = input("URL (opcional, Enter para omitir): ").strip()

        print("\nCreando ticket...")
        crear_ticket_assessment(
            componente=componente,
            version=version,
            ambiente=ambiente,
            url=url if url else ""
        )

if __name__ == '__main__':
    main()
