# assessment.py
from playwright.sync_api import sync_playwright
import sys

def crear_ticket_assessment(componente, version, ambiente, url=""):
    IP_NODO_MAP = {
        'qa': ['10.9.10.75', '10.9.10.76', '10.9.10.116', '10.9.10.156', '10.9.10.157', '10.9.11.188', '10.9.11.187'],
        'dev': ['10.9.10.75', '10.9.10.76', '10.9.10.116', '10.9.10.156', '10.9.10.157', '10.9.11.188', '10.9.11.187'],
        'hml': ['10.12.0.26', '10.12.0.27', '10.12.0.21', '10.12.2.173', '10.12.2.203', '10.12.2.204', '10.12.2.205', '10.12.2.206'],
        'prod-int': ['10.10.4.106', '10.10.4.105', '10.10.4.104'],
        'prod-ext': ['10.20.0.237', '10.20.0.238', '10.20.0.239']
    }

    def seleccionar_select2(label, valor, delay=False):
        selector = f'[data-fname="{label}"] .select2-choice'
        page.click(selector)
        page.keyboard.type(valor)
        if delay:
            page.wait_for_timeout(delay)
        page.keyboard.press('Enter')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=0)
        try:
            context = browser.new_context(storage_state="noc_auth_state.json")
        except:
            context = browser.new_context()
        
        page = context.new_page()

        page.goto("https://noc-mesa.buenosaires.gob.ar/WorkOrder.do?woMode=newWO&reqTemplate=4201")
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(100)
        
        try:
            page.wait_for_selector('[data-fname="requester"]', timeout=5000)
        except:
            print("Sesión expirada. Se requiere login manual")
            try:
                page.wait_for_selector('[data-fname="requester"]', timeout=60000)
                context.storage_state(path="noc_auth_state.json")
                print("Sesión guardada.")
            except:
                print("No hubo login")
                context.close()
                return
        
        seleccionar_select2('requester', 'lmardones', delay=5500)
        
        seleccionar_select2('level', 'ASI')
        
        seleccionar_select2('udf_fields.udf_pick_915', 'DGISIS')
        
        page.fill('#for_udf_fields\\.udf_sline_916', '-')
        
        ips_ambiente = IP_NODO_MAP[ambiente]
        ip_nodo_texto = ', '.join(ips_ambiente)
        page.fill('#for_udf_fields\\.udf_sline_603', ip_nodo_texto)
        
        seleccionar_select2('subcategory', 'ASSESSMENT')
        
        page.fill('#for_udf_fields\\.udf_sline_914', componente)
        
        page.fill('#for_udf_fields\\.udf_sline_902', version)
        
        asunto = f"Assessment sobre {componente} v{version}"
        page.fill('#for_subject', asunto)
        
        url_linea = f'<br><br><a href="{url}" target="_blank">{url}</a><br><br>' if url else ''
        
        descripcion = f'''<div>Buen día,<br><br>Por favor realizar el assessment del componente {componente} v{version}{url_linea}Adjunto manual de usuario y collection postman.<br><br>Quedo atento, gracias<br><br></div>'''
        
        description_frame = page.frame_locator('iframe.ze_area').first
        description_frame.locator('body').evaluate(f'''
            (body) => {{
                body.innerHTML = `{descripcion}`;
            }}
        ''')

        page.evaluate("""
        () => {
        if (document.getElementById('modal-recordatorio')) return;

        // Fondo oscuro semitransparente
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

        // Contenedor del modal (más chico)
        const modal = document.createElement('div');
        modal.style.background = 'white';
        modal.style.borderRadius = '10px';
        modal.style.boxShadow = '0 6px 20px rgba(0,0,0,0.25)';
        modal.style.padding = '20px 28px';
        modal.style.maxWidth = '320px';
        modal.style.textAlign = 'center';
        modal.style.fontFamily = 'system-ui, sans-serif';
        modal.style.animation = 'fadeIn 0.3s ease';

        // Contenido del modal
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

        // Animación de entrada
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
        
        input("\n[Presioná Enter para cerrar el navegador...]")
        context.close()

def main():
    import sys
    
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