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


def guardar_dns(componente, ambiente, dns):
    """Guarda (o pisa) el DNS del componente para el ambiente."""
    comp = normalizar_componente(componente)
    amb = normalizar_ambiente(ambiente)
    valor = (dns or '').strip()
    if not comp or not amb or not valor:
        return False

    try:
        with _conectar() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO dns (componente, ambiente, dns, actualizado) '
                'VALUES (?, ?, ?, ?)',
                (comp, amb, valor, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
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
    """Devuelve [(componente, ambiente, dns, actualizado), ...]."""
    try:
        with _conectar() as conn:
            if componente:
                return conn.execute(
                    'SELECT componente, ambiente, dns, actualizado FROM dns '
                    'WHERE componente = ? ORDER BY componente, ambiente',
                    (normalizar_componente(componente),)
                ).fetchall()
            return conn.execute(
                'SELECT componente, ambiente, dns, actualizado FROM dns '
                'ORDER BY componente, ambiente'
            ).fetchall()
    except sqlite3.Error as e:
        print(f"No se pudo leer la base de DNS: {e}")
        return []


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
        for comp, amb, dns, actualizado in filas:
            print(f"{comp:<{ancho_comp}}  {amb:<{ancho_amb}}  {dns}  ({actualizado})")

    elif comando == 'set':
        if len(args) < 4:
            print(uso)
            sys.exit(1)
        if guardar_dns(args[1], args[2], args[3]):
            print(f"Guardado: {normalizar_componente(args[1])} [{normalizar_ambiente(args[2])}] -> {args[3].strip()}")
        else:
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
