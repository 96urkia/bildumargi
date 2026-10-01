# -*- coding: utf-8 -*-
"""Análisis de la colección propia: métricas, agregados y búsquedas.

Todo trabaja sobre listas de diccionarios, sin pandas: una colección
municipal típica ronda los 20.000-40.000 ejemplares y el coste es
despreciable, a cambio de una instalación mucho más ligera.
"""

import statistics
from collections import Counter, defaultdict

from . import clasificacion, idiomas as mod_idiomas, utils

IDIOMA_SIN_DATO = mod_idiomas.IDIOMA_SIN_DATO

# Primer año que muestra el gráfico de evolución.
ANIO_BASE_HISTOGRAMA = 1980

# --- Referencia de fondo por habitante -------------------------------------
# Vive en datos/pautas.json para que cada red ponga la suya (un estándar
# autonómico, el plan de su red...). Por defecto: Pautas sobre los servicios de
# las bibliotecas públicas (2002) / IFLA-UNESCO (2001): de 1,5 a 2,5
# documentos por habitante y un fondo mínimo de 2.500.
_PAUTAS_DEFECTO = {
    "fuente": "Pautas sobre los servicios de las bibliotecas públicas (2002) / IFLA-UNESCO (2001)",
    "fuente_corta": "Pautas BP 2002 / IFLA",
    "tramos": [{"hasta_habitantes": None, "docs_hab_min": 1.5, "docs_hab_max": 2.5,
                "fondo_minimo": 2500}],
}
_pautas_cache = None


def cargar_pautas(ruta=None):
    """Lee datos/pautas.json; si falta o está mal formado, usa la de por defecto."""
    global _pautas_cache
    if _pautas_cache is not None and ruta is None:
        return _pautas_cache
    import json
    import os
    from config import RUTA_DATOS
    ruta = ruta or os.path.join(RUTA_DATOS, "pautas.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        tramos = [t for t in datos.get("tramos", [])
                  if float(t["docs_hab_min"]) <= float(t["docs_hab_max"])]
        if not tramos:
            raise ValueError("sin tramos válidos")
        datos["tramos"] = tramos
    except (OSError, ValueError, KeyError, TypeError):
        datos = _PAUTAS_DEFECTO
    _pautas_cache = datos
    return datos


def pauta_para(poblacion):
    """Tramo de referencia aplicable a un municipio (o None sin población)."""
    if not poblacion:
        return None
    pautas = cargar_pautas()
    for tramo in pautas["tramos"]:
        techo = tramo.get("hasta_habitantes")
        if techo is None or poblacion <= techo:
            return {
                "docs_hab_min": float(tramo["docs_hab_min"]),
                "docs_hab_max": float(tramo["docs_hab_max"]),
                "fondo_minimo": tramo.get("fondo_minimo"),
                "fuente": pautas.get("fuente", ""),
                "fuente_corta": pautas.get("fuente_corta") or pautas.get("fuente", ""),
            }
    return None


def _media(valores):
    limpios = [v for v in valores if v is not None]
    return statistics.fmean(limpios) if limpios else None


def filtrar(registros, idioma="__TODOS__", loc="__TODAS__", publico="todo"):
    salida = registros
    if idioma and idioma != "__TODOS__":
        salida = [r for r in salida if r.get("idioma") == idioma]
    if loc and loc != "__TODAS__":
        salida = [r for r in salida if r.get("loc") == loc]
    if publico == "adultos":
        salida = [r for r in salida if not r["es_infantil"]]
    elif publico == "infantil":
        salida = [r for r in salida if r["es_infantil"]]
    return salida


def opciones_filtros(registros):
    idiomas_pres = sorted({r.get("idioma") for r in registros if r.get("idioma")})
    # «Sin determinar» al final: es un cajón de sastre, no un idioma más.
    idiomas_pres = ([i for i in idiomas_pres if i != IDIOMA_SIN_DATO]
                    + ([IDIOMA_SIN_DATO] if any(r.get("idioma") == IDIOMA_SIN_DATO
                                                for r in registros) else []))
    locs = sorted({r.get("loc") for r in registros if r.get("loc")})
    return {"idiomas": idiomas_pres, "localizaciones": locs}


def metricas_cabecera(registros, poblacion, superficie):
    total = len(registros)
    prestados = sum(1 for r in registros if r["prestado"])
    anios = [r["year"] for r in registros if r.get("year")]
    return {
        "total": total,
        "pct_prestados": round(prestados / total * 100, 1) if total else 0.0,
        "edad_media": int(_media(anios)) if anios else None,
        "docs_habitante": round(total / poblacion, 2) if poblacion else None,
        "docs_m2": round(total / superficie, 1) if superficie else None,
        "poblacion": poblacion,
        "superficie": superficie,
        "pauta": pauta_para(poblacion),
    }


def _agrupar(registros, clave, total_referencia=None):
    grupos = defaultdict(list)
    for r in registros:
        valor = clave(r)
        if valor is None:
            continue
        grupos[valor].append(r)
    total_referencia = total_referencia if total_referencia is not None else len(registros)
    filas = []
    for valor, items in grupos.items():
        n = len(items)
        prestados = sum(1 for r in items if r["prestado"])
        anios = [r["year"] for r in items if r.get("year")]
        filas.append({
            "clave": valor,
            "volumenes": n,
            "prestados": prestados,
            "rotacion": round(prestados / n * 100, 1) if n else 0.0,
            "distribucion": round(n / total_referencia * 100, 1) if total_referencia else 0.0,
            "anio_medio": int(_media(anios)) if anios else None,
        })
    return filas


def tabla_categorias(registros):
    """Volúmenes, uso y edad media por categoría, separando adultos e
    infantil, que es como se trabaja la colección en la práctica."""
    filas = _agrupar(registros, lambda r: r["categoria"])
    for f in filas:
        f["es_infantil"] = clasificacion.es_categoria_infantil(f["clave"])
    adultos = sorted([f for f in filas if not f["es_infantil"]],
                     key=lambda f: -f["volumenes"])
    infantil = sorted([f for f in filas if f["es_infantil"]],
                      key=lambda f: -f["volumenes"])
    return {"adultos": adultos, "infantil": infantil}


def tabla_idiomas(registros, poblacion, idioma_ui="es"):
    secciones = {
        "completa": registros,
        "adultos": [r for r in registros if r["macro_seccion"] == "Adultos"],
        "infantil": [r for r in registros if r["macro_seccion"] == "Infantil/Juvenil"],
        "audiovisuales": [r for r in registros if r["macro_seccion"] == "Audiovisuales"],
    }
    salida = {}
    for nombre, sub in secciones.items():
        filas = sorted(_agrupar(sub, lambda r: r.get("idioma") or IDIOMA_SIN_DATO),
                       key=lambda f: -f["volumenes"])
        for f in filas:
            f["etiqueta"] = mod_idiomas.traducir_idioma(f["clave"], idioma_ui)
            f["registros_habitante"] = (round(f["volumenes"] / poblacion, 3)
                                        if poblacion else None)
        salida[nombre] = filas

    total = len(registros)
    conteo = Counter(r.get("idioma") or IDIOMA_SIN_DATO for r in registros)
    con_dato = total - conteo.get(IDIOMA_SIN_DATO, 0)
    return {
        "secciones": salida,
        "resumen": {
            "total": total,
            "con_dato": con_dato,
            "cobertura": round(con_dato / total * 100, 1) if total else 0.0,
            "distintos": len([k for k in conteo if k != IDIOMA_SIN_DATO]),
            "pct_euskera": round(conteo.get("Euskera", 0) / total * 100, 1) if total else 0.0,
        },
    }


CAMPOS_BUSQUEDA = {"signatura": "signatura_real", "titulo": "titulo",
                   "autor": "autor", "materia": "materias_texto"}


def buscar(registros, campo="signatura", texto="", prestamos="todos",
           anio_desde=None, anio_hasta=None, publico="todo",
           idioma="__TODOS__", loc="__TODAS__", categoria=None, anio=None):
    """Búsqueda libre sobre la colección, con filtros y paginación.

    `anio_desde`/`anio_hasta` acotan por año de edición, los dos inclusive:
    solo `anio_desde` es «desde ese año en adelante», solo `anio_hasta` es
    «hasta ese año», y los dos juntos son un intervalo cerrado."""
    salida = filtrar(registros, idioma=idioma, loc=loc, publico=publico)

    if categoria:
        salida = [r for r in salida if r["categoria"] == categoria]

    if anio:
        salida = [r for r in salida if str(r.get("year") or "") == str(anio)]

    texto = (texto or "").strip()
    if texto:
        columna = CAMPOS_BUSQUEDA.get(campo, "signatura_real")
        if columna == "signatura_real":
            # Varias signaturas separadas por comas se suman: «32*, I 32*»
            # recoge la sección de adultos y la infantil a la vez.
            patrones = [p.strip().upper() for p in texto.split(",") if p.strip()]
            salida = [r for r in salida
                      if any(utils.mask_comodin(r[columna], p) for p in patrones)]
        else:
            salida = [r for r in salida if utils.mask_multitoken(r.get(columna), texto)]

    if prestamos == "nunca":
        salida = [r for r in salida if r["prestamos"] == 0]
    elif prestamos == "estandar":
        salida = [r for r in salida if r["prestamos"] == 1]
    elif prestamos == "alta":
        salida = [r for r in salida if r["prestamos"] == 2]

    # Los dos extremos son inclusive. Los registros sin año se descartan
    # mientras el filtro esté activo, pero se cuentan: en una revisión de
    # sección ese dato importa.
    sin_anio_rango = 0
    if anio_desde is not None or anio_hasta is not None:
        sin_anio_rango = sum(1 for r in salida if not r.get("year"))
        filtrados = []
        for r in salida:
            anio_reg = r.get("year")
            if not anio_reg:
                continue
            if anio_desde is not None and anio_reg < anio_desde:
                continue
            if anio_hasta is not None and anio_reg > anio_hasta:
                continue
            filtrados.append(r)
        salida = filtrados

    return salida, sin_anio_rango


def histograma_anual(seleccion, desde=None):
    """Volúmenes y uso por año de edición.

    El suelo es 1980 salvo que el fondo empiece después: más atrás la cola es
    plana y solo comprime la parte legible. Lo anterior se devuelve agregado.
    """
    anios = [int(r["year"]) for r in seleccion if r.get("year")]
    if not anios:
        return {"filas": [], "anteriores": 0, "sin_anio": len(seleccion)}
    tope = max(anios)
    suelo = max(min(anios), desde or ANIO_BASE_HISTOGRAMA)
    por_anio = {}
    anteriores = 0
    for r in seleccion:
        if not r.get("year"):
            continue
        a_ = int(r["year"])
        if a_ < suelo:
            anteriores += 1
            continue
        entrada = por_anio.setdefault(a_, {"clave": a_, "volumenes": 0, "prestados": 0})
        entrada["volumenes"] += 1
        entrada["prestados"] += 1 if r["prestado"] else 0
    filas = []
    for a_ in range(suelo, tope + 1):
        e = por_anio.get(a_, {"clave": a_, "volumenes": 0, "prestados": 0})
        e["rotacion"] = round(e["prestados"] / e["volumenes"] * 100, 1) if e["volumenes"] else 0.0
        filas.append(e)
    return {"filas": filas, "anteriores": anteriores,
            "sin_anio": sum(1 for r in seleccion if not r.get("year"))}


def reparto(seleccion, clave):
    """Volúmenes, uso y antigüedad de cada grupo dentro de la selección."""
    filas = _agrupar(seleccion, clave)
    filas.sort(key=lambda f: -f["volumenes"])
    return filas


def perfil_secciones(registros, anio_actual):
    """Por sección del fondo propio: volúmenes, prestados y actualidad.

    Es lo que las sugerencias de compra cruzan con la oferta de la red: dónde
    hay más demanda que peso y dónde el fondo está menos actualizado."""
    salida = {}
    for r in registros:
        # Sección estándar: es la que se cruza con la oferta de la red
        clave = r.get("categoria_estandar") or r["categoria"]
        e = salida.setdefault(clave, {"clave": clave, "volumenes": 0, "prestados": 0,
                                              "con_anio": 0, "recientes": 0})
        e["volumenes"] += 1
        e["prestados"] += 1 if r["prestado"] else 0
        if r.get("year"):
            e["con_anio"] += 1
            e["recientes"] += 1 if int(r["year"]) >= anio_actual - 4 else 0
    return sorted(salida.values(), key=lambda e: -e["volumenes"])


def resumen_seleccion(seleccion):
    total = len(seleccion)
    anios = [r["year"] for r in seleccion if r.get("year")]
    return {
        "volumenes": total,
        "pct_prestamos": (round(sum(1 for r in seleccion if r["prestado"]) / total * 100, 1)
                          if total else 0.0),
        "anio_medio": int(_media(anios)) if anios else None,
    }


# --- Cotejo contra el fondo real -------------------------------------------
# La base de la red puede estar desactualizada y proponer títulos que la
# biblioteca ya tiene. Antes de recomendar, se cruza cada sugerencia contra el
# topográfico y el catálogo de la sesión, con claves normalizadas.

def construir_indice_fondo(registros, fichas):
    titulo_autor, titulos, isbns, ids = set(), set(), set(), set()
    for r in registros or []:
        # Identificador del registro en la base de la red (vía código de
        # barras): es el cotejo más fiable, no depende de cómo se escriba
        if r.get("id_sistema"):
            ids.add(utils.clave_id(r["id_sistema"]))
        ct = utils.clave_titulo(r.get("titulo"))
        if not ct:
            continue
        titulos.add(ct)
        ca = utils.clave_autor(r.get("autor"))
        if ca:
            titulo_autor.add(f"{ct}|{ca}")
    for ficha in (fichas or {}).values():
        ct = utils.clave_titulo(ficha.get("titulo"))
        if ct:
            titulos.add(ct)
            ca = utils.clave_autor(ficha.get("autor"))
            if ca:
                titulo_autor.add(f"{ct}|{ca}")
        isbns |= utils.claves_isbn(ficha.get("isbn"))
    ids.discard(None)
    ids.discard("")
    return {"titulo_autor": titulo_autor, "titulos": titulos, "isbn": isbns, "ids": ids}


def estado_en_fondo(fila, indice):
    """'EN_FONDO' si coincide título + primer apellido (o ISBN); 'POSIBLE' si
    coincide solo un título largo; '' si no consta."""
    if not indice:
        return ""
    if fila.get("id_sistema") and utils.clave_id(fila["id_sistema"]) in (indice.get("ids") or ()):
        return "EN_FONDO"
    if not indice.get("titulos"):
        return ""
    ct = utils.clave_titulo(fila.get("titulo"))
    ca = utils.clave_autor(fila.get("autor"))
    if ct and ca and f"{ct}|{ca}" in indice["titulo_autor"]:
        return "EN_FONDO"
    if fila.get("isbn") and utils.claves_isbn(fila["isbn"]) & indice["isbn"]:
        return "EN_FONDO"
    if ct and len(ct) >= 8 and ct in indice["titulos"]:
        return "POSIBLE"
    return ""


