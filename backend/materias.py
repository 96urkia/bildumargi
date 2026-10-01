# -*- coding: utf-8 -*-
"""De las materias comerciales a la signatura de la biblioteca.

Las fichas de DILVE traen la materia en THEMA (casi siempre), en IBIC (el
sistema anterior, que todavía acompaña) y, a veces, en CDU. Aquí se convierten
a las secciones con las que trabaja Bildumargi, que salen de la signatura.

La tabla es **obra propia**: usa los códigos como identificadores, igual que se
usa un ISBN, sin reproducir el esquema ni las descripciones de sus autores. Se
puede sustituir por red en `datos/materias_secciones.json`.

Los tramos de edad no se fijan a ojo: se **calibran** comparando la edad que
declara la editorial con el tramo en el que la biblioteca coloca esos mismos
títulos (ver `calibrar_tramos`). En la prueba con una biblioteca real, el
acierto pasó del 30 % al 79 %.
"""

import json
import os
import re

# Prefijo de materia -> sección. Se prueba del prefijo más largo al más corto.
# THEMA (esquema ONIX 93) e IBIC (esquema 12) van en tablas SEPARADAS: el
# mismo prefijo no significa lo mismo en los dos (FX es novela gráfica en IBIC
# y «temas narrativos» en THEMA; B, E y H no existen en THEMA).
# Revisada con THEMA v1.6 (EDItEUR). Los casos en que las bibliotecas no
# coinciden van marcados «criterio» y se pueden cambiar por red en
# datos/materias_secciones.json.
PSICOLOGIA = "159.9"

TABLA_THEMA = {
    "A": "7",                       # Artes (72 arquitectura, 78 música, 79 espectáculos)
    "C": "8",                       # Lengua y lingüística (81)
    "D": "8", "DB": "N",            # DB: clásicos antiguos y medievales -> narrativa (criterio)
    "DC": "P", "DD": "T",           # Poesía, teatro
    "DN": "9",                      # Biografía y no ficción (929)
    "DNL": "8",                     # Ensayo literario (82-4)
    "DS": "8",                      # Historia y crítica literaria (82.09)
    "F": "N",                       # Ficción (FX* son temas narrativos, no cómic)
    "G": "0",                       # Referencia, información, interdisciplinar
    "J": "3",                       # Sociedad y ciencias sociales
    "JM": PSICOLOGIA,               # Psicología
    "JMH": "3",                     # Psicología social (316.6) (criterio)
    "K": "3", "KFC": "6", "KJ": "6",  # Economía (33); contabilidad (657) y empresa (65)
    "L": "3",                       # Derecho (34)
    "M": "6", "MKL": "6",           # Medicina (61); psiquiatría (616.89)
    "MKM": PSICOLOGIA,              # Psicología clínica y psicoterapia (criterio: 615.851)
    "N": "9",                       # Historia y arqueología
    "P": "5",                       # Matemáticas y ciencias
    "Q": "1", "QD": "1",            # Filosofía (incluida QDTM, filosofía de la mente)
    "QR": "2",                      # Religión
    "R": "5", "RG": "9",            # Tierra y medio ambiente (55, 502); geografía (91)
    "RP": "7",                      # Urbanismo (711) (criterio)
    "S": "7",                       # Deporte (796)
    "T": "6",                       # Tecnología, ingeniería, agricultura
    "U": "0",                       # Informática (004)
    "V": "6",                       # Salud y vida personal
    "VFJ": PSICOLOGIA, "VFV": PSICOLOGIA,   # Problemas personales; relaciones y familia
    "VFVC": "6",                    # Sexualidad: consejos (613.88)
    "VS": PSICOLOGIA,               # Autoayuda y desarrollo personal
    "VSB": "3", "VSC": "3", "VSD": "3", "VSK": "3",   # Finanzas, carrera (criterio), derecho, educación
    "VSN": "5",                     # Aritmética para adultos
    "VX": PSICOLOGIA,               # Mente, cuerpo, espíritu: todo con la psicología (criterio de la red)
    "VXH": "6",                     # Terapias complementarias (615.8)
    "W": "7",                       # Ocio y aficiones
    "WB": "6",                      # Cocina (641)
    "WG": "6",                      # Transporte, interés general (629) (criterio)
    "WH": "8",                      # Humor (82-7) (criterio)
    "WJ": "6", "WK": "6", "WM": "6",  # Belleza y moda (646), hogar (64), jardinería (635)
    "WN": "5", "WNG": "6",          # Naturaleza (57-59); mascotas (636)
    "WQ": "9", "WT": "9",           # Historia local y familiar; viajes
    "WZ": "0",                      # Artículos varios
    "X": "C",                       # Cómic, novela gráfica, manga
    "XR": "7",                      # Estudios sobre el cómic (741.5) (criterio)
}

TABLA_IBIC = {                      # Solo registros antiguos: IBIC está obsoleto desde 2020
    "A": "7", "B": "9", "C": "8", "D": "8", "DC": "P", "DD": "T", "DS": "8",
    "E": "8", "F": "N", "FX": "C", "G": "0",
    "H": "9", "HB": "9", "HD": "9", "HP": "1", "HR": "2",
    "J": "3", "JM": PSICOLOGIA, "K": "3", "KJ": "6", "L": "3", "M": "6",
    "P": "5", "R": "5", "RG": "9", "T": "6", "U": "0",
    "V": "6", "VS": PSICOLOGIA, "VX": PSICOLOGIA, "VXH": "6",
    "W": "7", "WB": "6", "WJ": "6", "WK": "6", "WM": "6", "WN": "5",
    "WQ": "9", "WS": "7", "WT": "9",
}
TABLA = TABLA_THEMA                 # nombre anterior, por compatibilidad

# Conocimientos infantiles: «I» + cifra de la CDU
TABLA_INFANTIL = {
    "YN": "0", "YNA": "7", "YNB": "9", "YNC": "7", "YND": "7",
    "YNF": "7",                     # Televisión y cine (791)
    "YNG": "0", "YNH": "9",
    "YNJ": "3",                     # Guerra y fuerzas armadas (355) (criterio)
    "YNK": "3",                     # Trabajo, política y sociedad
    "YNL": "8", "YNM": "9", "YNN": "5",
    "YNNH": "6",                    # Mascotas (636)
    "YNP": "6", "YNR": "2", "YNT": "5",
    "YNTC": "0",                    # Informática
    "YNTT": None,                   # Viajes en el tiempo: tema de ficción, no conocimientos
    "YNU": "8",                     # Humor (82-7) (criterio)
    "YNV": "7", "YNW": "7",
    "YNX": "1",                     # Misterios y paranormal (133) (criterio)
    "YR": "0",
}

# Calificadores de edad de interés: código -> edad mínima declarada. Se busca
# primero a cuatro caracteres (5ABH, 5ABK) y luego a tres. 5AR, 5AX y 5AZ
# (lectores reacios, adultos que empiezan a leer, dificultades de
# aprendizaje) no indican edad y por eso no están.
EDAD_CALIFICADOR = {
    "5AB": 0, "5ABH": 1, "5ABK": 2,
    "5AC": 3, "5AD": 4, "5AF": 5, "5AG": 6, "5AH": 7, "5AJ": 8,
    "5AK": 9, "5AL": 10, "5AM": 11, "5AN": 12, "5AP": 13, "5AQ": 14,
    "5AS": 15, "5AT": 16, "5AU": 17,
}

# Tramos de partida (edad mínima -> sección) mientras no haya calibración
TRAMOS_DEFECTO = ((0, "I0"), (5, "I1"), (8, "I2"), (10, "I3"), (12, "JN"))
TRAMOS_VALIDOS = ("I0", "I1", "I2", "I3", "JN")

SIN_EDAD = "Infantil/juvenil sin edad"
SECCIONES_FICCION = {"N", "C", "P", "T", "IC", "IP", "JN", *TRAMOS_VALIDOS}
SIN_CLASIFICAR = "Sin clasificar"
LIBRO_TEXTO = "Libro de texto"


def cargar_tabla(ruta=None):
    """Permite a cada red ajustar las tablas sin tocar el código:
    {"secciones": {...THEMA...}, "ibic": {...}, "infantil": {...}}."""
    if ruta and os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                propia = json.load(f)
            return ({**TABLA_THEMA, **(propia.get("secciones") or {})},
                    {**TABLA_INFANTIL, **(propia.get("infantil") or {})},
                    {**TABLA_IBIC, **(propia.get("ibic") or {})})
        except (OSError, ValueError):
            pass
    return TABLA_THEMA, TABLA_INFANTIL, TABLA_IBIC


def _por_prefijo(codigo, tabla):
    for largo in range(len(codigo), 0, -1):
        if codigo[:largo] in tabla:
            return tabla[codigo[:largo]]
    return None


def _principal(materias, esquema):
    codigos = [m for m in materias if m.get("esquema") == esquema and m.get("codigo")]
    principal = next((m["codigo"] for m in codigos if m.get("principal")), None)
    return principal or (codigos[0]["codigo"] if codigos else None)


def edad_declarada(ficha):
    """Edad mínima que declara la editorial, y de dónde sale."""
    if ficha.get("edad_min") is not None:
        return ficha["edad_min"], "edad recomendada"
    for m in ficha.get("materias") or []:
        codigo = (m.get("codigo") or "").strip().upper()
        if m.get("esquema") in ("98", "17"):
            for largo in (4, 3):
                if codigo[:largo] in EDAD_CALIFICADOR:
                    return EDAD_CALIFICADOR[codigo[:largo]], "calificador de edad"
    return None, None


def tramo_por_edad(edad, calibracion=None):
    """Sección infantil para una edad declarada. Con calibración se usa el
    tramo donde la biblioteca coloca los libros de esa edad; sin ella, los
    tramos de partida."""
    if calibracion:
        if str(edad) in calibracion:
            return calibracion[str(edad)]
        cercana = min(calibracion, key=lambda e: (abs(int(e) - edad), int(e)))
        return calibracion[cercana]
    seccion = None
    for minima, s in TRAMOS_DEFECTO:
        if edad >= minima:
            seccion = s
    return seccion


def clasificar(ficha, calibracion=None, tablas=None):
    """Devuelve (sección, motivo) para una ficha de DILVE ya interpretada."""
    tablas = tablas or (TABLA_THEMA, TABLA_INFANTIL, TABLA_IBIC)
    tabla, tabla_infantil = tablas[0], tablas[1]
    tabla_ibic = tablas[2] if len(tablas) > 2 else TABLA_IBIC
    materias = ficha.get("materias") or []
    thema, ibic = _principal(materias, "93"), _principal(materias, "12")
    todos = [m["codigo"] for m in materias if m.get("esquema") in ("93", "12") and m.get("codigo")]
    cdu = next((m["codigo"].replace(" ", "") for m in materias
                if m.get("esquema") in ("09", "51") and m.get("codigo")), None)
    es_ficcion = (thema or ibic or "").startswith(("F", "YF", "X", "DB", "DC", "DD"))

    # 1. Libros de texto. THEMA manda sobre IBIC, y el esquema de materias
    # escolares (42) también lo llevan las novelas de los planes lectores.
    if (thema or "").startswith("YP") and not (thema or "").startswith("YPCK9"):
        return LIBRO_TEXTO, thema
    if not thema and (ibic or "").startswith("YQ"):
        return LIBRO_TEXTO, ibic
    if any(m.get("esquema") == "42" for m in materias) and not es_ficcion:
        return LIBRO_TEXTO, "materia escolar"

    edad, fuente = edad_declarada(ficha)
    infantil = (any(c.startswith("Y") for c in todos) or (cdu or "").startswith("087.5")
                or (edad is not None and edad < 12 and not (thema or "").startswith("F")))

    # 2. Infantil y juvenil
    if infantil:
        if any(c.startswith("X") for c in todos):
            return "IC", "cómic infantil"
        if (thema or ibic or "").startswith("YDP"):     # YDC son antologías de ficción
            return "IP", "poesía infantil"
        conocimientos = next((c for c in todos if c.startswith(("YN", "YR"))), None)
        if conocimientos and not (thema or "").startswith("YF"):
            cifra = _por_prefijo(conocimientos, tabla_infantil)
            if cifra:
                return "I " + cifra, "conocimientos " + conocimientos
        if (ficha.get("forma") or "").upper() == "BH":       # libro de cartón
            return "I0", "libro de cartón"
        if edad is not None:
            return tramo_por_edad(edad, calibracion), f"{fuente}: desde {edad} años"
        if (thema or "").startswith("YBC"):
            return "I0", "álbum ilustrado"
        return SIN_EDAD, thema or ibic or cdu or "—"

    # 3. CDU, salvo literatura sin género marcado y publicaciones especiales
    if cdu and not cdu.startswith("087") and not re.match(r"8\d*[\d.]*(-[4-9])?$", cdu):
        if cdu.startswith("159.9"):
            return PSICOLOGIA, "CDU " + cdu
        if re.match(r"82[\d.]*-1", cdu):
            return "P", "CDU " + cdu
        if re.match(r"82[\d.]*-2", cdu):
            return "T", "CDU " + cdu
        if re.match(r"82[\d.]*-3", cdu):
            return "N", "CDU " + cdu
        if cdu[:1].isdigit():
            return cdu[0], "CDU " + cdu

    # 4. THEMA y 5. IBIC
    for codigo, nombre, tabla_esquema in ((thema, "THEMA", tabla), (ibic, "IBIC", tabla_ibic)):
        if codigo:
            seccion = _por_prefijo(codigo, tabla_esquema)
            if seccion:
                return seccion, f"{nombre} {codigo}"
    return SIN_CLASIFICAR, "—"


def otras_secciones(ficha, principal=None, calibracion=None, tablas=None):
    """Secciones en las que también encaja el libro por sus otras materias THEMA.

    Una ficha suele llevar varias: la novela gráfica de «Orgullo y prejuicio»
    trae novela romántica (principal) y novela gráfica. `clasificar` decide
    con la principal; aquí se repite la clasificación con cada una de las
    demás como si fuera la principal, sin la CDU (que taparía a todas), y se
    devuelven las secciones distintas que salen: [(sección, motivo), ...].
    Libro de texto, «sin clasificar» e «infantil sin edad» no suman nada."""
    materias = ficha.get("materias") or []
    principal = principal or clasificar(ficha, calibracion, tablas)[0]
    if principal == LIBRO_TEXTO:
        return []
    codigos = [m["codigo"] for m in materias if m.get("esquema") == "93" and m.get("codigo")]
    actual = _principal(materias, "93")
    # Una novela con materias de no ficción (el lugar, la época, los animales
    # que salen) no se lleva también a historia o a ciencias: de la ficción
    # solo se admiten otras secciones de ficción (novela gráfica, poesía…).
    ficcion = (actual or "").startswith(("F", "YF"))
    resto = [m for m in materias if m.get("esquema") not in ("93", "09", "51")]
    vistas, salida = {principal}, []
    for codigo in dict.fromkeys(codigos):
        if codigo == actual:
            continue
        prueba = dict(ficha, materias=resto + [
            {"esquema": "93", "codigo": c, "principal": 1 if c == codigo else 0} for c in codigos])
        seccion, motivo = clasificar(prueba, calibracion, tablas)
        if seccion in vistas or seccion in (LIBRO_TEXTO, SIN_CLASIFICAR, SIN_EDAD):
            continue
        if ficcion and seccion not in SECCIONES_FICCION:
            continue
        vistas.add(seccion)
        salida.append((seccion, motivo))
    return salida


def seccion_de_signatura(categoria):
    """Sección de Bildumargi (de la signatura) en la misma notación que la
    tabla de arriba, para poder compararlas."""
    texto = str(categoria or "")
    if texto.startswith("Ficción"):
        return "N"
    for prefijo, codigo in (("JN", "JN"), ("IC", "IC"), ("IP", "IP"), ("IT", "IT"), ("C (", "C")):
        if texto.startswith(prefijo):
            return codigo
    if texto == "Teatro":
        return "T"
    if texto == "Poesía":
        return "P"
    for patron, plantilla in ((r"^(I[0-3]) ", "{}"), (r"^I (\d) ", "I {}"), (r"^(159\.9) ", "{}"), (r"^(\d) ", "{}")):
        m = re.match(patron, texto)
        if m:
            return plantilla.format(m.group(1))
    return texto


def calibrar_tramos(pares):
    """Aprende la equivalencia «edad declarada -> tramo de esta biblioteca».

    `pares`: lista de (edad declarada, sección real del ejemplar). Para cada
    edad se toma el tramo más frecuente. Con pocos datos no se calibra: se
    exige un mínimo de ejemplos para no aprender de una casualidad."""
    from collections import Counter, defaultdict
    por_edad = defaultdict(list)
    for edad, seccion in pares:
        if edad is not None and seccion in TRAMOS_VALIDOS:
            por_edad[int(edad)].append(seccion)
    if sum(len(v) for v in por_edad.values()) < 10:
        return {}
    return {str(edad): Counter(v).most_common(1)[0][0] for edad, v in sorted(por_edad.items())}
