from playwright.sync_api import sync_playwright
import sys
import json
import os
import atexit

# Cargar configuración
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if not os.path.exists(config_path):
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

def crear_ticket_deploy(componente, version, ambiente, url="", fecha=None, hora=None):
    AMBIENTE_MAP = {
        'dev': 'DEV',
        'qa': 'QA',
        'hml': 'Homologación',
        'prd': 'Producción'
    }

    # Rutas
    base_dir = os.path.dirname(__file__)
    browser_profile = os.path.join(base_dir, 'browser_profile_noc')
    auth_state_file = os.path.join(base_dir, 'noc_auth_state.json')

    def seleccionar_select2(label, valor, esperar_sugerencia=False):
        selector = f'[data-fname="{label}"] .select2-choice'
        page.click(selector)

        page.keyboard.type(valor)

        if esperar_sugerencia:
            # Esperar a que aparezca al menos una opción en el dropdown
            page.wait_for_selector(
                '.select2-results li.select2-result-selectable',
                timeout=30000
            )

        page.keyboard.press('Enter')

    with sync_playwright() as p:
        # Usar contexto persistente
        context = p.chromium.launch_persistent_context(
            user_data_dir=browser_profile,
            headless=False,
            slow_mo=0
        )

        # Cargar cookies guardadas si existen
        if os.path.exists(auth_state_file):
            with open(auth_state_file, 'r') as f:
                state = json.load(f)
                if state.get('cookies'):
                    context.add_cookies(state['cookies'])

        # Registrar cierre limpio al salir (incluyendo Ctrl+C)
        def cleanup():
            try:
                context.close()
            except:
                pass

        atexit.register(cleanup)

        page = context.new_page()

        page.goto("https://noc-mesa.buenosaires.gob.ar/WorkOrder.do?woMode=newWO&reqTemplate=9304")
        page.wait_for_load_state('domcontentloaded')

        # Detectar si estamos logueados o se necesita login
        try:
            # Intentar encontrar el campo de solicitante (existe si estás logueado)
            page.wait_for_selector('[data-fname="requester"]', timeout=5000)
        except:
            # No encontró el formulario, debe estar en login
            print("Sesión expirada. Se requiere login manual")

            # Esperar a que el usuario se loguee (sin límite de tiempo)
            try:
                page.wait_for_selector('[data-fname="requester"]', timeout=0)
                # Guardar sesión explícitamente (funciona incluso con Ctrl+C después)
                context.storage_state(path=auth_state_file)
                print("Sesión guardada.")
            except:
                print("No hubo login")
                context.close()
                return

        page.wait_for_timeout(500)

        # === SOLICITANTE ===
        seleccionar_select2('requester', config['noc_user'], esperar_sugerencia=True)
        
        # === MINISTERIO/REPARTICION ===
        seleccionar_select2('level', 'ASI')
        
        # === EDIFICIO ===
        seleccionar_select2('udf_fields.udf_pick_310', 'HIT 8')
        
        # === SOLICITA UN DEPLOY ===
        page.click('[data-fname="udf_fields.udf_pick_11106"] .select2-choice')
        page.keyboard.press('ArrowDown')  # "Sin especificar"
        page.keyboard.press('ArrowDown')  # "SI"
        page.keyboard.press('Enter')
        
        # === UBICACION DEL PAQUETE INSTALABLE ===
        page.fill('#for_udf_fields\\.udf_sline_908', '-')
        
        # === NOMBRE IMAGEN EN QUAY ===
        imagen_quay = f"{componente}:{version}"
        page.fill('#for_udf_fields\\.udf_sline_10801', imagen_quay)
        
        # === CATEGORIA ===
        seleccionar_select2('category', 'se')
        
        # === SUBCATEGORIA ===
        seleccionar_select2('subcategory', 'ad')
        
        # === ARTICULO ===
        seleccionar_select2('item', 'dep')
        
        # === APLICACION ===
        page.fill('#for_udf_fields\\.udf_sline_914', componente)
        
        # === TIPO DE AMBIENTE ===
        ambiente_valor = AMBIENTE_MAP.get(ambiente.lower(), ambiente.upper())
        seleccionar_select2('udf_fields.udf_pick_307', ambiente_valor)
        
        # === VERSION ===
        page.fill('#for_udf_fields\\.udf_sline_902', version)
        
        # === ASUNTO ===
        asunto = f"Deploy {ambiente.upper()} {componente} {version}"
        page.fill('#for_subject', asunto)
        
        # === DESCRIPCION ===
        
        if fecha and hora:
            linea_fecha_hora = f'<span class="size" style="font-size: 20px"><span class="colour" style="color:#ff0000">Desplegar el {fecha} a las {hora}hs</span></span><br><br>'
        else:
            linea_fecha_hora = ''
        
        url_linea = f'<br><br><a href="{url}" target="_blank">{url}</a><br><br>' if url else ''
        
        descripcion = f'''<div>Buenas,<br><br>{linea_fecha_hora}</div><div>Solicito deploy en {ambiente.upper()} del componente {componente} {version}{url_linea}<br>Quedo atento, gracias<br><br></div>'''


        description_frame = page.frame_locator('iframe.ze_area').first
        description_frame.locator('body').evaluate(f'''
            (body) => {{
                body.innerHTML = `{descripcion}`;
            }}
        ''')
    
        page.click('input[value="DEPLOY STANDARD"]')

        if fecha and hora:
            print(f"  Deploy programado: {fecha} a las {hora}hs")
        if url:
            print(f"  URL: {url}")

        print("\n[Cerrá el navegador o presioná Enter para finalizar...]")

        # Esperar cierre del navegador o Enter del usuario
        import threading
        closed = threading.Event()

        def on_close():
            closed.set()

        page.on('close', on_close)

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
        context.close()

def main():
    import sys
    
    # Si hay argumentos, usar modo CLI
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('componente')
        parser.add_argument('version')
        parser.add_argument('ambiente', choices=['dev', 'qa', 'hml', 'prod'])
        parser.add_argument('url', nargs='?', default='')
        parser.add_argument('fecha', nargs='?', default=None)
        parser.add_argument('hora', nargs='?', default=None)
        args = parser.parse_args()
        
        crear_ticket_deploy(args.componente, args.version, args.ambiente, 
                           args.url, args.fecha, args.hora)
    else:
        # Preguntar interactivamente
        componente = input("Componente: ").strip()
        version = input("Versión: ").strip()
        print("\nAmbientes disponibles: qa, hml, prd")
        ambiente = input("Ambiente: ").strip().lower()
        while ambiente not in ['qa', 'hml', 'prd']:
            print("Ambiente inválido. Usá: qa, hml o prd")
            ambiente = input("Ambiente: ").strip().lower()
        url = input("URL (opcional, Enter para omitir): ").strip()
        fecha = input("Fecha del deploy (ej: 13/11, Enter para omitir): ").strip()
        hora = None
        if fecha:
            hora = input("Hora del deploy (ej: 14:00): ").strip()
        
        crear_ticket_deploy(
            componente=componente,
            version=version,
            ambiente=ambiente,
            url=url if url else "",
            fecha=fecha if fecha else None,
            hora=hora if hora else None
        )

if __name__ == '__main__':
    main()