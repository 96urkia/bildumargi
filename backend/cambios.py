# -*- coding: utf-8 -*-
"""Altas y bajas entre dos cargas.

Se comparan los listados topográficos por código de barras:

    alta   ejemplar que está en esta carga y no en la anterior
    baja   ejemplar que estaba en la anterior y ya no está: expurgo, pérdida
           o traslado a otra biblioteca

Solo dice qué ha cambiado, no por qué. Si los dos topográficos se exportaron
con criterios distintos (otras localizaciones, por ejemplo), saldrán
diferencias que no son altas ni bajas: la interfaz lo advierte.
"""

import collections

from . import absysnet, clasificacion

CAMPOS = ("record_id", "signatura_real", "titulo", "loc", "categoria")


def _ejemplares(topo_bytes, reglas):
    lista = absysnet.leer_topografico(topo_bytes) if topo_bytes else []
    for r in lista:
        r["categoria"] = clasificacion.categoria_analisis(r["signatura_real"])
    clasificacion.aplicar_reglas(lista, reglas)
    return {r["record_id"]: r for r in lista}


def comparar(topo_anterior, topo_actual, reglas=None):
    """Altas y bajas de `topo_actual` respecto a `topo_anterior` (bytes de
    los dos listados topográficos). `reglas`: tabla de signaturas en vigor,
    para agrupar por sección igual que el análisis."""
    antes = _ejemplares(topo_anterior, reglas)
    ahora = _ejemplares(topo_actual, reglas)
    altas = [ahora[k] for k in ahora.keys() - antes.keys()]
    bajas = [antes[k] for k in antes.keys() - ahora.keys()]
    orden = lambda r: (r.get("signatura_real") or "", r.get("titulo") or "")
    por_seccion = collections.defaultdict(lambda: {"altas": 0, "bajas": 0})
    for r in altas:
        por_seccion[r["categoria"]]["altas"] += 1
    for r in bajas:
        por_seccion[r["categoria"]]["bajas"] += 1
    return {
        "altas": len(altas),
        "bajas": len(bajas),
        "antes": len(antes),
        "ahora": len(ahora),
        "por_seccion": sorted(({"clave": k, **v} for k, v in por_seccion.items()),
                              key=lambda x: -(x["altas"] + x["bajas"])),
        "lista_altas": [{c: r.get(c) for c in CAMPOS} for r in sorted(altas, key=orden)],
        "lista_bajas": [{c: r.get(c) for c in CAMPOS} for r in sorted(bajas, key=orden)],
    }
