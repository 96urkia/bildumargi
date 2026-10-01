# -*- coding: utf-8 -*-
"""
Bildumargi · Conversor de MARC a base de datos
==============================================

Convierte la exportación MARC del catálogo colectivo en el fichero .db que
Bildumargi necesita para las recomendaciones de compra.

    python conversor.py todopublicas.mrc
    python conversor.py catalogo.mods -o datos/base_red.db
    python conversor.py exportaciones/ --anio-minimo-marcxml 2015

Formatos de entrada admitidos:
    .mrc / .mrk / .marc      MARC21 binario (lo habitual en AbsysNet/Baratz)
    .xml / .mods / .marcxml  MARCXML

Después, escribe la ruta del .db resultante en la línea 34 de config.py.

Tablas que genera
-----------------
    libros         id_sistema, isbn, autor, titulo, editorial, anio, cdu, anio_num
    ejemplares     id_sistema, biblioteca, seccion, signatura, codigo_barras
    materias       id_sistema, materia
    idiomas_reg    id_sistema, idioma, idioma_original, traduccion
    marc_completo  id_sistema, marcxml
    materias_fts / libros_fts   índices de búsqueda por texto (FTS5 trigram)

Sobre el tamaño del fichero
---------------------------
Medido sobre 500.000 registros: con MARCXML completo la base pesa ~2,1 GB y
sin él ~850 MB. El MARCXML solo se usa para la ficha catalográfica de un
registro concreto, y Bildumargi cae a los datos de `libros` cuando no lo
encuentra, así que recortarlo por año (--anio-minimo-marcxml) o quitarlo del
todo (--sin-marc) es la primera palanca si necesitas una base más ligera.
Los índices FTS5 trigram casi triplican el fichero (61 MB -> 170 MB para
100.000 registros); --sin-fts los omite.

Creado por: Asier Urkia · bildumargi@gmail.com
Licencia: AGPLv3 (ver LICENSE)
"""

import argparse
import logging
import os
import re
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from pymarc import MARCReader, parse_xml_to_array
    from pymarc.marcxml import record_to_xml
except ImportError:
    print("\nFalta la librería pymarc. Instálala con:\n\n    pip install pymarc\n")
    sys.exit(1)

from backend.idiomas import IDIOMAS_MARC  # noqa: E402

logging.getLogger("pymarc").setLevel(logging.ERROR)

# ===========================================================================
# MAPEO DEL CAMPO 952 (ejemplares)
# ===========================================================================
# Este es el único punto que conviene revisar si tu catálogo coloca los datos
# del ejemplar en otros subcampos. Los valores por defecto son los de
# AbsysNet/Baratz.
SUB_BIBLIOTECA = "a"
SUB_SECCION = "b"
SUB_SIGNATURA = "c"
SUB_CODIGO_BARRAS = "p"

EXT_BINARIO = (".mrc", ".marc", ".mrk", ".dat")
EXT_XML = (".xml", ".mods", ".marcxml")

_RE_COD3 = re.compile(r"[a-z]{3}")
_RE_ANIO = re.compile(r"(1[89]\d{2}|20\d{2})")


def nombre_idioma(cod):
    if not cod:
        return None
    cod = cod.lower().strip()
    return IDIOMAS_MARC.get(cod, f"Otro ({cod})")


def extraer_idioma(record):
    """idioma desde el MARC 008 (posiciones 35-37), exclusivamente.

    El 041 NO se usa: admite varios códigos en $a y puede contradecir al 008
    (p. ej. 041$a='cat' con 008='spa'), lo que producía registros catalogados
    como castellano que salían como catalán. `idioma_original` y `traduccion`
    se conservan en la tabla por compatibilidad, pero ya no se calculan.
    """
    if "008" not in record:
        return None, None, 0
    dato = record["008"].data or ""
    if len(dato) < 38:
        return None, None, 0
    posible = dato[35:38].strip().lower()
    if not _RE_COD3.fullmatch(posible):
        return None, None, 0
    return nombre_idioma(posible), None, 0


def extraer_anio_numerico(record):
    """Año de publicación como entero, en orden de fiabilidad.

    1. 008/07-10 ("Date 1"): fecha canónica y siempre numérica.
    2. 260$c: texto libre, en catalogación ISBD clásica.
    3. 264$c: equivalente en catalogación RDA.

    Leer solo el 260 dejaba sin año los registros en RDA, que son precisamente
    los más recientes; al filtrar recomendaciones por año se caían todos sin
    que nada avisara. El 008 rescata además casos como 'ca. 2018' o 'S.a.',
    donde el texto libre no da un año utilizable.
    """
    if "008" in record:
        datos = record["008"].data or ""
        if len(datos) >= 11 and datos[7:11].isdigit():
            anio = int(datos[7:11])
            if 1800 <= anio <= 2100:
                return anio
    for tag in ("260", "264"):
        for campo in record.get_fields(tag):
            if "c" in campo:
                m = _RE_ANIO.search(campo["c"] or "")
                if m:
                    return int(m.group(1))
    return None


def sin_acentos(texto):
    if not texto:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


ESQUEMA = """
CREATE TABLE libros (
    id_sistema TEXT PRIMARY KEY, isbn TEXT, autor TEXT, titulo TEXT,
    editorial TEXT, anio TEXT, cdu TEXT,
    -- anio_num: el año ya extraído como entero. `anio` es texto libre del
    -- 260$c y trae cosas como 'ca. 2018' o '[2015?]', que un CAST en SQL
    -- convierte en 0 y descarta en silencio. Además, un CAST en el WHERE
    -- impide usar índice; una columna INTEGER sí lo permite.
    anio_num INTEGER
);
CREATE TABLE ejemplares (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_sistema TEXT, biblioteca TEXT,
    seccion TEXT, signatura TEXT, codigo_barras TEXT
);
CREATE TABLE materias (
    id_sistema TEXT, materia TEXT
);
CREATE TABLE marc_completo (
    id_sistema TEXT PRIMARY KEY, marcxml TEXT
);
CREATE TABLE idiomas_reg (
    id_sistema TEXT PRIMARY KEY, idioma TEXT, idioma_original TEXT, traduccion INTEGER
);
"""

INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_libros_titulo ON libros(titulo)",
    "CREATE INDEX IF NOT EXISTS idx_libros_autor ON libros(autor)",
    "CREATE INDEX IF NOT EXISTS idx_libros_cdu ON libros(cdu)",
    "CREATE INDEX IF NOT EXISTS idx_libros_anio ON libros(anio)",
    "CREATE INDEX IF NOT EXISTS idx_libros_anio_num ON libros(anio_num)",
    "CREATE INDEX IF NOT EXISTS idx_ejemplares_id ON ejemplares(id_sistema)",
    "CREATE INDEX IF NOT EXISTS idx_ejemplares_biblioteca ON ejemplares(biblioteca)",
    # Imprescindible: 1,19 s -> 0,03 s al traducir 20.000 códigos de barras.
    # El análisis de la colección se identifica por código de barras (952$p) y
    # no por id_sistema (001), así que esta traducción se hace en cada carga.
    "CREATE INDEX IF NOT EXISTS idx_ejemplares_codbar ON ejemplares(codigo_barras)",
    "CREATE INDEX IF NOT EXISTS idx_materias_id ON materias(id_sistema)",
    "CREATE INDEX IF NOT EXISTS idx_materias_texto ON materias(materia)",
    "CREATE INDEX IF NOT EXISTS idx_idiomas_idioma ON idiomas_reg(idioma)",
]


def ficheros_de(entradas):
    extensiones = EXT_BINARIO + EXT_XML
    for entrada in entradas:
        if os.path.isdir(entrada):
            for nombre in sorted(os.listdir(entrada)):
                if nombre.lower().endswith(extensiones):
                    yield os.path.join(entrada, nombre)
        elif os.path.exists(entrada):
            yield entrada
        else:
            print(f"  AVISO: no se encuentra «{entrada}», se omite.")


def registros_de(ruta, codificacion="iso-8859-1"):
    """Devuelve los registros de un fichero, sea MARC binario o MARCXML."""
    if ruta.lower().endswith(EXT_XML):
        for record in parse_xml_to_array(ruta):
            if record is not None:
                yield record
        return
    with open(ruta, "rb") as fh:
        lector = MARCReader(fh, to_unicode=True, file_encoding=codificacion)
        for record in lector:
            if record is not None:
                yield record


def convertir(entradas, salida, anio_minimo=None, anio_minimo_marcxml=2015,
              guardar_marc=True, crear_fts=True, fts_libros=True,
              codificacion="iso-8859-1"):
    if os.path.exists(salida):
        os.remove(salida)
    carpeta = os.path.dirname(os.path.abspath(salida))
    os.makedirs(carpeta, exist_ok=True)

    print("Configurando base de datos SQLite…")
    conn = sqlite3.connect(salida)
    cursor = conn.cursor()
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.executescript(ESQUEMA)
    conn.commit()

    buf_libros, buf_ejemplares, buf_materias, buf_marc, buf_idiomas = [], [], [], [], []

    def volcar():
        if buf_libros:
            cursor.executemany("INSERT OR IGNORE INTO libros VALUES (?,?,?,?,?,?,?,?)", buf_libros)
        if buf_ejemplares:
            cursor.executemany("INSERT INTO ejemplares (id_sistema,biblioteca,seccion,signatura,codigo_barras) "
                               "VALUES (?,?,?,?,?)", buf_ejemplares)
        if buf_materias:
            cursor.executemany("INSERT INTO materias (id_sistema,materia) VALUES (?,?)", buf_materias)
        if buf_marc:
            cursor.executemany("INSERT OR IGNORE INTO marc_completo VALUES (?,?)", buf_marc)
        if buf_idiomas:
            cursor.executemany("INSERT OR IGNORE INTO idiomas_reg VALUES (?,?,?,?)", buf_idiomas)
        conn.commit()
        for b in (buf_libros, buf_ejemplares, buf_materias, buf_marc, buf_idiomas):
            b.clear()

    print("Procesando registros MARC…")
    count = count_incluidos = count_marc = count_ejemplares = 0

    for ruta in ficheros_de(entradas):
        print(f"  Leyendo {os.path.basename(ruta)} …")
        for record in registros_de(ruta, codificacion):
            if "001" not in record:
                continue
            count += 1
            id_sistema = record["001"].data.strip()

            titulo = record.title.strip().rstrip(" /") if record.title else None
            autor = record.author.strip().rstrip(",") if record.author else None
            isbn = record["020"]["a"].strip() if "020" in record and "a" in record["020"] else None

            editorial = anio = None
            for tag in ("260", "264"):        # 264 = equivalente RDA del 260
                for campo in record.get_fields(tag):
                    if editorial is None and "b" in campo:
                        editorial = campo["b"].strip().rstrip(",")
                    if anio is None and "c" in campo:
                        anio = (campo["c"].replace("D.L.", "").replace("[", "")
                                .replace("]", "").replace("c", "").strip().rstrip("."))

            anio_num = extraer_anio_numerico(record)

            # Corte opcional. Sin él no se descarta nada, que es lo que hace
            # falta para que el análisis de idiomas cubra todo el fondo y no
            # solo el tramo reciente.
            if anio_minimo is not None and (anio_num is None or anio_num < anio_minimo):
                if count % 10000 == 0:
                    print(f"    Leídos {count:,} | incluidos {count_incluidos:,} | marcxml {count_marc:,}")
                continue

            count_incluidos += 1
            cdu = record["080"]["a"].strip() if "080" in record and "a" in record["080"] else None

            buf_libros.append((id_sistema, isbn, autor, titulo, editorial, anio, cdu, anio_num))

            for campo in record.get_fields("650"):
                subcampos = [valor.strip() for clave, valor in campo]
                if subcampos:
                    buf_materias.append((id_sistema, " -- ".join(subcampos)))

            for campo in record.get_fields("952"):
                biblioteca = campo[SUB_BIBLIOTECA].strip() if SUB_BIBLIOTECA in campo else None
                if biblioteca:
                    count_ejemplares += 1
                    buf_ejemplares.append((
                        id_sistema, biblioteca,
                        campo[SUB_SECCION].strip() if SUB_SECCION in campo else None,
                        campo[SUB_SIGNATURA].strip() if SUB_SIGNATURA in campo else None,
                        campo[SUB_CODIGO_BARRAS].strip() if SUB_CODIGO_BARRAS in campo else None,
                    ))

            # --- idioma precalculado: barato en espacio, caro de recalcular ---
            idi, orig, trad = extraer_idioma(record)
            buf_idiomas.append((id_sistema, idi, orig, trad))

            # --- MARCXML solo para el tramo indicado ---
            debe_guardar = guardar_marc and (
                anio_minimo_marcxml is None
                or (anio_minimo_marcxml > 0 and anio_num is not None and anio_num >= anio_minimo_marcxml))
            if debe_guardar:
                try:
                    buf_marc.append((id_sistema, record_to_xml(record).decode("utf-8")))
                    count_marc += 1
                except Exception:
                    pass

            if count % 10000 == 0:
                volcar()
                print(f"    Leídos {count:,} | incluidos {count_incluidos:,} | marcxml {count_marc:,}")

    volcar()

    print("Creando índices…")
    for q in INDICES:
        cursor.execute(q)
    conn.commit()

    if crear_fts:
        conn.create_function("SIN_ACENTOS", 1, sin_acentos)
        version = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
        if version < (3, 34, 0):
            print(f"  AVISO: SQLite {sqlite3.sqlite_version} no soporta el tokenizador "
                  f"'trigram' (necesita >= 3.34). Se omiten los índices FTS5.")
        else:
            print("Creando FTS5 de materias…")
            cursor.executescript("""
                DROP TABLE IF EXISTS materias_fts;
                CREATE VIRTUAL TABLE materias_fts USING fts5(
                    id_sistema UNINDEXED, materia_norm, tokenize = 'trigram');
            """)
            cursor.execute("""INSERT INTO materias_fts (id_sistema, materia_norm)
                              SELECT id_sistema, SIN_ACENTOS(UPPER(materia)) FROM materias
                              WHERE materia IS NOT NULL""")
            cursor.execute("INSERT INTO materias_fts(materias_fts) VALUES('optimize')")

            if fts_libros:
                print("Creando FTS5 de libros (título/autor)…")
                cursor.executescript("""
                    DROP TABLE IF EXISTS libros_fts;
                    CREATE VIRTUAL TABLE libros_fts USING fts5(
                        id_sistema UNINDEXED, titulo_norm, autor_norm, tokenize = 'trigram');
                """)
                cursor.execute("""INSERT INTO libros_fts (id_sistema, titulo_norm, autor_norm)
                                  SELECT id_sistema, SIN_ACENTOS(UPPER(COALESCE(titulo,''))),
                                         SIN_ACENTOS(UPPER(COALESCE(autor,''))) FROM libros""")
                cursor.execute("INSERT INTO libros_fts(libros_fts) VALUES('optimize')")
            conn.commit()

    # VACUUM no aporta datos, solo compacta: si falla no debe tumbar el
    # proceso después de un volcado largo.
    print("Compactando…")
    try:
        cursor.execute("VACUUM")
    except sqlite3.Error as e:
        print(f"  AVISO: VACUUM no se ha podido completar ({e}). La base es válida, "
              f"solo queda sin compactar.")

    resumen = cursor.execute("""
        SELECT COALESCE(idioma,'Sin determinar') AS idi, COUNT(*)
        FROM idiomas_reg GROUP BY idi ORDER BY 2 DESC
    """).fetchall()
    sin_anio, desde_2015 = cursor.execute("""
        SELECT SUM(CASE WHEN anio_num IS NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN anio_num >= 2015 THEN 1 ELSE 0 END) FROM libros
    """).fetchone()
    bibliotecas = cursor.execute(
        "SELECT COUNT(DISTINCT biblioteca) FROM ejemplares").fetchone()[0]

    # Fusionar el WAL y dejar el fichero autónomo ANTES de cerrar. Un .db en
    # modo WAL sin fusionar pierde en silencio los registros que todavía viven
    # en el -wal, y además necesita permiso de escritura en su carpeta incluso
    # para leerlo: fatal si se distribuye por correo o se sube a un servidor.
    try:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cursor.execute("PRAGMA journal_mode = DELETE")
    except sqlite3.Error as e:
        print(f"  AVISO: no se ha podido consolidar el WAL ({e}).")
    conn.close()

    tamano_mb = os.path.getsize(salida) / (1024 * 1024)
    print()
    print("=" * 46)
    print("PROCESO FINALIZADO")
    print("=" * 46)
    print(f"Registros MARC leídos:  {count:,}")
    print(f"Registros incluidos:    {count_incluidos:,}")
    print(f"Ejemplares (952):       {count_ejemplares:,}")
    print(f"Bibliotecas distintas:  {bibliotecas:,}")
    print(f"Con MARCXML guardado:   {count_marc:,}")
    print(f"Sin año detectable:     {sin_anio or 0:,}")
    print(f"Publicados desde 2015:  {desde_2015 or 0:,}")
    print(f"Tamaño final:           {tamano_mb:.1f} MB")
    print()
    print("Reparto por idioma:")
    for idi, n in resumen[:12]:
        pct = n / count_incluidos * 100 if count_incluidos else 0
        print(f"  {idi:24} {n:>8,}  ({pct:5.1f}%)")

    if count_ejemplares == 0:
        print()
        print("AVISO: no se ha leído ningún ejemplar del campo 952. Sin ellos no puede")
        print("saberse qué biblioteca tiene cada título y las recomendaciones de compra")
        print("saldrán vacías. Revisa el mapeo de subcampos al principio de este fichero.")
    return count_incluidos


def main():
    parser = argparse.ArgumentParser(
        description="Convierte la exportación MARC del catálogo en la base .db de Bildumargi.")
    parser.add_argument("entrada", nargs="+",
                        help="fichero .mrc/.xml/.mods, o carpeta que los contenga")
    try:
        import config as _config                  # la carpeta de datos configurada
        salida_por_defecto = os.path.join(_config.RUTA_DATOS, "base_red.db")
    except Exception:                             # noqa: BLE001 — sin config, como antes
        salida_por_defecto = os.path.join("datos", "base_red.db")
    parser.add_argument("-o", "--salida", default=salida_por_defecto,
                        help=f"ruta del .db a generar (por defecto {salida_por_defecto})")
    parser.add_argument("--anio-minimo", type=int, default=None,
                        help="descartar registros anteriores a este año (por defecto, ninguno)")
    parser.add_argument("--anio-minimo-marcxml", type=int, default=2015,
                        help="guardar el MARCXML solo desde este año (0 = ninguno)")
    parser.add_argument("--sin-marc", action="store_true",
                        help="no guardar el MARCXML: base mucho más ligera, sin ficha completa")
    parser.add_argument("--sin-fts", action="store_true",
                        help="no crear los índices FTS5 de búsqueda por texto")
    parser.add_argument("--sin-fts-libros", action="store_true",
                        help="crear el FTS5 de materias pero no el de título/autor")
    parser.add_argument("--codificacion", default="iso-8859-1",
                        help="codificación del MARC binario (por defecto iso-8859-1)")
    args = parser.parse_args()

    print("\nBildumargi · conversor de catálogo\n")
    convertir(args.entrada, args.salida,
              anio_minimo=args.anio_minimo,
              anio_minimo_marcxml=(None if args.anio_minimo_marcxml == 0 and args.sin_marc
                                   else args.anio_minimo_marcxml),
              guardar_marc=not args.sin_marc,
              crear_fts=not args.sin_fts,
              fts_libros=not args.sin_fts_libros,
              codificacion=args.codificacion)
    print(f"\nEscribe esta ruta en la línea 34 de config.py:\n    URL_BASE_DATOS = \"{args.salida}\"\n")


if __name__ == "__main__":
    main()
