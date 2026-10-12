# -*- coding: utf-8 -*-
"""Idioma de los ejemplares desde un catálogo MARC21 (opcional).

DILVE describe bien las novedades, pero no tiene muchos libros antiguos o
descatalogados; el MARC del catálogo describe casi todo el fondo, con algún
error de catalogación. Combinados se conoce el idioma de casi todo (ver
idiomas.asignar_idiomas).

El MARC llega en un .db generado con conversor.py (el del catálogo colectivo
de la red o el del propio catálogo exportado de AbsysNet). Puede pesar más de
un gigabyte, así que no se consulta en cada análisis: se extrae una vez el
idioma de los ejemplares de la biblioteca a un fichero pequeño,
datos/marc_idiomas.db, y se vuelve a extraer cuando el .db se actualiza.

Qué ejemplares: los de la biblioteca en el .db (columna `biblioteca` de
`ejemplares`), reconocida por los códigos de barras del análisis abierto.
Así entran también los que aún no están en esa carga.

Si el .db es el de la red, se guardan además los ISBN de los libros de los
autores del catálogo propio (tabla `red_libros`): de ahí salen los tomos de
las series que la biblioteca no tiene (ver servidor.py, «Completar las
series»).
"""

import collections
import os
import sqlite3
from datetime import datetime, timezone

from . import utils
from .series import autor_normalizado

TABLAS_NECESARIAS = ("ejemplares", "idiomas_reg")


class ErrorMarc(Exception):
    pass


def _por_bloques(conn, plantilla, valores, tam=900):
    valores = list(valores)
    for inicio in range(0, len(valores), tam):
        lote = valores[inicio: inicio + tam]
        yield from conn.execute(plantilla.format(marcas=",".join("?" * len(lote))), lote)


def _abrir_origen(ruta):
    ruta = os.path.abspath(os.path.expanduser(str(ruta or "").strip().strip('"')))
    if not os.path.isfile(ruta):
        raise ErrorMarc(f"No se encuentra el fichero «{ruta}».")
    try:
        conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        tablas = {f[0] for f in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.DatabaseError as exc:
        raise ErrorMarc(f"«{os.path.basename(ruta)}» no es una base de datos SQLite: {exc}")
    faltan = [t for t in TABLAS_NECESARIAS if t not in tablas]
    if faltan:
        conn.close()
        raise ErrorMarc(f"«{os.path.basename(ruta)}» no tiene las tablas {', '.join(faltan)}: "
                        "debe ser un .db generado con conversor.py.")
    return conn, ruta


def extraer(ruta_origen, codigos_barras, ruta_destino, autores=()):
    """Extrae del .db el idioma de los ejemplares de la biblioteca y lo guarda
    en `ruta_destino`, con los ISBN de los libros de `autores` (normalizados)
    que haya en el .db. Devuelve un resumen."""
    origen, ruta_origen = _abrir_origen(ruta_origen)
    try:
        codigos = [str(c) for c in codigos_barras if c]
        # La biblioteca (o bibliotecas, si cambió de nombre) de esos códigos
        bibliotecas = collections.Counter(
            b for (b,) in _por_bloques(origen, "SELECT biblioteca FROM ejemplares WHERE codigo_barras IN ({marcas})",
                                       codigos) if b)
        if not bibliotecas:
            raise ErrorMarc("Ninguno de los códigos de barras del análisis está en ese .db: "
                            "¿es el catálogo de esta biblioteca o de su red?")
        # Solo las que reúnen una parte apreciable de los códigos (no un
        # ejemplar suelto prestado o trasladado desde otra)
        total = sum(bibliotecas.values())
        nombres = [b for b, n in bibliotecas.items() if n >= max(20, total * 0.05)] or [bibliotecas.most_common(1)[0][0]]
        filas = list(_por_bloques(
            origen,
            """SELECT e.codigo_barras, i.idioma FROM ejemplares e
               JOIN idiomas_reg i ON i.id_sistema = e.id_sistema
               WHERE e.biblioteca IN ({marcas})""", nombres))
        encontrados = sum(1 for _ in _por_bloques(
            origen, "SELECT 1 FROM ejemplares WHERE codigo_barras IN ({marcas})", codigos))
        # Libros de los mismos autores en todo el .db (para completar series)
        buscados = {a for a in autores if a}
        red = set()
        if buscados and "libros" in {f[0] for f in origen.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            for autor, isbn in origen.execute(
                    "SELECT autor, isbn FROM libros WHERE isbn IS NOT NULL AND autor IS NOT NULL"):
                normalizado = autor_normalizado(autor)
                if normalizado in buscados:
                    isbn13 = utils.isbn13(isbn)
                    if isbn13:
                        red.add((normalizado, isbn13))
    finally:
        origen.close()

    temporal = f"{ruta_destino}.tmp"
    if os.path.exists(temporal):
        os.remove(temporal)
    os.makedirs(os.path.dirname(os.path.abspath(ruta_destino)) or ".", exist_ok=True)
    destino = sqlite3.connect(temporal)
    with destino:
        destino.execute("CREATE TABLE idiomas (codigo_barras TEXT PRIMARY KEY, idioma TEXT)")
        destino.execute("CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT)")
        destino.execute("CREATE TABLE red_libros (autor TEXT, isbn TEXT, PRIMARY KEY (autor, isbn))")
        destino.execute("CREATE INDEX idx_red_autor ON red_libros(autor)")
        destino.executemany("INSERT OR IGNORE INTO red_libros VALUES (?, ?)", sorted(red))
        destino.executemany("INSERT OR REPLACE INTO idiomas VALUES (?, ?)",
                            ((str(c), i) for c, i in filas if c))
        resumen = {
            "origen": ruta_origen,
            "fecha_origen": datetime.fromtimestamp(os.path.getmtime(ruta_origen), timezone.utc)
                                    .isoformat(timespec="seconds"),
            "extraido": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bibliotecas": " | ".join(nombres),
            "ejemplares": str(len({c for c, _ in filas})),
            "del_analisis": str(encontrados),
            "en_analisis": str(len(codigos)),
            "red_libros": str(len(red)),
        }
        destino.executemany("INSERT INTO meta VALUES (?, ?)", resumen.items())
    destino.close()
    os.replace(temporal, ruta_destino)
    return estado(ruta_destino)


def estado(ruta):
    """Resumen de la última extracción, o None si no la hay."""
    if not os.path.exists(ruta):
        return None
    try:
        conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        datos = dict(conn.execute("SELECT clave, valor FROM meta"))
        conn.close()
    except sqlite3.DatabaseError:
        return None
    for campo in ("ejemplares", "del_analisis", "en_analisis", "red_libros"):
        if campo in datos:
            datos[campo] = int(datos[campo])
    return datos


def idiomas_de(ruta, codigos_barras):
    """{código de barras: idioma} de los ejemplares extraídos."""
    if not os.path.exists(ruta):
        return {}
    try:
        conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        salida = dict(_por_bloques(conn, "SELECT codigo_barras, idioma FROM idiomas WHERE codigo_barras IN ({marcas})",
                                   [str(c) for c in codigos_barras]))
        conn.close()
        return salida
    except sqlite3.DatabaseError:
        return {}


def isbns_de_autores(ruta, autores):
    """{autor normalizado: {isbn}} de los libros de la red de esos autores."""
    if not os.path.exists(ruta) or not autores:
        return {}
    salida = collections.defaultdict(set)
    try:
        conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        if "red_libros" not in {f[0] for f in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            conn.close()
            return {}
        for autor, isbn in _por_bloques(conn, "SELECT autor, isbn FROM red_libros WHERE autor IN ({marcas})", autores):
            salida[autor].add(isbn)
        conn.close()
    except sqlite3.DatabaseError:
        return {}
    return salida
