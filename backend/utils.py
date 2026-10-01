# -*- coding: utf-8 -*-
"""Utilidades compartidas: normalización de texto, claves de cotejo y
decodificación tolerante de los ficheros de AbsysNet."""

import html
import re
import unicodedata

_RE_NO_ALFANUM = re.compile(r"[^A-Z0-9 ]")
_ARTICULOS_INICIALES = {"EL", "LA", "LOS", "LAS", "UN", "UNA", "UNOS", "UNAS",
                        "THE", "A", "AN", "LE", "LES", "DER", "DIE", "DAS", "IL"}


def sin_entidades(texto):
    """«Garc&#237;a M&#225;rquez» -> «García Márquez». La base de la red trae
    algunos campos con entidades HTML/XML, a veces dobles (&amp;#237;)."""
    if texto is None or "&" not in str(texto):
        return texto
    texto = str(texto)
    for _ in range(2):
        nuevo = html.unescape(texto)
        if nuevo == texto:
            break
        texto = nuevo
    return texto


def sin_acentos(texto) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto))
                   if not unicodedata.combining(c))


def norm_clave(texto) -> str:
    """Mayúsculas, sin acentos y sin puntuación: base para comparar
    títulos y autores."""
    s = sin_acentos(str(sin_entidades(texto) or "")).upper().replace("&", " Y ")
    return re.sub(r"\s+", " ", _RE_NO_ALFANUM.sub(" ", s)).strip()


def clave_titulo(titulo) -> str:
    """Título sin subtítulo (corta en ' : ' o ' = ') y sin artículo inicial."""
    base = re.split(r"\s+[:=]\s+", str(sin_entidades(titulo) or ""), maxsplit=1)[0]
    palabras = norm_clave(base).split()
    if palabras and palabras[0] in _ARTICULOS_INICIALES:
        palabras = palabras[1:]
    return " ".join(palabras)


def clave_autor(autor) -> str:
    """Primer apellido normalizado (AbsysNet escribe 'APELLIDO, Nombre')."""
    palabras = norm_clave(str(sin_entidades(autor) or "").split(",")[0]).split()
    return palabras[0] if palabras else ""


def claves_isbn(isbn) -> set:
    """Claves comparables de un ISBN: el número limpio y el núcleo de 9
    dígitos, común a la versión ISBN-10 y a la ISBN-13 con prefijo 978."""
    limpio = re.sub(r"[^0-9X]", "", str(isbn or "").upper())
    if len(limpio) < 10:
        return set()
    claves = {limpio}
    if len(limpio) == 13 and limpio.startswith("978"):
        claves.add(limpio[3:12])
    elif len(limpio) == 10:
        claves.add(limpio[:9])
    return claves


def clave_id(v):
    """Normaliza un identificador a texto.

    En la base `id_sistema` y `codigo_barras` son TEXT; si se comparan contra
    enteros la búsqueda falla en silencio y todo el fondo sale como «Sin
    determinar»."""
    if v is None:
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s or None


def decodificar_bytes(data: bytes) -> str:
    """Los listados de AbsysNet llegan en codificaciones distintas según el
    navegador y la versión: se prueban por orden y, como último recurso, se
    sustituyen los caracteres ilegibles en vez de fallar."""
    if isinstance(data, str):
        return data
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def leer_texto_tolerante(ruta: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(ruta, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(ruta, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


# --- Búsquedas de texto sobre listas de registros --------------------------

def mask_comodin(valor, patron: str) -> bool:
    """Coincidencia por comienzo, con `*` como comodín en cualquier posición.
    Se usa en signaturas: «32*», «I 5*» o «*(460*»."""
    texto = str(valor or "").upper().strip()
    if "*" in patron:
        return bool(re.match(re.escape(patron).replace(r"\*", ".*"), texto))
    return texto.startswith(patron)


def mask_contiene(valor, busqueda: str) -> bool:
    """Coincidencia por subcadena, ignorando acentos y mayúsculas."""
    texto = sin_acentos(str(valor or "")).upper()
    busqueda = busqueda.strip().upper()
    if "*" in busqueda:
        return bool(re.search(re.escape(sin_acentos(busqueda)).replace(r"\*", ".*"), texto))
    return sin_acentos(busqueda) in texto


def mask_multitoken(valor, busqueda: str) -> bool:
    """Cada palabra de la búsqueda debe aparecer, en cualquier orden:
    «novia paz» encuentra «La novia de la paz»."""
    tokens = [tok for tok in sin_acentos(busqueda.strip().upper()).split() if tok]
    if not tokens:
        return False
    texto = sin_acentos(str(valor or "")).upper()
    return all(tok in texto for tok in tokens)


def formato_miles(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def isbn13(valor):
    """Normaliza un ISBN a 13 cifras (los de 10 se convierten). None si no lo es."""
    import re as _re
    d = _re.sub(r"[^0-9Xx]", "", str(valor or "")).upper()
    if len(d) == 10:
        base = "978" + d[:9]
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))
        return base + str((10 - total % 10) % 10)
    return d if len(d) == 13 and d.isdigit() else None
