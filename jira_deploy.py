# jira_deploy.py
from playwright.sync_api import sync_playwright
import sys
import re

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if not os.path.exists(config_path):
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

def crear_ticket_jira(componente, version, tag, ticket_noc):
    
    def normalizar_tag(tag):
        match = re.match(r'([A-Z]+)-?(\d+)', tag.upper())
        if match:
            prefijo = match.group(1)
            numero = int(match.group(2))
            return f"{prefijo}-{numero:02d}"
        return tag
    
    with sync_playwright() as p:
        print("=== PASO 1: Obtener datos del ticket NOC ===\n")
        
        noc_browser = None
        try:
            noc_browser = p.chromium.launch(headless=True)
            noc_context = noc_browser.new_context(storage_state="noc_auth_state.json")
            noc_page = noc_context.new_page()
            noc_url = f"https://noc-mesa.buenosaires.gob.ar/WorkOrder.do?woMode=viewWO&woID={ticket_noc}"
            
            noc_page.goto(noc_url, timeout=30000)
            noc_page.wait_for_load_state('domcontentloaded')
            
            noc_page.wait_for_selector('#req-desc-body', timeout=5000)
            print("Sesión NOC válida")
            
        except:
            print("Sesión NOC expirada o no existe. Abriendo navegador visible para login...")
            if noc_browser:
                noc_browser.close()
            
            noc_browser = p.chromium.launch(headless=False)
            try:
                noc_context = noc_browser.new_context(storage_state="noc_auth_state.json")
            except:
                noc_context = noc_browser.new_context()
            
            noc_page = noc_context.new_page()
            noc_url = f"https://noc-mesa.buenosaires.gob.ar/WorkOrder.do?woMode=viewWO&woID={ticket_noc}"
            
            noc_page.goto(noc_url)
            noc_page.wait_for_load_state('domcontentloaded')
            
            try:
                noc_page.wait_for_selector('#req-desc-body', timeout=60000)
                noc_context.storage_state(path="noc_auth_state.json")
                
                noc_page.goto(noc_url)
                noc_page.wait_for_load_state('domcontentloaded')
            except:
                noc_browser.close()
                return
        
        # Extraer descripción
        try:
            descripcion_elemento = noc_page.locator('#req-desc-body')
            descripcion = descripcion_elemento.inner_text()
        except Exception as e:
            descripcion = f"Deploy {componente} {version}"
        
        # Extraer URL GIT
        url_git = ""
        try:
            url_git_elem = noc_page.locator('p[data-name="udf_sline_11422"]')
            url_git = url_git_elem.inner_text().strip()
            if url_git:
                print(f"URL GIT obtenida: {url_git}")
        except Exception as e:
            print(f"No se encontró URL GIT: {e}")
        
        print("\nDatos extraídos del NOC")
        
        noc_browser.close()
        
        # PASO 2: Crear ticket en JIRA
        
        browser = p.chromium.launch(headless=False)
        
        try:
            jira_context = browser.new_context(storage_state="jira_auth_state.json")
        except:
            jira_context = browser.new_context()
        
        jira_page = jira_context.new_page()
        create_issue_url = "https://asijira.buenosaires.gob.ar/secure/CreateIssue!default.jspa"
        
        jira_page.goto(create_issue_url)
        jira_page.wait_for_load_state('domcontentloaded')
        
        # Verificar si aparece página de error de permisos
        try:
            error_msg = jira_page.locator('.aui-message-warning:has-text("No estás registrado")')
            if error_msg.is_visible(timeout=2000):
                jira_page.locator('a:has-text("Identificación")').click()
                jira_page.wait_for_load_state('domcontentloaded')
        except:
            pass
        
        # Verificar login
        try:
            jira_page.wait_for_selector('#project-field, #pid', timeout=5000)
        except:
            try:
                jira_page.wait_for_selector('#project-field, #pid', timeout=60000)
                jira_context.storage_state(path="jira_auth_state.json")
                
                jira_page.goto(create_issue_url)
                jira_page.wait_for_load_state('domcontentloaded')
            except:
                jira_context.close()
                browser.close()
                return
        
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
                <span>Cargá manualmente <strong>Proyecto</strong> y <strong>Tipo de Incidencia</strong> y seleccioná <strong>Siguiente</strong></span>
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
            jira_page.wait_for_selector('#summary', timeout=120000)
        except:
            jira_context.close()
            browser.close()
            return
        
        # Componente - intentar seleccionar solo si existe exactamente
        componente_seleccionado = False
        if componente:
            try:
                jira_page.locator('#components-textarea').click()
                jira_page.locator('#components-textarea').fill(componente)
                
                jira_page.wait_for_selector('#components-suggestions .aui-list-item', timeout=3000)
                
                try:
                    exact_match = jira_page.locator(f'#components-suggestions .aui-list-item a:has-text("{componente}")').first
                    texto_sugerencia = exact_match.inner_text()
                    
                    if texto_sugerencia.strip() == componente:
                        exact_match.click()
                        componente_seleccionado = True
                    else:
                        jira_page.locator('#components-textarea').clear()
                except:
                    jira_page.locator('#components-textarea').clear()
                    
            except Exception as e:
                print("Dejando el campo componente vacío")
        
        # Resumen
        resumen = f"Deploy {componente} {version}" if componente else f"Deploy {version}"
        jira_page.locator('#summary').click()
        jira_page.locator('#summary').fill(resumen)
        
        # Descripción
        try:
            jira_page.locator('li[data-mode="source"] button').click()
            jira_page.locator('#description').fill(descripcion)
        except Exception as e:
            print(f"No se pudo llenar descripción: {e}")
        
        # Versión
        jira_page.locator('#fixVersions-textarea').click()
        jira_page.locator('#fixVersions-textarea').fill(version)
        
        try:
            jira_page.wait_for_selector('#fixVersions-suggestions .aui-list-item', timeout=3000)
            jira_page.locator('#fixVersions-suggestions .aui-list-item').first.click()
        except Exception as e:
            print(f"No se pudo seleccionar versión automáticamente: {e}")
        
        # Tag
        tag_normalizado = normalizar_tag(tag)
        try:
            jira_page.locator('#customfield_11304').select_option(label=tag_normalizado)
        except Exception as e:
            print(f"No se pudo seleccionar tag: {e}")
        
        # Responsable Referente
        jira_page.locator('#customfield_10187-field').click()
        jira_page.locator('#customfield_10187-field').fill(config['jira_responsable'])
        try:
            jira_page.wait_for_selector('#customfield_10187-suggestions .aui-list-item', timeout=3000)
            jira_page.locator('#customfield_10187-suggestions .aui-list-item').first.click()
        except:
            pass
        
        # Nro Ticket ME
        jira_page.locator('#customfield_10500').click()
        jira_page.locator('#customfield_10500').fill(ticket_noc)
        
        # URL GIT
        if url_git:
            try:
                jira_page.locator('#customfield_10159').click()
                jira_page.locator('#customfield_10159').fill(url_git)
            except Exception as e:
                print(f"No se pudo llenar URL GIT: {e}")
        
        # Mostrar modal solo si NO se seleccionó componente
        if not componente_seleccionado:
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
        
        input("\nPresioná Enter para cerrar el navegador...")
        jira_context.close()
        browser.close()

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
        
        componente = input("Componente: ").strip()
        version = input("Versión (ej: 1.0.0): ").strip()
        tag = input("Tag (ej: RC-1 o RC-01): ").strip()
        ticket_noc = input("Nro Ticket NOC: ").strip()
        
        crear_ticket_jira(
            componente=componente,
            version=version,
            tag=tag,
            ticket_noc=ticket_noc
        )

if __name__ == '__main__':
    main()