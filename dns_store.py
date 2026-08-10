"""Base de datos local (SQLite) de DNS por componente y ambiente.

La primera vez que se carga el DNS de un componente para un ambiente queda
guardado; las siguientes corridas lo autocompletan.
"""
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dns.db')

# noc usa dev/qa/hml/prd y assessment usa qa/dev/hml/prod-int/prod-ext.
# Los tres ambientes de producción comparten el mismo DNS guardado.
AMBIENTE_CANONICO = {
    'dev': 'dev',
    'qa': 'qa',
    'hml': 'hml',
    'prd': 'prod',
    'prod-int': 'prod',
    'prod-ext': 'prod',
}


def normalizar_ambiente(ambiente):
    amb = (ambiente or '').strip().lower()
    return AMBIENTE_CANONICO.get(amb, amb)


def normalizar_componente(componente):
    return (componente or '').strip().lower()


def _conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dns (
            componente  TEXT NOT NULL,
            ambiente    TEXT NOT NULL,
            dns         TEXT NOT NULL,
            actualizado TEXT NOT NULL,
            PRIMARY KEY (componente, ambiente)
        )
    ''')
    # 'origen' distingue lo cargado a mano de lo importado de OpenShift, para
    # que un re-import no pise un DNS que alguien corrigió a mano.
    columnas = [c[1] for c in conn.execute('PRAGMA table_info(dns)')]
    if 'origen' not in columnas:
        conn.execute("ALTER TABLE dns ADD COLUMN origen TEXT NOT NULL DEFAULT 'manual'")
    return conn


def obtener_dns(componente, ambiente):
    """Devuelve el DNS guardado para el componente/ambiente, o None."""
    comp = normalizar_componente(componente)
    amb = normalizar_ambiente(ambiente)
    if not comp or not amb:
        return None

    try:
        with _conectar() as conn:
            fila = conn.execute(
                'SELECT dns FROM dns WHERE componente = ? AND ambiente = ?',
                (comp, amb)
            ).fetchone()
    except sqlite3.Error as e:
        print(f"No se pudo leer la base de DNS: {e}")
        return None

    return fila[0] if fila else None


def guardar_dns(componente, ambiente, dns, origen='manual'):
    """Guarda (o pisa) el DNS del componente para el ambiente."""
    comp = normalizar_componente(componente)
    amb = normalizar_ambiente(ambiente)
    valor = (dns or '').strip()
    if not comp or not amb or not valor:
        return False

    try:
        with _conectar() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO dns (componente, ambiente, dns, actualizado, origen) '
                'VALUES (?, ?, ?, ?, ?)',
                (comp, amb, valor, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), origen)
            )
    except sqlite3.Error as e:
        print(f"No se pudo guardar el DNS: {e}")
        return False

    return True


def borrar_dns(componente, ambiente=None):
    """Borra el DNS de un componente (de un ambiente, o de todos). Devuelve cuántos borró."""
    comp = normalizar_componente(componente)
    if not comp:
        return 0

    try:
        with _conectar() as conn:
            if ambiente:
                cur = conn.execute(
                    'DELETE FROM dns WHERE componente = ? AND ambiente = ?',
                    (comp, normalizar_ambiente(ambiente))
                )
            else:
                cur = conn.execute('DELETE FROM dns WHERE componente = ?', (comp,))
            return cur.rowcount
    except sqlite3.Error as e:
        print(f"No se pudo borrar el DNS: {e}")
        return 0


def listar_dns(componente=None):
    """Devuelve [(componente, ambiente, dns, actualizado, origen), ...]."""
    try:
        with _conectar() as conn:
            if componente:
                return conn.execute(
                    'SELECT componente, ambiente, dns, actualizado, origen FROM dns '
                    'WHERE componente LIKE ? ORDER BY componente, ambiente',
                    (f'%{normalizar_componente(componente)}%',)
                ).fetchall()
            return conn.execute(
                'SELECT componente, ambiente, dns, actualizado, origen FROM dns '
                'ORDER BY componente, ambiente'
            ).fetchall()
    except sqlite3.Error as e:
        print(f"No se pudo leer la base de DNS: {e}")
        return []


def _url_de_route(spec):
    host = (spec.get('host') or '').strip()
    if not host:
        return None
    esquema = 'https://' if spec.get('tls') else 'http://'
    return esquema + host + (spec.get('path') or '')


def _elegir_host(urls):
    """Entre varias routes del mismo componente/ambiente, elige la que corresponde.

    Descarta las pre-productivas (pre-qa, preqa) y prefiere el dominio corto
    'gcba.gob.ar' por sobre el interno del cluster '.apps.ocp4-*'. Si aun asi
    queda mas de una, devuelve None: se reporta como conflicto en vez de elegir
    cualquiera.
    """
    candidatos = sorted(urls)
    if len(candidatos) == 1:
        return candidatos[0]

    sin_pre = [u for u in candidatos if 'preqa' not in u and 'pre-qa' not in u
               and 'predev' not in u and 'pre-dev' not in u]
    if sin_pre:
        candidatos = sin_pre
    if len(candidatos) == 1:
        return candidatos[0]

    cortos = [u for u in candidatos if '.apps.ocp4' not in u]
    if len(cortos) == 1:
        return cortos[0]

    return None


def importar_routes(path, dry_run=False, force=False):
    """Importa los DNS de dev y qa desde un 'oc get routes -A -o json'.

    No pisa lo cargado a mano salvo force=True; si vuelve a importarse, sí
    actualiza lo que ya venía de OpenShift.
    """
    import json
    from collections import defaultdict

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"No se pudo leer {path}: {e}")
        return False

    candidatos = defaultdict(set)
    for item in data.get('items', []):
        meta = item.get('metadata', {})
        ns = meta.get('namespace', '')
        if ns.endswith('-dev'):
            amb = 'dev'
        elif ns.endswith('-qa'):
            amb = 'qa'
        else:
            continue
        url = _url_de_route(item.get('spec', {}))
        if url:
            candidatos[(normalizar_componente(meta.get('name')), amb)].add(url)

    nuevos, actualizados, protegidos, conflictos = [], [], [], []

    with _conectar() as conn:
        existentes = {
            (c, a): (d, o)
            for c, a, d, o in conn.execute('SELECT componente, ambiente, dns, origen FROM dns')
        }

    for (comp, amb), urls in sorted(candidatos.items()):
        elegida = _elegir_host(urls)
        if not elegida:
            conflictos.append((comp, amb, sorted(urls)))
            continue

        actual = existentes.get((comp, amb))
        if actual is None:
            nuevos.append((comp, amb, elegida))
        elif actual[0] == elegida:
            continue
        elif actual[1] == 'manual' and not force:
            protegidos.append((comp, amb, actual[0], elegida))
        else:
            actualizados.append((comp, amb, elegida))

    print(f"Routes leidas          : {sum(len(v) for v in candidatos.values())}")
    print(f"Componentes dev/qa     : {len(candidatos)}")
    print(f"  nuevos               : {len(nuevos)}")
    print(f"  a actualizar         : {len(actualizados)}")
    print(f"  sin cambios          : {len(candidatos) - len(nuevos) - len(actualizados) - len(protegidos) - len(conflictos)}")
    print(f"  protegidos (manual)  : {len(protegidos)}")
    print(f"  conflictos (omitidos): {len(conflictos)}")

    if protegidos:
        print("\nCargados a mano, NO se tocan (usa --force para pisarlos):")
        for comp, amb, viejo, nuevo in protegidos:
            print(f"  {comp} [{amb}]: {viejo}  <-  {nuevo}")

    if conflictos:
        print("\nVarias routes para el mismo componente, se omiten (cargalos con 'dns set'):")
        for comp, amb, urls in conflictos[:15]:
            print(f"  {comp} [{amb}]: {', '.join(urls)}")
        if len(conflictos) > 15:
            print(f"  ... y {len(conflictos) - 15} mas")

    if dry_run:
        print("\n(dry-run: no se guardo nada)")
        return True

    for comp, amb, url in nuevos + actualizados:
        guardar_dns(comp, amb, url, origen='ocp')

    print(f"\nGuardados: {len(nuevos) + len(actualizados)}")
    return True


def derivar_ambiente(destino='hml', dry_run=False):
    """Deriva los DNS de un ambiente cambiandole el sufijo a los de qa/dev.

    Solo aplica al patron corto '<algo>-{dev,qa}.gcba.gob.ar'. Los hosts del
    tipo '.apps.ocp4-dev...' NO se derivan: ese 'ocp4-dev' es el nombre del
    cluster, no el ambiente, y el cluster de destino tiene otro dominio.

    Los DNS que genera son inferidos, no verificados contra el cluster: quedan
    con origen 'derivado' para que un import real los pise despues.
    """
    import re

    destino = normalizar_ambiente(destino)
    patron = re.compile(r'^(https?://.*)-(?:dev|qa)(\.gcba\.gob\.ar.*)$')

    with _conectar() as conn:
        filas = conn.execute(
            'SELECT componente, ambiente, dns FROM dns WHERE ambiente IN (?, ?)',
            ('qa', 'dev')
        ).fetchall()
        ya_existen = {
            c for (c,) in conn.execute(
                'SELECT componente FROM dns WHERE ambiente = ?', (destino,)
            )
        }

    # qa primero: si un componente esta en los dos, se deriva desde qa.
    fuentes = {}
    for comp, amb, dns in filas:
        if comp not in fuentes or amb == 'qa':
            fuentes[comp] = (amb, dns)

    derivados, omitidos, existentes = [], [], 0
    for comp, (amb, dns) in sorted(fuentes.items()):
        if comp in ya_existen:
            existentes += 1
            continue
        match = patron.match(dns)
        if not match or '.apps.ocp4' in dns:
            omitidos.append((comp, dns))
            continue
        derivados.append((comp, f"{match.group(1)}-{destino}{match.group(2)}", amb))

    print(f"Componentes con dev/qa    : {len(fuentes)}")
    print(f"  a derivar a '{destino}'      : {len(derivados)}")
    print(f"  ya tenian {destino}          : {existentes}")
    print(f"  sin patron derivable    : {len(omitidos)}")

    if derivados:
        print("\nEjemplos:")
        for comp, url, amb in derivados[:5]:
            print(f"  {comp}: {url}   (desde {amb})")

    if dry_run:
        print("\n(dry-run: no se guardo nada)")
        return True

    for comp, url, _ in derivados:
        guardar_dns(comp, destino, url, origen='derivado')

    print(f"\nGuardados: {len(derivados)}")
    return True


def pedir_dns(componente, ambiente):
    """Pide el DNS por consola usando lo guardado como valor por defecto.

    Enter acepta el guardado, '-' omite el DNS en este ticket sin borrarlo,
    y cualquier otro valor lo actualiza. Devuelve el DNS a usar ('' si ninguno).
    """
    guardado = obtener_dns(componente, ambiente)

    if guardado:
        amb = normalizar_ambiente(ambiente)
        print(f"DNS guardado para {normalizar_componente(componente)} [{amb}]: {guardado}")
        respuesta = input("URL del componente (Enter para usar el guardado, '-' para omitir): ").strip()
        if not respuesta:
            return guardado
        if respuesta == '-':
            return ''
    else:
        respuesta = input("URL del componente (DNS, opcional, Enter para omitir): ").strip()
        if not respuesta:
            return ''

    if guardar_dns(componente, ambiente, respuesta):
        print(f"DNS guardado para {normalizar_componente(componente)} [{normalizar_ambiente(ambiente)}]")
    return respuesta


def resolver_dns(componente, ambiente, url):
    """Resuelve el DNS en modo CLI: si vino por argumento lo guarda, si no lo busca."""
    if url:
        guardar_dns(componente, ambiente, url)
        return url

    guardado = obtener_dns(componente, ambiente)
    if guardado:
        print(f"DNS: {guardado} (guardado)")
        return guardado
    return ''


def main():
    uso = (
        "Uso:\n"
        "  dns list [componente]              Lista los DNS guardados\n"
        "  dns set <componente> <ambiente> <dns>   Guarda o actualiza un DNS\n"
        "  dns del <componente> [ambiente]    Borra un DNS (o todos los del componente)\n"
        "  dns import <routes.json> [--dry-run] [--force]\n"
        "                                     Importa dev y qa desde 'oc get routes -A -o json'\n"
        "  dns derivar <ambiente> [--dry-run] Deriva un ambiente cambiando el sufijo de qa/dev\n"
        f"\nAmbientes: {', '.join(sorted(set(AMBIENTE_CANONICO)))}"
        "\n(prd, prod-int y prod-ext comparten el mismo DNS)"
    )

    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help', 'help'):
        print(uso)
        return

    comando = args[0]

    if comando == 'list':
        filas = listar_dns(args[1] if len(args) > 1 else None)
        if not filas:
            print("No hay DNS guardados.")
            return
        ancho_comp = max(len(f[0]) for f in filas)
        ancho_amb = max(len(f[1]) for f in filas)
        marcas = {'manual': '  *', 'derivado': '  ~'}
        for comp, amb, dns, actualizado, origen in filas:
            print(f"{comp:<{ancho_comp}}  {amb:<{ancho_amb}}  {dns}{marcas.get(origen, '')}")
        print(f"\n{len(filas)} entradas  (* = cargada a mano, ~ = derivada sin verificar)")

    elif comando == 'set':
        if len(args) < 4:
            print(uso)
            sys.exit(1)
        if guardar_dns(args[1], args[2], args[3]):
            print(f"Guardado: {normalizar_componente(args[1])} [{normalizar_ambiente(args[2])}] -> {args[3].strip()}")
        else:
            sys.exit(1)

    elif comando == 'derivar':
        if len(args) < 2:
            print(uso)
            sys.exit(1)
        derivar_ambiente(args[1], dry_run='--dry-run' in args)

    elif comando == 'import':
        if len(args) < 2:
            print(uso)
            sys.exit(1)
        ok = importar_routes(
            args[1],
            dry_run='--dry-run' in args,
            force='--force' in args
        )
        if not ok:
            sys.exit(1)

    elif comando == 'del':
        if len(args) < 2:
            print(uso)
            sys.exit(1)
        borrados = borrar_dns(args[1], args[2] if len(args) > 2 else None)
        print(f"Borrados: {borrados}")

    else:
        print(uso)
        sys.exit(1)


if __name__ == '__main__':
    main()
