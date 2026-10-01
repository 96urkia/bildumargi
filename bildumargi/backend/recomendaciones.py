# -*- coding: utf-8 -*-
"""Recomendaciones de compra a partir del catálogo colectivo de la red.

Toda esta sección depende de que haya una base de datos enlazada. Si no la
hay, `servidor.py` ni siquiera publica estos endpoints y la interfaz oculta
la pestaña entera.
"""

from . import analisis, clasificacion, idiomas as mod_idiomas, utils

ETIQUETAS_FONDO = {
    "EN_FONDO": "Ya en el fondo",
    "POSIBLE": "Puede estar en el fondo",
    "": "No consta",
}


def _anotar(filas, base, indice, excluir_fondo, solo_bibliografico, solo_normalizados=True):
    """Añade idioma, tipo de soporte y estado respecto al fondo propio, y
    aplica los filtros correspondientes. Devuelve (filas, descartes)."""
    descartes = {"en_fondo": 0, "posibles": 0, "idioma": 0, "soporte": 0}
    if not filas:
        return filas, descartes

    # 1. Cotejo contra el fondo propio.
    conservadas = []
    for fila in filas:
        estado = analisis.estado_en_fondo(fila, indice)
        if estado == "EN_FONDO":
            descartes["en_fondo"] += 1
            if excluir_fondo:
                continue
        elif estado == "POSIBLE":
            descartes["posibles"] += 1
        fila["estado_fondo"] = estado
        fila["estado_fondo_etiqueta"] = ETIQUETAS_FONDO[estado]
        conservadas.append(fila)
    filas = conservadas

    # 2. Idioma, desde el 008 del MARC.
    ids = [f["id_sistema"] for f in filas if f.get("id_sistema")]
    mapa_idiomas = base.idiomas_de(sorted(set(ids))) if ids else {}
    for fila in filas:
        fila["idioma"] = mapa_idiomas.get(fila.get("id_sistema")) or mod_idiomas.IDIOMA_SIN_DATO

    # 3. Solo idiomas dentro de la norma MARC: se descartan «Sin determinar» y
    #    los códigos 008 no catalogados, que son errores de catalogación.
    if solo_normalizados and base.hay_idiomas:
        antes = len(filas)
        filas = [f for f in filas if mod_idiomas.es_idioma_normalizado(f["idioma"])]
        descartes["idioma"] = antes - len(filas)

    # 4. Solo registros bibliográficos (sin GMD en el 245$h).
    if solo_bibliografico and base.hay_marc:
        mapa_soporte = base.soportes_de(sorted({f["id_sistema"] for f in filas if f.get("id_sistema")}))
        antes = len(filas)
        filas = [f for f in filas if mapa_soporte.get(f.get("id_sistema"), True)]
        descartes["soporte"] = antes - len(filas)

    return filas, descartes


def generales(base, biblioteca, indice, limite=50, anio_minimo=2015, idioma=None,
              excluir_fondo=True, solo_bibliografico=True):
    """Títulos más extendidos en la red que esta biblioteca no tiene.

    Se pide a la base un lote mayor del solicitado: los filtros posteriores
    (fondo propio, idioma normalizado, soporte) recortan bastante, y sin ese
    margen la lista se quedaría corta."""
    pool = int(limite) * (4 if (excluir_fondo or solo_bibliografico) else 2)
    filas = base.recomendaciones_generales(biblioteca, pool, anio_minimo, idioma)
    filas, descartes = _anotar(filas, base, indice, excluir_fondo, solo_bibliografico)

    coincidencias, exacta = base.coincidencia_biblioteca(biblioteca)
    aviso = None
    if not exacta:
        if coincidencias:
            aviso = (f"El nombre «{biblioteca}» no aparece tal cual en la base; "
                     f"se parece a: {', '.join(coincidencias[:5])}. Revisa el "
                     f"directorio de bibliotecas.")
        else:
            aviso = (f"«{biblioteca}» no aparece en la base de la red, así que "
                     f"pueden recomendarse títulos que ya estén en el fondo.")

    return {"filas": filas[:int(limite)], "descartes": descartes, "aviso": aviso}


# ===========================================================================
# Panel de recomendaciones
# ===========================================================================
def _seccion_principal(fila):
    """Sección en la que se cuenta un título, con el mismo nombre que usa el
    análisis del fondo propio («9 - Historia / Geografía»).

    `bloques_libro` puede devolver varias colocaciones cuando la red no se
    pone de acuerdo (media red lo tiene como novela, media como cómic): se
    toma la más votada."""
    destinos = clasificacion.bloques_libro(fila.get("cdu"), fila.get("todas_signaturas"))
    if not destinos:
        return None
    _grupo, categoria = destinos[0]
    return clasificacion.etiqueta_categoria(categoria)


def preparar_candidatos(base, biblioteca, indice, anio_minimo=2015, texto="", campo="titulo",
                        excluir_fondo=True, solo_bibliografico=True):
    """La parte cara del panel: sacar de la red los títulos que esta
    biblioteca no tiene, cotejarlos con el fondo, anotar idioma y soporte y
    colocarlos en su sección.

    Solo depende de estos parámetros, no de la sección ni del idioma que se
    elijan después: el servidor guarda el resultado en la sesión y cada clic
    posterior se limita a filtrar esta lista en memoria."""
    filas = base.base_recomendaciones(biblioteca, anio_minimo)

    texto = (texto or "").strip()
    if texto:
        if campo == "autor":
            filas = [f for f in filas if utils.mask_multitoken(f.get("autor"), texto)]
        elif campo == "materia":
            ids_ok = base.ids_con_materia([f["id_sistema"] for f in filas], texto)
            filas = [f for f in filas if f["id_sistema"] in ids_ok]
        else:
            filas = [f for f in filas if utils.mask_multitoken(f.get("titulo"), texto)]

    filas, descartes = _anotar(filas, base, indice, excluir_fondo, solo_bibliografico)
    for fila in filas:
        fila["seccion"] = _seccion_principal(fila)
        # Las signaturas de toda la red solo servían para colocar el título:
        # guardarlas en la sesión ocuparía más que todo lo demás junto.
        fila.pop("todas_signaturas", None)
        fila.pop("cdu", None)
    return {"filas": filas, "descartes": descartes}


def panel(base, biblioteca, indice, limite=200, anio_minimo=2015, seccion=None,
          idioma=None, texto="", campo="titulo", excluir_fondo=True, solo_bibliografico=True,
          candidatos=None):
    """Candidatos de compra: títulos que tiene la red y esta biblioteca no.

    Se ordenan por el número de bibliotecas de la red que los tienen. El
    recuento por sección se hace sobre todos los candidatos (antes de elegir
    sección), para que el panel pueda cruzarlo con la demanda propia.

    `candidatos` es el resultado de `preparar_candidatos`; si no se da, se
    calcula aquí (es lo lento)."""
    if candidatos is None:
        candidatos = preparar_candidatos(base, biblioteca, indice, anio_minimo, texto, campo,
                                         excluir_fondo, solo_bibliografico)
    filas = list(candidatos["filas"])          # copia: la lista guardada no se toca
    descartes = dict(candidatos["descartes"])

    if idioma and idioma != "__TODOS__":
        filas = [f for f in filas if f.get("idioma") == idioma]

    conteo = {}
    for fila in filas:
        if fila.get("seccion"):
            e = conteo.setdefault(fila["seccion"], {"clave": fila["seccion"], "candidatos": 0, "bibliotecas": 0})
            e["candidatos"] += 1
            e["bibliotecas"] += fila.get("n_bibliotecas") or 0
    secciones = sorted(conteo.values(), key=lambda e: -e["candidatos"])
    for e in secciones:
        e["media_bibliotecas"] = round(e["bibliotecas"] / e["candidatos"], 1) if e["candidatos"] else 0

    todas = len(filas)
    if seccion:
        filas = [f for f in filas if f.get("seccion") == seccion]

    filas.sort(key=lambda f: (-(f.get("n_bibliotecas") or 0), -(int(str(f.get("anio") or 0)[:4] or 0)
                                                                 if str(f.get("anio") or "")[:4].isdigit() else 0)))
    total = len(filas)
    n_bib = [f.get("n_bibliotecas") or 0 for f in filas]

    coincidencias, exacta = base.coincidencia_biblioteca(biblioteca)
    aviso = None
    if not exacta:
        aviso = (f"«{biblioteca}» no aparece tal cual en el catálogo de la red"
                 + (f"; se parece a: {', '.join(coincidencias[:4])}." if coincidencias
                    else ", así que pueden recomendarse títulos que ya tengas."))

    # Copias de las filas visibles: el servidor les añade valoraciones y no
    # deben quedar pegadas a la lista guardada en la sesión.
    visibles = [dict(f) for f in filas[:int(limite)]]
    return {
        "filas": visibles,
        "total": total,
        "total_sin_seccion": todas,
        "secciones": secciones,
        "descartes": descartes,
        "resumen": {
            "candidatos": total,
            "media_bibliotecas": round(sum(n_bib) / len(n_bib), 1) if n_bib else 0,
            "max_bibliotecas": max(n_bib) if n_bib else 0,
            "bibliotecas_red": max(0, len(base.bibliotecas_en_base()) - (1 if exacta else 0)),
        },
        "aviso": aviso,
    }
