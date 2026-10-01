# -*- coding: utf-8 -*-
"""Clasificación de ejemplares por tejuelo (signatura).

La signatura es lo que manda en toda la aplicación. La CDU del catálogo (080)
solo interviene en un caso: colocar en la colección infantil los títulos de la
red que se recomiendan para compra (ver `bloques_libro`).

Hay un único motor de reglas —`clasificar_signatura`— y el resto de funciones
solo traducen su salida. Mantener dos motores fue lo que en su día hizo que
las enciclopedias se detectaran en el análisis y no en las recomendaciones.
"""

import re
from functools import lru_cache
from collections import Counter

# Contador de préstamos del listado «más prestados» ("33 - N MOL"). Exige
# espacios a ambos lados del guion para no romper signaturas CDU como "2-15 CUA".
_R_CONTADOR = re.compile(r"^\s*\d+ +- +")


def _limpiar_signatura(sig):
    return _R_CONTADOR.sub("", str(sig or ""))


def _norm_sig(s):
    return re.sub(r"\s+", " ", str(s or "").replace("\t", " ")).strip().upper()


# --- Infantil (prefijo I). El (?![A-Z]) evita capturar "ICO 3" o "ITA 9",
# pero admite "IC-PIL" / "IC.PIL" además de "IC PIL".
_R_I_DVD = re.compile(r"^I\s+DVD(?![A-Z])")
_R_I_COMIC = re.compile(r"^IC(?![A-Z])")
_R_I_TEA = re.compile(r"^IT(?![A-Z])")
_R_I_POE = re.compile(r"^IP(?![A-Z])")
_R_I_CDU_E = re.compile(r"^I\s+(\d)")        # "I 5 ANI"
_R_I_EDAD = re.compile(r"^I([0-3])(?!\d)")   # "I0".."I3"
_R_I_CDU_J = re.compile(r"^I([4-9])(?!\d)")  # "I5 ..."
_R_JN = re.compile(r"^JN(?![A-Z])")

# --- Adultos. El (?![A-Z]) impide que C/T/P capturen "CUA 12", "TOL 3" o
# "PER 7", pero acepta separadores no alfabéticos como "C-IBA" o "C.IBA".
_R_DVD = re.compile(r"^DVD(?![A-Z])")
_R_COMIC = re.compile(r"^C(?![A-Z])")
_R_TEA = re.compile(r"^T(?![A-Z])")
_R_POE = re.compile(r"^P(?![A-Z])")
_R_ENC = re.compile(r"^\(?031\)?(?![\d.])")
# Ficción es la N. Un 821 es literatura (8): «821 GRE» puede ser un
# diccionario de literatura, no una novela.
_R_FIC = re.compile(r"^N(?![A-Z])")
_R_PSICO = re.compile(r"^159\.9")               # psicología: sección propia, fuera de filosofía
_R_CDU = re.compile(r"^(\d)")

# Equivalencia Adultos -> Infantil, usada en las recomendaciones de compra
# cuando el 080 lleva 087.5 (obra para niños) pero la red la coloca en adultos.
_EQUIV_INFANTIL = {
    "Cómic": "I Cómic", "Teatro": "I Teatro", "Poesía": "I Poesía", "DVD": "I DVD",
    "Ficción": "I Otros", "Enciclopedias": "I Otros", "Otros": "I Otros",
    "CDU 0": "I CDU 0", "CDU 1": "I CDU 1", "CDU 2": "I CDU 2", "CDU 3": "I CDU 3",
    "CDU 4": "I CDU 4", "CDU 5": "I CDU 5", "CDU 6": "I CDU 6", "CDU 7": "I CDU 7",
    "CDU 8": "I CDU 8", "CDU 9": "I CDU 9", "CDU 159.9": "I CDU 1",
}


@lru_cache(maxsize=300_000)
def clasificar_signatura(sig):
    """Devuelve (grupo, categoria) a partir de UN tejuelo. Todo anclado al inicio.

    Se memoriza: en el catálogo de la red las mismas signaturas («N ARA pat»,
    «I1 ROD cue»…) se repiten miles de veces, y clasificarlas era más de la
    mitad del tiempo de las sugerencias de compra. Es una función pura (misma
    signatura, misma sección), así que recordar el resultado no cambia nada."""
    s = _norm_sig(_limpiar_signatura(sig))
    if not s:
        return None, None

    # Infantil primero: IC/IT/IP empiezan por I pero no llevan dígito detrás.
    if _R_I_DVD.match(s):
        return "Infantil", "I DVD"
    if _R_I_COMIC.match(s):
        return "Infantil", "I Cómic"
    if _R_I_TEA.match(s):
        return "Infantil", "I Teatro"
    if _R_I_POE.match(s):
        return "Infantil", "I Poesía"
    m = _R_I_CDU_E.match(s)
    if m:
        return "Infantil", f"I CDU {m.group(1)}"
    m = _R_I_EDAD.match(s)
    if m:
        return "Infantil", f"I{m.group(1)}"
    m = _R_I_CDU_J.match(s)
    if m:
        return "Infantil", f"I CDU {m.group(1)}"
    if _R_JN.match(s):
        return "Infantil", "JN"

    # Adultos
    if _R_DVD.match(s):
        return "Adultos", "DVD"
    if _R_COMIC.match(s):
        return "Adultos", "Cómic"
    if _R_TEA.match(s):
        return "Adultos", "Teatro"
    if _R_POE.match(s):
        return "Adultos", "Poesía"
    if _R_ENC.match(s):
        return "Adultos", "Enciclopedias"
    if _R_FIC.match(s):
        return "Adultos", "Ficción"
    if _R_PSICO.match(s):
        return "Adultos", "CDU 159.9"
    m = _R_CDU.match(s)
    if m and m.group(1) != "4":
        return "Adultos", f"CDU {m.group(1)}"

    return "Adultos", "Otros"


_CDU_NOMBRES = {
    "0": "0 - Generalidades", "1": "1 - Filosofía", "159.9": "159.9 - Psicología", "2": "2 - Religión",
    "3": "3 - Ciencias Sociales", "4": "4 - Lingüística", "5": "5 - Ciencias Puras",
    "6": "6 - Tecnología", "7": "7 - Arte / Deportes", "8": "8 - Literatura",
    "9": "9 - Historia / Geografía",
}
_CAT_ANALISIS = {
    "Enciclopedias": "Enciclopedias (031)", "I DVD": "I DVD (DVD Infantil)",
    "DVD": "DVD Audiovisual", "I Cómic": "IC (Comic Infantil)",
    "Cómic": "C (Comic Adultos)", "I Poesía": "IP (Infantil Poesía)",
    "I Teatro": "IT (Infantil Teatro)", "JN": "JN (Juvenil)",
    "Ficción": "Ficción / Narrativa", "Poesía": "Poesía", "Teatro": "Teatro",
    "Otros": "Otros", "I Otros": "Otros",
}


def categoria_analisis(signatura):
    """Etiqueta de categoría para el análisis de la colección."""
    if not signatura or not isinstance(signatura, str):
        return "Sin clasificar"
    grupo, categoria = clasificar_signatura(signatura)
    if not grupo:
        return "Sin clasificar"
    return etiqueta_categoria(categoria)


def etiqueta_categoria(categoria):
    """Nombre de sección para el análisis a partir de la categoría interna.

    Es el mismo nombre en toda la aplicación: Diagnóstico, Secciones y las
    sugerencias de compra hablan de «9 - Historia / Geografía», no de
    «CDU 9». Así se pueden cruzar la demanda propia y la oferta de la red."""
    if categoria == SIN_SIGNATURA:
        return "Sin signatura reconocible"
    if categoria in _CAT_ANALISIS:
        return _CAT_ANALISIS[categoria]
    if categoria.startswith("I CDU "):
        # La sección infantil de conocimientos se abre por su número de
        # tejuelo: «I 5 - Ciencias Puras», no un único bloque «CDU Infantil».
        return "I " + _CDU_NOMBRES.get(categoria[-1], categoria[-1])
    if re.fullmatch(r"I[0-3]", categoria):
        return f"{categoria} (Infantil)"
    if categoria.startswith("CDU "):
        return _CDU_NOMBRES.get(categoria[4:], categoria)
    return "Otros"


def clasificar_macro(cat: str) -> str:
    """Agrupa una categoría en Adultos / Infantil-Juvenil / Audiovisuales.

    El \\b de "CD" es imprescindible: buscándolo como subcadena, "CDU" casaba
    con audiovisuales y se llevaba media colección."""
    c = str(cat).upper()
    if "DVD" in c or re.search(r"\bCD\b", c):
        return "Audiovisuales"
    if es_categoria_infantil(cat):
        return "Infantil/Juvenil"
    return "Adultos"


def es_categoria_infantil(categoria) -> bool:
    cat_str = str(categoria).upper()
    # También los nombres que pongan las bibliotecas en su tabla de
    # signaturas, en cualquiera de los idiomas de la interfaz
    if re.search(r"INFANTIL|JUVENIL|XUVENIL|HAUR|GAZTE|CHILDREN", cat_str):
        return True
    if re.match(r"^(I[0-9]?|JN|IC|IP|IT)(\s|$)", cat_str):
        return True
    return False


# --- Colocación de los títulos de la red (recomendaciones de compra) -------
# Cada biblioteca de la red da su signatura y se vota. La CDU del catálogo
# solo cuenta para la colección infantil:
#   · un 080 con 087.5 (obra para niños) pasa a infantil un título que la red
#     coloca en adultos sin la I delante;
#   · sin tejuelo utilizable, un 080 con 087.5 coloca el título en su sección
#     infantil de conocimientos.
# En adultos la CDU no decide nada: sin tejuelo, el título queda en «Sin
# signatura reconocible».
SIN_SIGNATURA = "Sin signatura"

# Cada biblioteca de la red coloca a su manera: la categoría gana si la
# respalda al menos este porcentaje de los ejemplares.
_UMBRAL_TEJUELO = 0.33

_R_087 = re.compile(r"\(?087\.5\)?")


def _cdu_limpia(cdu):
    return re.sub(r"\s+", "", str(cdu or "")).upper()


def es_infantil_por_cdu(cdu):
    return "087.5" in _cdu_limpia(cdu)


def categoria_infantil_desde_cdu(cdu):
    """Sección infantil de un título sin tejuelo, a partir de un 080 con 087.5.

    «5(087.5)» → I CDU 5. La literatura infantil (82) va a «Otros»: su tramo
    de edad (I1, I2…) solo lo da el tejuelo, y el 080 no lo trae."""
    c = _cdu_limpia(cdu)
    if "087.5" not in c:
        return None, None
    resto = _R_087.sub("", c).lstrip(":+/-")
    m = re.match(r"\(?(\d)", resto)
    if not m or resto.startswith("82"):
        return "Infantil", "I Otros"
    return "Infantil", f"I CDU {m.group(1)}"


def _votar_tejuelos(todas_signaturas, umbral=_UMBRAL_TEJUELO):
    resueltas = [r for r in (clasificar_signatura(tok)
                             for tok in str(todas_signaturas or "").split("||")) if r[0]]
    if not resueltas:
        return []
    votos = Counter(resueltas)
    total = len(resueltas)
    admitidas = [gc for gc, n in votos.items() if n / total >= umbral]
    return sorted(admitidas, key=lambda gc: (-votos[gc], gc))


def bloques_libro(cdu, todas_signaturas):
    """Lista de (grupo, categoria) en los que aparece un título de la red.

    Puede devolver más de uno cuando varias colocaciones superan el umbral
    (media red lo tiene como novela y la otra media como cómic)."""
    admitidas = _votar_tejuelos(todas_signaturas)
    if not admitidas:
        grupo, categoria = categoria_infantil_desde_cdu(cdu)
        return [(grupo, categoria)] if grupo else [("Adultos", SIN_SIGNATURA)]

    infantil = es_infantil_por_cdu(cdu)
    bloques = []
    for grupo, categoria in admitidas:
        if infantil and grupo == "Adultos":
            grupo, categoria = "Infantil", _EQUIV_INFANTIL.get(categoria, "I Otros")
        if (grupo, categoria) not in bloques:
            bloques.append((grupo, categoria))
    return bloques


MENUS_ADULTOS = {
    "Enciclopedias": "Enciclopedias (031)", "Ficción": "Ficción adultos (N)",
    "Cómic": "Cómic adultos", "Teatro": "Teatro adultos", "Poesía": "Poesía adultos",
    "DVD": "DVD adultos",
    "CDU 0": "0 · Generalidades",
    "CDU 1": "1 · Filosofía", "CDU 159.9": "159.9 · Psicología", "CDU 2": "2 · Religión / Teología",
    "CDU 3": "3 · Ciencias sociales / Economía", "CDU 5": "5 · Ciencias puras / Naturales",
    "CDU 6": "6 · Ciencias aplicadas / Tecnología", "CDU 7": "7 · Bellas artes / Deportes",
    "CDU 8": "8 · Lingüística / Literatura", "CDU 9": "9 · Geografía / Historia",
    "Otros": "Otros",
    SIN_SIGNATURA: "Sin signatura reconocible",
}
MENUS_INFANTIL = {
    "I0": "I0 · Bebeteca", "I1": "I1 · Hasta 8 años", "I2": "I2 · 8 a 10 años",
    "I3": "I3 · 10 a 12 años", "JN": "JN · Juvenil",
    "I Cómic": "IC · Cómic infantil", "I Teatro": "IT · Teatro infantil",
    "I Poesía": "IP · Poesía infantil", "I DVD": "I DVD · Audiovisual infantil",
    "I CDU 0": "I 0 · Generalidades", "I CDU 1": "I 1 · Filosofía",
    "I CDU 2": "I 2 · Religión", "I CDU 3": "I 3 · Ciencias sociales",
    "I CDU 4": "I 4 · Lengua", "I CDU 5": "I 5 · Ciencias puras",
    "I CDU 6": "I 6 · Ciencias aplicadas", "I CDU 7": "I 7 · Arte / Deportes",
    "I CDU 8": "I 8 · Literatura", "I CDU 9": "I 9 · Geografía e historia",
    "I Otros": "Infantil · Otros",
}


# --- Tabla de signaturas editable (Configuración) ---------------------------
# Cada red y cada biblioteca pueden decir cómo empiezan sus signaturas y a qué
# sección van («VIA → Viajes», «EUS → Euskera»). Solo afecta al análisis del
# fondo propio (Diagnóstico, Secciones, informe); las sugerencias de compra
# siguen con las secciones estándar, que son las que comparte toda la red.
#
# Reglas: gana el prefijo más largo que encaje con el principio de la
# signatura. Un prefijo con letras no se corta a mitad de palabra («C» no
# casa con «CUA 12», sí con «C IBA» o «C-IBA»); si además termina en cifra y
# no lleva espacios («I1»), tampoco sigue otra cifra («I10»). Los prefijos
# solo numéricos siguen la jerarquía de la CDU: «8» incluye «821».
MAX_REGLAS = 300


def reglas_defecto():
    """La tabla por defecto: reproduce la clasificación de siempre."""
    filas = [("I DVD", "I DVD (DVD Infantil)"), ("IC", "IC (Comic Infantil)"),
             ("IT", "IT (Infantil Teatro)"), ("IP", "IP (Infantil Poesía)")]
    filas += [(f"I{d}", f"I{d} (Infantil)") for d in "0123"]
    filas += [(f"I {d}", "I " + _CDU_NOMBRES[d]) for d in "0123456789"]
    filas += [(f"I{d}", "I " + _CDU_NOMBRES[d]) for d in "456789"]
    filas += [("JN", "JN (Juvenil)"), ("DVD", "DVD Audiovisual"), ("C", "C (Comic Adultos)"),
              ("T", "Teatro"), ("P", "Poesía"), ("031", "Enciclopedias (031)"),
              ("(031)", "Enciclopedias (031)"), ("N", "Ficción / Narrativa"),
              ("159.9", _CDU_NOMBRES["159.9"])]
    filas += [(d, _CDU_NOMBRES[d]) for d in "012356789"]
    return [{"prefijo": p, "seccion": s} for p, s in filas]


def normalizar_reglas(entrada):
    """Tabla válida a partir de lo recibido, o None si no hay tabla propia.
    Prefijos en mayúsculas y con espacios normalizados; el último repetido
    gana; filas vacías fuera."""
    if entrada is None:
        return None
    if not isinstance(entrada, list):
        raise ValueError("La tabla de signaturas debe ser una lista de filas.")
    vistas = {}
    for fila in entrada[:MAX_REGLAS]:
        if not isinstance(fila, dict):
            continue
        prefijo = _norm_sig(fila.get("prefijo"))[:20]
        seccion = " ".join(str(fila.get("seccion") or "").split())[:60]
        if prefijo and seccion:
            vistas[prefijo] = seccion
    return [{"prefijo": p, "seccion": s} for p, s in vistas.items()]


def _encaja(prefijo, firma):
    if not firma.startswith(prefijo):
        return False
    resto = firma[len(prefijo):]
    if not resto:
        return True
    if re.search(r"[A-Z]", prefijo):
        if resto[0].isalpha():
            return False
        if prefijo[-1].isdigit() and " " not in prefijo and resto[0].isdigit():
            return False
    return True


class Clasificador:
    """Clasifica signaturas con una tabla de reglas (prefijo -> sección)."""

    def __init__(self, reglas):
        self.reglas = sorted(((r["prefijo"], r["seccion"]) for r in reglas), key=lambda x: -len(x[0]))
        self._memo = {}

    def categoria(self, signatura):
        if not signatura or not isinstance(signatura, str):
            return "Sin clasificar"
        firma = _norm_sig(_limpiar_signatura(signatura))
        if not firma:
            return "Sin clasificar"
        if firma not in self._memo:
            self._memo[firma] = next((sec for pre, sec in self.reglas if _encaja(pre, firma)), "Otros")
        return self._memo[firma]


def aplicar_reglas(registros, reglas):
    """Pone a cada ejemplar la sección de la tabla (o la estándar si no hay
    tabla propia). La estándar queda en «categoria_estandar» para lo que se
    cruza con la red (sugerencias de compra)."""
    clasificador = Clasificador(reglas) if reglas else None
    for r in registros:
        if "categoria_estandar" not in r:
            r["categoria_estandar"] = r.get("categoria")
        r["categoria"] = (clasificador.categoria(r.get("signatura_real")) if clasificador
                          else r["categoria_estandar"])
        r["macro_seccion"] = clasificar_macro(r["categoria"])
        r["es_infantil"] = es_categoria_infantil(r["categoria"])
    return registros
