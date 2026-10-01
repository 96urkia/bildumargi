# -*- coding: utf-8 -*-
"""Lectura de las exportaciones de AbsysNet: listado topográfico, catálogo,
no prestados y más prestados.

Cada fichero se identifica por su CONTENIDO, no por el nombre ni por el hueco
en el que lo suba el usuario, para poder recolocarlo en vez de fallar con un
error críptico.
"""

import re
from collections import Counter

from . import clasificacion, utils

TIPOS_FICHERO = {
    "topo": "Listado topográfico",
    "catalogo": "Catálogo",
    "nunca": "No prestados",
    "mas2": "Más prestados",
}

_RE_AUTOR_PERSONA = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ.\-\s]*,\s+\S")
_RE_NOTA_ISBN = re.compile(r"^(D\.?L\.?|ISBN)", re.IGNORECASE)

# Detecta, dentro de una línea del topográfico, la secuencia
# "Suc. (nº corto) + Loc. (letras) + Cód. Barras (7+ dígitos)". Se ancla por
# CONTENIDO y no por posición fija de carácter: el ancho real de la columna
# se desplaza uno o dos espacios según la longitud de la signatura, y cortar
# por posición puede truncar el código de barras (leer "786898" en vez de
# "3786898"), un fallo silencioso que corrompe todo el cruce posterior.
_RE_SUC_LOC_CODBAR = re.compile(r"(\d{1,3})\s+([A-Za-z]{1,4})\s+(\d{6,})")


def identificar_fichero(data: bytes) -> str:
    """Reconoce qué exportación de AbsysNet es un fichero, mirando su cabecera."""
    if not data or not str(data).strip():
        return "vacio"
    cabecera = utils.sin_acentos(utils.decodificar_bytes(data[:8000])).upper()

    if "CATALOGO TOPOGRAFICO" in cabecera:
        return "catalogo"
    if "MAS PRESTADOS" in cabecera:
        return "mas2"
    if "NO PRESTADOS" in cabecera:
        return "nunca"
    if "LISTADO TOPOGRAFICO DE EJEMPLARES" in cabecera:
        return "topo"

    # Respaldo: si no hay cabecera (exportación recortada), se deduce por estructura.
    if "COD. BAR." in cabecera and "SIGNATURA" in cabecera:
        return "topo"
    if re.search(r"^[ \t]*\d{7,}[ \t]*$", cabecera, re.MULTILINE) and "ISBN" in cabecera:
        return "catalogo"
    return "desconocido"


def detectar_sucursal(*textos):
    """Código de sucursal (columna 'Suc.') más repetido entre las líneas de
    datos de los listados recibidos, o None. Usar el más frecuente, y no el
    primero, hace la detección resistente a líneas sueltas con formato raro."""
    contador = Counter()
    for texto in textos:
        if not texto:
            continue
        for line in texto.splitlines():
            m = _RE_SUC_LOC_CODBAR.search(line)
            if m:
                contador[int(m.group(1))] += 1
    if not contador:
        return None
    return contador.most_common(1)[0][0]


def validar_ficheros(subidos: dict):
    """Recibe {hueco: (nombre, bytes)} y devuelve (asignados, avisos, errores).

    El hueco 'catalogo' admite también una LISTA de fragmentos: las
    bibliotecas con fondos grandes no pueden exportar el catálogo completo de
    AbsysNet en un solo fichero. Los fragmentos se concatenan y se tratan como
    un único texto; el orden da igual, porque cada ficha es un bloque
    autocontenido que arranca en su propio número de registro."""
    subidos = dict(subidos)
    catalogo_valor = subidos.get("catalogo")
    if isinstance(catalogo_valor, list):
        fragmentos = [par for par in catalogo_valor if par]
        if fragmentos:
            texto = "\n".join(utils.decodificar_bytes(data) for _, data in fragmentos)
            nombres = ", ".join(nombre for nombre, _ in fragmentos)
            subidos["catalogo"] = (nombres, texto.encode("utf-8"))
        else:
            subidos["catalogo"] = None

    asignados, avisos, errores = {}, [], []
    for hueco, par in subidos.items():
        if not par:
            continue
        nombre, data = par
        tipo = identificar_fichero(data)
        if tipo == "vacio":
            errores.append(f"El fichero «{nombre}» está vacío.")
            continue
        if tipo == "desconocido":
            errores.append(
                f"No se reconoce el fichero «{nombre}». Debe ser una exportación "
                f"de AbsysNet en .txt, sin abrir ni guardar con Excel.")
            continue
        if tipo in asignados:
            errores.append(
                f"Hay dos ficheros del tipo «{TIPOS_FICHERO[tipo]}»: revisa «{nombre}».")
            continue
        if tipo != hueco:
            avisos.append(
                f"«{nombre}» se ha colocado como {TIPOS_FICHERO[tipo]}, "
                f"no como {TIPOS_FICHERO[hueco]}.")
        asignados[tipo] = data

    if "topo" not in asignados:
        errores.append("Falta el listado topográfico, que es obligatorio.")
    if "catalogo" not in asignados:
        avisos.append("Sin el catálogo, el análisis va en modo reducido: "
                      "no habrá año de edición, autor ni materias.")
    return asignados, avisos, errores


def _parsear_linea_topo(line: str):
    """Divide una línea del listado topográfico.

    Signatura y Sig. supl. se recortan por posición fija (evita romper
    signaturas con espacios internos). Suc., Loc. y Cód. Barras se localizan
    por contenido, y el título es lo que queda después."""
    def col(a, b=None):
        return (line[a:b] if b is not None else line[a:]).strip()

    signatura = col(0, 27)
    sig_supl = col(27, 40)

    cod_bar, loc, titulo = "", "", ""
    m = _RE_SUC_LOC_CODBAR.search(line)
    if m:
        loc = m.group(2).upper()
        cod_bar = m.group(3)
        resto = line[m.end():].strip()
        m_nreg = re.match(r"^\d{1,10}\s+(.+)$", resto)
        titulo = m_nreg.group(1) if m_nreg else resto

    if not cod_bar:  # respaldo por posición fija
        cod_bar = col(53, 64)
        titulo = col(74)

    return {"signatura": signatura, "sig_supl": sig_supl, "cod_bar": cod_bar,
            "titulo": titulo, "loc": loc}


def parsear_fichas_catalogo(cat_text: str) -> dict:
    """Ficha ISBD simplificada (autor, título, ISBN, materias) por registro,
    a partir del fichero de Catálogo (Formato 1 / Cuerpo 1 / Orden 8)."""
    cat_limpio = re.sub(
        r"^\s*(Pág\.\s*\d+|Catálogo Topográfico.*|\d{2}/\d{2}/\d{4})\s*$",
        "", cat_text, flags=re.MULTILINE)
    matches = list(re.finditer(r"^[ \t]*(\d{7,})[ \t]*$", cat_limpio, re.MULTILINE))
    fichas = {}
    for i, m in enumerate(matches):
        rid = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i < len(matches) - 1 else len(cat_limpio)
        bloque = cat_limpio[start:end]

        cierre = re.search(r"^\s*\d{2}\s+[A-ZÁÉÍÓÚÑÜ]{2}\b.*$", bloque, re.MULTILINE)
        if cierre:
            bloque = bloque[: cierre.start()]

        lineas = [ln.strip() for ln in bloque.split("\n") if ln.strip()]
        if not lineas:
            continue

        autor = None
        resto = lineas
        if _RE_AUTOR_PERSONA.match(lineas[0]) and "/" not in lineas[0]:
            autor = lineas[0]
            resto = lineas[1:]
        if not resto:
            continue

        idx_isbn = next((i2 for i2, ln in enumerate(resto) if _RE_NOTA_ISBN.match(ln)), None)
        if idx_isbn is not None:
            titulo_lineas = resto[:idx_isbn]
            linea_isbn = resto[idx_isbn]
            materias_lineas = resto[idx_isbn + 1:]
        elif resto[-1].lstrip().startswith("1."):
            titulo_lineas, linea_isbn, materias_lineas = resto[:-1], "", [resto[-1]]
        else:
            titulo_lineas, linea_isbn, materias_lineas = resto, "", []

        titulo_par = re.sub(r"\s+", " ", " ".join(titulo_lineas)).strip()
        partes = re.split(r"\s+/\s*", titulo_par, maxsplit=1)
        titulo = partes[0].strip(" .") or None
        resto_isbd = partes[1].strip() if len(partes) > 1 else None

        isbn_m = re.search(r"ISBN\s*([\dXx\-]{8,})", linea_isbn)
        isbn = isbn_m.group(1) if isbn_m else None

        materias_txt = re.sub(r"\s+", " ", " ".join(materias_lineas)).strip()
        corte = re.search(r"\b[IVXLC]+\.\s", materias_txt)
        if corte:
            materias_txt = materias_txt[: corte.start()]
        materias = [frag.strip(" .-") for frag in re.split(r"\d+\.\s*", materias_txt)
                    if frag.strip(" .-")]

        fichas[rid] = {"autor": autor, "titulo": titulo, "resto_isbd": resto_isbd,
                       "isbn": isbn, "materias": materias}
    return fichas


def prestamos_del_listado(texto):
    """Número de préstamos por código de barras en el listado «Más prestados».

    AbsysNet no siempre incluye esa columna, y cuando la incluye su posición
    cambia de una red a otra. Se busca la columna numérica que aparece en casi
    todas las líneas y cuyos valores no crecen (el listado viene ordenado de
    más a menos prestado); se prueba tanto por el inicio como por el final del
    número, porque suelen ir alineados a la derecha. Si no se encuentra,
    devuelve un diccionario vacío y el resto de la aplicación sigue igual."""
    lineas = [l for l in texto.split("\n") if re.search(r"\b\d{7,}\b", l)]
    if len(lineas) < 5:
        return {}
    numeros = lambda l: [(m.start(), m.end(), int(m.group()))
                         for m in re.finditer(r"(?<![\d.,/])\d{1,5}(?![\d.,/])", l)]
    columnas = {}
    for i, linea in enumerate(lineas):
        for ini, fin, valor in numeros(linea):
            columnas.setdefault(("inicio", ini), []).append(valor)
            columnas.setdefault(("final", fin), []).append(valor)
    mejor, mejor_n = None, 0
    for clave, valores in columnas.items():
        if len(valores) < 0.6 * len(lineas) or len(set(valores)) < 3 or max(valores) < 2:
            continue
        no_crece = sum(1 for a, b in zip(valores, valores[1:]) if b <= a) / max(1, len(valores) - 1)
        if no_crece > 0.9 and len(valores) > mejor_n:
            mejor, mejor_n = clave, len(valores)
    if mejor is None:
        return {}
    salida = {}
    for linea in lineas:
        codbar = int(re.search(r"\b(\d{7,})\b", linea).group(1))
        candidatos = [v for ini, fin, v in numeros(linea) if (ini if mejor[0] == "inicio" else fin) == mejor[1]]
        if candidatos:
            salida[codbar] = max(candidatos[0], salida.get(codbar, 0))
    return salida


def procesar_datos(topo_bytes, nunca_bytes, mas2_bytes, catalogo_bytes, anio_actual=2026):
    """Devuelve (registros, huerfanos, fichas).

    `registros` es una lista de diccionarios, uno por ejemplar del
    topográfico. Si algo falla devuelve (None, mensaje_de_error, {})."""
    if not topo_bytes:
        return None, "Falta el listado topográfico.", {}

    topo_text = utils.decodificar_bytes(topo_bytes)
    vistos = set()
    registros = []
    for line in topo_text.split("\n"):
        linea = line.rstrip("\n")
        cabecera = linea.strip()
        if not cabecera or re.search(r"^(\d{2}/\d{2}/\d{4}|LISTADO|Signatura|-----)", cabecera):
            continue
        campos = _parsear_linea_topo(linea)
        cod_bar = campos["cod_bar"]
        if not re.fullmatch(r"\d{6,}", cod_bar):
            continue
        record_id = int(cod_bar)
        if record_id in vistos:
            continue
        vistos.add(record_id)
        registros.append({
            "record_id": record_id,
            "signatura_real": campos["signatura"],
            "sig_supl": campos["sig_supl"],
            "titulo": campos["titulo"].rstrip(" /") or "(título no detectado)",
            "loc": campos["loc"] or "Sin dato",
        })

    if not registros:
        return None, ("No se ha podido leer ninguna línea del topográfico. "
                      "Comprueba que el fichero es el .txt exportado por AbsysNet."), {}

    modo_reducido = not catalogo_bytes
    fichas = {}
    total_topo = len(registros)

    if not modo_reducido:
        cat_text = utils.decodificar_bytes(catalogo_bytes)
        cat_sin_fechas = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", "", cat_text)
        anios = {}
        matches = list(re.finditer(r"^[ \t]*(\d{7,})[ \t]*$", cat_sin_fechas, re.MULTILINE))
        for i, m in enumerate(matches):
            rid = int(m.group(1))
            start = m.start()
            end = matches[i + 1].start() if i < len(matches) - 1 else len(cat_sin_fechas)
            bloque = cat_sin_fechas[start:end]
            # Fechas biográficas de autores y personas-materia: sin quitarlas,
            # un autor fallecido después de la publicación arrastra el año.
            bloque = re.sub(r"\([12]\d{3}\s*-\s*[12]\d{3}\)", "", bloque)
            bloque = re.sub(r"\([12]\d{3}\s*-\s*\)", "", bloque)
            # El ISBN puede traer 4 cifras que parecen un año ("84-241-2025-6").
            bloque = re.sub(r"ISBN\s*[\dXx\-]{8,}", "", bloque, flags=re.IGNORECASE)
            # Depósito legal: solo el número tras el guion es el año real.
            bloque = re.sub(r"(D\.?L\.?\s*[A-ZÁÉÍÓÚÑÜ]{0,3}\s*)\d+-(\d{4})", r"\1\2", bloque)
            candidatos = [int(y) for y in re.findall(r"\b(18\d{2}|19\d{2}|20\d{2})\b", bloque)
                          if 1800 <= int(y) <= anio_actual]
            if candidatos:
                anios[rid] = max(candidatos)

        if not anios:
            return None, ("El fichero de catálogo no contiene fichas legibles. "
                          "Debe exportarse con Formato 1 / Cuerpo 1 / Orden 8."), {}

        registros = [r for r in registros if r["record_id"] in anios]
        if not registros:
            return None, ("El topográfico y el catálogo no comparten ningún registro: "
                          "parecen de bibliotecas o fechas distintas."), {}
        for r in registros:
            r["year"] = anios[r["record_id"]]

        fichas_todas = parsear_fichas_catalogo(cat_text)
        validos = {r["record_id"] for r in registros}
        fichas = {rid: f for rid, f in fichas_todas.items() if rid in validos}
    else:
        for r in registros:
            r["year"] = None

    nunca_ids = set()
    if nunca_bytes:
        nunca_ids = {int(x) for x in re.findall(r"\b\d{7,}\b", utils.decodificar_bytes(nunca_bytes))}
    mas2_ids, veces = set(), {}
    if mas2_bytes:
        texto_mas2 = utils.decodificar_bytes(mas2_bytes)
        mas2_ids = {int(x) for x in re.findall(r"\b\d{7,}\b", texto_mas2)}
        veces = prestamos_del_listado(texto_mas2)

    for r in registros:
        prestamos = 1
        if r["record_id"] in nunca_ids:
            prestamos = 0
        if r["record_id"] in mas2_ids:
            prestamos = 2
        r["prestamos"] = prestamos
        r["prestado"] = prestamos > 0
        # Número de préstamos del listado de más prestados, si el listado lo
        # trae. Solo lo tienen los ejemplares que salen en ese listado.
        r["n_prestamos"] = veces.get(r["record_id"], 0)
        r["categoria"] = clasificacion.categoria_analisis(r["signatura_real"])
        r["macro_seccion"] = clasificacion.clasificar_macro(r["categoria"])
        r["es_infantil"] = clasificacion.es_categoria_infantil(r["categoria"])

        ficha = fichas.get(r["record_id"]) or {}
        r["autor"] = ficha.get("autor") or ""
        r["isbn"] = utils.isbn13(ficha.get("isbn")) if ficha.get("isbn") else None
        r["materias_texto"] = " | ".join(ficha.get("materias") or [])
        if ficha.get("titulo"):
            r["titulo"] = ficha["titulo"]
        r["idioma"] = None  # se completa después con la base de la red

    return registros, total_topo - len(registros), fichas
