import re

TAGS_VALIDOS = ('RC', 'BETA', 'HOTFIX', 'FIX')

def parsear_url_git(url):
    """
    Extrae (componente, version, tag) de una URL de GitLab tipo:
      https://repositorio-asi.buenosaires.gob.ar/<namespace>/<componente>/-/tree/<version>-<TAG>
      https://repositorio-asi.buenosaires.gob.ar/<namespace>/<componente>/-/blob/<version>-<TAG>/CHANGELOG.md?ref_type=tags
      https://repositorio-asi.buenosaires.gob.ar/<namespace>/<componente>/-/tags/v<version>-<TAG>

    El TAG puede venir numerado (RC, FIX2, RC-3, HOTFIX02).

    Devuelve None si no pudo parsear componente, versión y tag.
    """
    match = re.search(r'/([^/]+)/-/(?:tree|blob|tags)/([^/?]+)', url.strip())
    if not match:
        return None

    componente = match.group(1)
    ref = match.group(2)

    # El tag puede venir numerado: FIX2, RC-3, HOTFIX02.
    tag_pattern = '|'.join(TAGS_VALIDOS)
    ref_match = re.match(rf'^v?(.+)-((?:{tag_pattern})-?\d*)$', ref, re.IGNORECASE)
    if not ref_match:
        return None

    version = ref_match.group(1)
    tag = ref_match.group(2).upper()

    return componente, version, tag
