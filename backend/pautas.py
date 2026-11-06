# -*- coding: utf-8 -*-
"""La colección frente a las pautas oficiales.

Las cifras se han copiado de los documentos, sin interpretar:

  IFLA      Directrices IFLA/UNESCO para el desarrollo del servicio de bibliotecas
            públicas, abril de 2001, ap. 4.6. Da cifras para el tamaño; para la
            composición solo dice «porcentajes similares» en los fondos reducidos.
  MINISTERIO  Ministerio de Cultura-CCAA, Consejo de Cooperación Bibliotecaria,
            Pautas para establecer una política de colecciones en una biblioteca
            pública, enero de 2010, pp. 23-27. Son valores para dimensionar una
            biblioteca nueva, «susceptibles de modificaciones».
  DIPUTACIO Columna «PDC Diputació» (Política de desenvolupament de la col·lecció
            de la Diputació de Barcelona, 2012; módulos L0/L1), tal como la recoge la
            Política de Desenvolupament de la Col·lecció de la Biblioteca Pau Vila
            de Molins de Rei, ap. 6.2-6.6. Esa es la fuente de que se dispone: no es
            el documento original de la Diputació ni una pauta de toda Catalunya.

Se trabaja con la sección estándar de cada ejemplar (`categoria_estandar`), que sale
de la signatura y no cambia aunque la biblioteca renombre sus secciones.

Las pautas no coinciden en sus apartados, y por eso se agrupan:
  · 4 + 8 + poesía + teatro: el Ministerio junta lingüística y literatura y aparta
    poesía y teatro; la Diputació aparta filología e incluye poesía y teatro en 8.
  · 9: la Diputació separa historia, geografía y biografía.
  · Ficción infantil: las franjas de edad de cada pauta no coinciden con I0-I3.
"""

import re

from backend import clasificacion

# --- Referencias ---------------------------------------------------------------
# (hasta_habitantes, documentos por habitante, colección inicial mínima y máxima).
# El último tramo aparece en el documento como «Más de 50000 habitantes», después de
# «De 50.000 a 100.000»: es una errata evidente por «más de 100.000».
TRAMOS_MINISTERIO = (
    (5_000, 2.5, 4_000, 5_500),
    (10_000, 2.5, 7_000, 12_500),
    (20_000, 2.0, 12_500, 20_000),
    (50_000, 2.0, 20_000, 65_000),
    (100_000, 1.5, 45_000, 80_000),
    (None, 1.5, 80_000, 95_000),
)
IFLA_LIBROS_MIN, IFLA_LIBROS_MAX, IFLA_FONDO_MINIMO = 1.5, 2.5, 2_500
TERCIO = 33.3

# clave: (% Ministerio sobre el fondo, % Diputació sobre los libros)
SECCIONES = (
    ("0", 4, 1),
    ("1", 2, 4.5),
    ("2", 1, 0.5),
    ("3", 4, 4.5),
    ("5", 4, 5),
    ("6", 5, 10),
    ("7", 7, 7),
    ("8", 4 + 1 + 1, 3.5 + 3.5),         # lingüística y literatura, poesía, teatro
    ("9", 9, 3 + 5 + 2),                 # historia, geografía, biografía
    ("novela", 19, 18),
    ("comic", 4, 4.5),
    ("jn", (3, 5), 3),                   # Ministerio: «en torno a un 3-5 %», aparte
    ("i_con", 7, 6),
    ("i_fic", 1 + 5 + 6, 9 + 4 + 2),     # prelectores + franjas de edad
    ("i_com", 1, 4),
)
GRUPO_DE_SECCION = {
    "0 - Generalidades": "0", "Enciclopedias (031)": "0",
    "1 - Filosofía": "1", "159.9 - Psicología": "1", "2 - Religión": "2",
    "3 - Ciencias Sociales": "3", "5 - Ciencias Puras": "5", "6 - Tecnología": "6",
    "7 - Arte / Deportes": "7", "4 - Lingüística": "8", "8 - Literatura": "8",
    "Poesía": "8", "Teatro": "8", "9 - Historia / Geografía": "9",
    "Ficción / Narrativa": "novela", "C (Comic Adultos)": "comic", "JN (Juvenil)": "jn",
    "IC (Comic Infantil)": "i_com", "IP (Infantil Poesía)": "i_fic", "IT (Infantil Teatro)": "i_fic",
    "I DVD (DVD Infantil)": "dvd", "DVD Audiovisual": "dvd",
}
_FICCION = {"novela", "comic", "jn", "i_fic", "i_com"}
_NO_FICCION = {"0", "1", "2", "3", "5", "6", "7", "9", "i_con"}


def _seccion(registro):
    return registro.get("categoria_estandar") or registro.get("categoria") or ""


def grupo(registro):
    seccion = _seccion(registro)
    if seccion in GRUPO_DE_SECCION:
        return GRUPO_DE_SECCION[seccion]
    if re.match(r"I \d - ", seccion):
        return "i_con"
    if re.fullmatch(r"I[0-3] \(Infantil\)", seccion):
        return "i_fic"
    # Sin sección propia, los CD caen en «Otros»: se reconocen por la signatura
    if re.search(r"\bCD\b", seccion) or re.match(r"(I )?CDR?\b", str(registro.get("signatura_real") or "")):
        return "cd"
    return "otros"


def _pct(parte, total):
    return round(100 * parte / total, 1) if total else None


def _fila(clave, referencia, valor, unidad="%"):
    """`referencia` es un número o un par (mínimo, máximo)."""
    minimo, maximo = referencia if isinstance(referencia, tuple) else (referencia, referencia)
    if valor is None:
        posicion = None
    else:
        posicion = "debajo" if valor < minimo else "encima" if maximo is not None and valor > maximo else "dentro"
    return {"clave": clave, "min": minimo, "max": maximo, "valor": valor, "unidad": unidad, "posicion": posicion}


def comparar(registros, habitantes):
    total = len(registros)
    cuenta = {}
    for r in registros:
        g = grupo(r)
        cuenta[g] = cuenta.get(g, 0) + 1
    audiovisual = cuenta.get("dvd", 0) + cuenta.get("cd", 0)
    libros = total - audiovisual

    # Macrosecciones del Ministerio, con la misma regla que el resto de Bildumargi
    macro = {"Adultos": 0, "Infantil/Juvenil": 0, "Audiovisuales": 0}
    infantil_diputacio = 0
    for r in registros:
        seccion = _seccion(r)
        macro["Audiovisuales" if grupo(r) in ("cd", "dvd") else clasificacion.clasificar_macro(seccion)] += 1
        # «Tot el fons que contingui signatura infantil»: la novela juvenil (JN) no
        if grupo(r) in ("i_con", "i_fic", "i_com") or seccion.startswith("I DVD"):
            infantil_diputacio += 1

    ficcion = sum(cuenta.get(g, 0) for g in _FICCION)
    # Poesía y teatro son ficción para la Diputació, aunque compartan grupo con 4 y 8
    poesia_teatro = sum(1 for r in registros if _seccion(r) in ("Poesía", "Teatro"))
    ficcion += poesia_teatro
    no_ficcion = sum(cuenta.get(g, 0) for g in _NO_FICCION) + cuenta.get("8", 0) - poesia_teatro

    # IFLA, ap. 4.6: «En los fondos más reducidos, el material para los niños y las
    # obras de ficción y de no ficción para adultos deben estar en porcentajes
    # similares». No da cifras: el tercio de cada uno es la lectura de esa frase.
    ninos = sum(cuenta.get(g, 0) for g in ("i_con", "i_fic", "i_com"))
    ficcion_adultos = sum(cuenta.get(g, 0) for g in ("novela", "comic", "jn")) + poesia_teatro
    no_ficcion_adultos = sum(cuenta.get(g, 0) for g in _NO_FICCION if g != "i_con") + cuenta.get("8", 0) - poesia_teatro
    base_ifla = ninos + ficcion_adultos + no_ficcion_adultos

    tramo = None
    if habitantes:
        tramo = next(t for t in TRAMOS_MINISTERIO if t[0] is None or habitantes <= t[0])
    bloques = [
        {"fuente": "ifla", "filas": [
            _fila("libros_hab", (IFLA_LIBROS_MIN, IFLA_LIBROS_MAX),
                  round(libros / habitantes, 2) if habitantes else None, ""),
            _fila("fondo_minimo", (IFLA_FONDO_MINIMO, None), libros, "n"),
            _fila("ninos", TERCIO, _pct(ninos, base_ifla)),
            _fila("ficcion_adultos", TERCIO, _pct(ficcion_adultos, base_ifla)),
            _fila("no_ficcion_adultos", TERCIO, _pct(no_ficcion_adultos, base_ifla)),
        ]},
        {"fuente": "ministerio", "tramo": tramo[0] if tramo else None, "filas": [
            *([_fila("docs_hab", tramo[1], round(total / habitantes, 2), ""),
               _fila("coleccion_inicial", (tramo[2], tramo[3]), total, "n")] if tramo else []),
            _fila("adultos", 65, _pct(macro["Adultos"], total)),
            _fila("infantil_juvenil", 20, _pct(macro["Infantil/Juvenil"], total)),
            _fila("audiovisuales", 15, _pct(macro["Audiovisuales"], total)),
        ]},
        {"fuente": "diputacio", "filas": [
            _fila("general", 75, _pct(total - infantil_diputacio, total)),
            _fila("infantil", 25, _pct(infantil_diputacio, total)),
            _fila("libros", 77, _pct(libros, total)),
            _fila("cd", 14, _pct(cuenta.get("cd", 0), total)),
            _fila("dvd", 9, _pct(cuenta.get("dvd", 0), total)),
            _fila("ficcion", 45, _pct(ficcion, ficcion + no_ficcion)),
            _fila("no_ficcion", 55, _pct(no_ficcion, ficcion + no_ficcion)),
        ]},
    ]
    secciones = []
    for clave, ministerio, diputacio in SECCIONES:
        n = cuenta.get(clave, 0)
        secciones.append({"clave": clave, "documentos": n,
                          "ministerio": _fila(clave, ministerio, _pct(n, total)),
                          "diputacio": _fila(clave, diputacio, _pct(n, libros))})
    secciones.append({"clave": "otros", "documentos": cuenta.get("otros", 0),
                      "ministerio": {"valor": _pct(cuenta.get("otros", 0), total)},
                      "diputacio": {"valor": _pct(cuenta.get("otros", 0), libros)}})
    return {"total": total, "libros": libros, "habitantes": habitantes, "bloques": bloques,
            "secciones": secciones, "hay_cd": bool(cuenta.get("cd"))}
