# -*- coding: utf-8 -*-
"""Base de datos SQLite de la red.

La base la genera `conversor.py` a partir de los ficheros MARC del catálogo.
Puede ser un fichero local o una URL de descarga directa; en el segundo caso
se descarga una vez y se guarda en la carpeta `cache/`.

Si no hay base enlazada, o la que hay no trae las tablas del catálogo, la
aplicación sigue funcionando: el análisis de la colección propia no la
necesita. Lo que se apaga es la sección de recomendaciones de compra, que sí.
"""

import hashlib
import os
import re
import sqlite3
import urllib.request

from . import idiomas, utils

TABLAS_MINIMAS = ("libros", "ejemplares")


class BaseRed:
    """Conexión a la base de la red y consultas sobre el catálogo colectivo."""

    def __init__(self, origen: str, carpeta_cache: str):
        self.origen = (origen or "").strip()
        self.carpeta_cache = carpeta_cache
        self.conn = None
        self.ruta = None
        self.error = None
        self.tablas = set()
        self._cache_tabla = {}
        self._abrir()

    # -- apertura ----------------------------------------------------------
    def _abrir(self):
        if not self.origen:
            self.error = "No hay ninguna base de datos enlazada."
            return
        try:
            self.ruta = self._resolver_ruta()
        except Exception as exc:
            self.error = f"No se ha podido obtener la base de datos: {exc}"
            return

        try:
            self.conn = sqlite3.connect(self.ruta, check_same_thread=False)
            self.conn.create_function(
                "REGEXP", 2,
                lambda expr, item: bool(re.search(expr, str(item), re.IGNORECASE)) if item else False)
            self.tablas = {
                fila[0] for fila in self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")
            }
        except Exception as exc:
            self.conn = None
            self.error = f"El fichero no es una base SQLite válida: {exc}"
            return

        faltan = [t for t in TABLAS_MINIMAS if t not in self.tablas]
        if faltan:
            self.error = ("La base no contiene las tablas del catálogo "
                          f"({', '.join(faltan)}). Genérala con conversor.py.")
            return

        self._crear_indices()

    def _resolver_ruta(self):
        if not self.origen.lower().startswith(("http://", "https://")):
            ruta = self.origen
            if not os.path.isabs(ruta):
                ruta = os.path.abspath(ruta)
            if not os.path.exists(ruta):
                raise FileNotFoundError(f"no existe el fichero «{ruta}»")
            return ruta

        os.makedirs(self.carpeta_cache, exist_ok=True)
        # El nombre en disco se deriva de la URL a propósito: con un nombre
        # fijo, cambiar la URL no forzaría la descarga y se seguiría leyendo
        # la base antigua sin aviso.
        firma = hashlib.sha256(self.origen.encode("utf-8")).hexdigest()[:10]
        destino = os.path.join(self.carpeta_cache, f"base_red_{firma}.db")

        if os.path.exists(destino) and os.path.getsize(destino) < 10000:
            # Menos de 10 KB es la página HTML de descarga, no la base.
            os.remove(destino)
        if not os.path.exists(destino):
            self._limpiar_descargas(destino)
            urllib.request.urlretrieve(self.origen, destino)
        return destino

    def _limpiar_descargas(self, conservar):
        try:
            for nombre in os.listdir(self.carpeta_cache):
                ruta = os.path.join(self.carpeta_cache, nombre)
                if nombre.startswith("base_red_") and nombre.endswith(".db") and ruta != conservar:
                    os.remove(ruta)
        except OSError:
            pass

    def _crear_indices(self):
        """Sin estos índices, traducir 20.000 códigos de barras a id_sistema
        supone un escaneo completo de la tabla de ejemplares."""
        sentencias = (
            "CREATE INDEX IF NOT EXISTS idx_ejemplares_id_sistema ON ejemplares(id_sistema)",
            "CREATE INDEX IF NOT EXISTS idx_ejemplares_biblioteca ON ejemplares(biblioteca)",
            "CREATE INDEX IF NOT EXISTS idx_ejemplares_codbar ON ejemplares(codigo_barras)",
            "CREATE INDEX IF NOT EXISTS idx_libros_id_sistema ON libros(id_sistema)",
        )
        for sql in sentencias:
            try:
                self.conn.execute(sql)
            except sqlite3.Error:
                pass
        try:
            self.conn.commit()
        except sqlite3.Error:
            pass

    # -- estado ------------------------------------------------------------
    @property
    def disponible(self) -> bool:
        """True solo si hay catálogo de red utilizable. De esto depende que
        se muestre o no la sección de recomendaciones de compra."""
        return self.conn is not None and not self.error

    def tabla_existe(self, nombre) -> bool:
        return nombre in self.tablas

    @property
    def hay_marc(self) -> bool:
        return self.disponible and self.tabla_existe("marc_completo")

    @property
    def hay_idiomas(self) -> bool:
        return self.disponible and (self.tabla_existe("idiomas_reg")
                                    or self.tabla_existe("marc_completo"))

    def estado(self):
        return {
            "disponible": self.disponible,
            "hay_marc": self.hay_marc,
            "hay_idiomas": self.hay_idiomas,
            "hay_materias": self.disponible and self.tabla_existe("materias"),
            "error": self.error,
            "origen": "url" if self.origen.lower().startswith("http") else ("fichero" if self.origen else ""),
        }

    # -- consultas por bloques ---------------------------------------------
    def _por_bloques(self, plantilla, ids):
        """SQLite limita el número de variables por sentencia: se consulta en
        tandas de 800 y se devuelve un generador, para no acumular el MARCXML
        entero en memoria."""
        lista = list(ids)
        for i in range(0, len(lista), 800):
            bloque = lista[i:i + 800]
            marcas = ",".join("?" * len(bloque))
            try:
                for fila in self.conn.execute(plantilla.format(marcas=marcas), bloque):
                    yield fila
            except sqlite3.Error:
                return

    def mapa_codbar_a_id(self, codigos):
        """codigo_barras -> id_sistema. Hace falta porque son identificadores
        distintos: el topográfico trae el código de barras (952$p) y
        marc_completo se indexa por id_sistema (campo 001)."""
        mapa = {}
        if not self.disponible or not codigos:
            return mapa
        sql = "SELECT codigo_barras, id_sistema FROM ejemplares WHERE codigo_barras IN ({marcas})"
        for cb, ids in self._por_bloques(sql, codigos):
            k = utils.clave_id(cb)
            if k and k not in mapa:
                mapa[k] = utils.clave_id(ids)
        return mapa

    def biblioteca_de_codigos(self, codigos):
        """Nombre con el que figura la biblioteca en la base, sacado de sus
        propios códigos de barras (el más frecuente). Puede no coincidir
        letra a letra con el del directorio."""
        if not self.disponible or not codigos:
            return None
        cuenta = {}
        sql = "SELECT biblioteca FROM ejemplares WHERE codigo_barras IN ({marcas})"
        for (nombre,) in self._por_bloques(sql, list(codigos)[:4000]):
            if nombre:
                cuenta[nombre] = cuenta.get(nombre, 0) + 1
        return max(cuenta, key=cuenta.get) if cuenta else None

    def idiomas_de(self, ids_sistema):
        """id_sistema -> idioma. Prioridad a marc_completo (008 en directo);
        respaldo en la tabla precalculada idiomas_reg."""
        mapa = {}
        if not self.disponible or not ids_sistema:
            return mapa
        pendientes = set(ids_sistema)
        if self.tabla_existe("marc_completo"):
            sql = "SELECT id_sistema, marcxml FROM marc_completo WHERE id_sistema IN ({marcas})"
            for rid, xml in self._por_bloques(sql, ids_sistema):
                clave = utils.clave_id(rid)
                mapa[clave] = idiomas.idioma_desde_marcxml(xml)
                pendientes.discard(clave)
        if pendientes and self.tabla_existe("idiomas_reg"):
            sql = "SELECT id_sistema, idioma FROM idiomas_reg WHERE id_sistema IN ({marcas})"
            for rid, idi in self._por_bloques(sql, sorted(pendientes)):
                mapa[utils.clave_id(rid)] = idi or idiomas.IDIOMA_SIN_DATO
        return mapa

    def soportes_de(self, ids_sistema):
        """id_sistema -> es_bibliografico, según el 245$h."""
        mapa = {}
        if not self.hay_marc or not ids_sistema:
            return mapa
        sql = "SELECT id_sistema, marcxml FROM marc_completo WHERE id_sistema IN ({marcas})"
        for rid, xml in self._por_bloques(sql, ids_sistema):
            mapa[utils.clave_id(rid)] = idiomas.es_bibliografico_desde_marcxml(xml)
        return mapa

    def idiomas_disponibles(self):
        """Idiomas presentes en TODA la red, no solo en el lote descargado: el
        fondo en euskera está en menos bibliotecas que el castellano y nunca
        entraba en los primeros resultados."""
        if not self.disponible or not self.tabla_existe("idiomas_reg"):
            return []
        try:
            return sorted(r[0] for r in self.conn.execute(
                "SELECT DISTINCT idioma FROM idiomas_reg "
                "WHERE idioma IS NOT NULL AND TRIM(idioma) <> ''"))
        except sqlite3.Error:
            return []

    def bibliotecas_en_base(self):
        if not self.disponible:
            return []
        try:
            return [r[0] for r in self.conn.execute(
                "SELECT DISTINCT biblioteca FROM ejemplares WHERE biblioteca IS NOT NULL")]
        except sqlite3.Error:
            return []

    def coincidencia_biblioteca(self, nombre):
        """(coincidencias, es_exacta). Los nombres del directorio no siempre
        coinciden con el 952$a: sin coincidencia exacta, el NOT EXISTS de las
        recomendaciones es siempre cierto y se recomiendan títulos que la
        biblioteca ya tiene, sin que salte ningún error."""
        objetivo = (nombre or "").strip().upper()
        valores = self.bibliotecas_en_base()
        exactas = [v for v in valores if (v or "").strip().upper() == objetivo]
        if exactas:
            return exactas, True
        parciales = [v for v in valores if objetivo and objetivo in (v or "").strip().upper()]
        return parciales, False

    def columna_existe(self, tabla, columna):
        try:
            return any(r[1] == columna for r in self.conn.execute(f"PRAGMA table_info({tabla})"))
        except sqlite3.Error:
            return False

    def cond_anio(self):
        """`libros.anio` es TEXT y puede traer 'ca. 2015' o '[2015?]', que CAST
        convierte en 0 y descarta en silencio. Si la base trae `anio_num`
        (INTEGER) se usa esa: es exacta y permite aprovechar el índice."""
        if self.columna_existe("libros", "anio_num"):
            return "AND l.anio_num IS NOT NULL AND l.anio_num >= ?"
        return "AND CAST(COALESCE(l.anio, 0) AS INTEGER) >= ?"

    # -- recomendaciones ---------------------------------------------------
    def recomendaciones_generales(self, biblioteca, limite=50, anio_minimo=2015, idioma=None):
        """Títulos que tiene la red y no tiene esta biblioteca, ordenados por
        número de bibliotecas que los tienen.

        El año y el idioma se filtran DENTRO de la consulta, no después: el
        LIMIT se aplica tras ordenar, así que recortar primero y filtrar
        después devolvería casi siempre una lista vacía."""
        if not self.disponible:
            return []
        filtro_idioma = ""
        if idioma and self.tabla_existe("idiomas_reg"):
            filtro_idioma = ("AND EXISTS (SELECT 1 FROM idiomas_reg ir "
                             "WHERE ir.id_sistema = l.id_sistema AND ir.idioma = ?)")
        sql = f"""
            SELECT l.id_sistema, l.titulo, l.autor, l.anio,
                   COUNT(DISTINCT e.biblioteca) AS total_bibliotecas
            FROM libros l
            JOIN ejemplares e ON l.id_sistema = e.id_sistema
            WHERE NOT EXISTS (
                SELECT 1 FROM ejemplares e2
                WHERE e2.id_sistema = l.id_sistema AND TRIM(UPPER(e2.biblioteca)) = ?
            )
            {self.cond_anio()}
            {filtro_idioma}
            GROUP BY l.id_sistema, l.titulo, l.autor, l.anio
            ORDER BY total_bibliotecas DESC
            LIMIT ?
        """
        params = [biblioteca.upper().strip(), int(anio_minimo)]
        if filtro_idioma:
            params.append(idioma)
        params.append(int(limite))
        try:
            filas = self.conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            return []
        return [{"id_sistema": utils.clave_id(f[0]), "titulo": utils.sin_entidades(f[1]),
                 "autor": utils.sin_entidades(f[2]), "anio": f[3], "total_bibliotecas": f[4]} for f in filas]

    def base_recomendaciones(self, biblioteca, anio_minimo=2015):
        if not self.disponible:
            return []
        sql = f"""
            SELECT l.id_sistema, l.titulo, l.autor, l.anio, l.cdu,
                   COUNT(DISTINCT e.biblioteca) AS n_bibliotecas,
                   GROUP_CONCAT(e.signatura, '||') AS todas_signaturas
            FROM libros l
            JOIN ejemplares e ON l.id_sistema = e.id_sistema
            WHERE l.id_sistema NOT IN (
                SELECT DISTINCT id_sistema FROM ejemplares WHERE UPPER(TRIM(biblioteca)) = ?
            )
            {self.cond_anio()}
            GROUP BY l.id_sistema, l.titulo, l.autor, l.anio, l.cdu
            HAVING n_bibliotecas > 0
        """
        try:
            filas = self.conn.execute(sql, [biblioteca.upper().strip(), int(anio_minimo)]).fetchall()
        except sqlite3.Error:
            return []
        return [{"id_sistema": utils.clave_id(f[0]), "titulo": utils.sin_entidades(f[1]),
                 "autor": utils.sin_entidades(f[2]), "anio": f[3], "cdu": f[4], "n_bibliotecas": f[5],
                 "todas_signaturas": f[6]} for f in filas]

    def ids_con_materia(self, ids_sistema, busqueda):
        if not self.disponible or not ids_sistema or not self.tabla_existe("materias"):
            return set()
        encontrados = set()
        objetivo = utils.sin_acentos(busqueda.upper())
        sql = "SELECT id_sistema, materia FROM materias WHERE id_sistema IN ({marcas})"
        for id_sistema, materia in self._por_bloques(sql, ids_sistema):
            if materia and objetivo in utils.sin_acentos(materia.upper()):
                encontrados.add(utils.clave_id(id_sistema))
        return encontrados

    def titulos_de(self, ids_sistema):
        """id_sistema -> {titulo, autor, anio}, en bloque. Lo usa la pestaña
        «Red» para rotular la actividad, que solo guarda el id del título."""
        mapa = {}
        if not self.disponible or not ids_sistema:
            return mapa
        sql = "SELECT id_sistema, titulo, autor, anio FROM libros WHERE id_sistema IN ({marcas})"
        for rid, titulo, autor, anio in self._por_bloques(sql, sorted({str(i) for i in ids_sistema if i})):
            mapa[utils.clave_id(rid)] = {"titulo": utils.sin_entidades(titulo),
                                         "autor": utils.sin_entidades(autor), "anio": anio}
        return mapa

    # -- ficha catalográfica -----------------------------------------------
    def ficha(self, id_sistema):
        """Ficha catalográfica desde la base de la red: registro MARC si está
        disponible y, si no, los datos básicos de la tabla `libros`."""
        if not self.disponible:
            return None
        ejemplares = []
        try:
            filas = self.conn.execute(
                "SELECT biblioteca, seccion, signatura, codigo_barras "
                "FROM ejemplares WHERE id_sistema = ?", (str(id_sistema),)).fetchall()
            ejemplares = [{"biblioteca": f[0], "seccion": f[1], "signatura": f[2],
                           "codigo_barras": f[3]} for f in filas]
        except sqlite3.Error:
            pass

        if self.hay_marc:
            try:
                fila = self.conn.execute(
                    "SELECT marcxml FROM marc_completo WHERE id_sistema = ?",
                    (str(id_sistema),)).fetchone()
            except sqlite3.Error:
                fila = None
            if fila and fila[0]:
                ficha = _ficha_desde_marcxml(fila[0])
                ficha["ejemplares"] = ejemplares
                ficha["fuente"] = "marc"
                return ficha

        try:
            fila = self.conn.execute(
                "SELECT titulo, autor, anio, cdu FROM libros WHERE id_sistema = ?",
                (str(id_sistema),)).fetchone()
        except sqlite3.Error:
            fila = None
        if fila:
            return {"titulo": utils.sin_entidades(fila[0]), "autor": utils.sin_entidades(fila[1]),
                    "anio": fila[2], "cdu": fila[3],
                    "materias": [], "ejemplares": ejemplares, "fuente": "basico"}
        return {"titulo": None, "autor": None, "materias": [], "ejemplares": ejemplares,
                "fuente": "ninguno"}


# --- Lectura del MARCXML sin dependencias externas -------------------------
_RE_CAMPO = r'<datafield[^>]*tag="{tag}"[^>]*>(.*?)</datafield>'
_RE_SUBCAMPO = re.compile(r'<subfield[^>]*code="([a-zA-Z0-9])"[^>]*>(.*?)</subfield>', re.S)

CAMPOS_FICHA = {"250": "edicion", "300": "descripcion_fisica", "490": "serie",
                "500": "notas", "505": "contenido", "520": "resumen"}


def _limpiar_xml(texto):
    texto = re.sub(r"<[^>]+>", "", texto or "")
    # Todas las entidades, también las numéricas (&#237;) y las dobles (&amp;#237;)
    texto = utils.sin_entidades(texto) or ""
    return re.sub(r"\s+", " ", texto).strip()


def _campos(xml, tag):
    return re.findall(_RE_CAMPO.format(tag=tag), xml or "", re.S)


def _subcampos(bloque):
    return {code: _limpiar_xml(val) for code, val in _RE_SUBCAMPO.findall(bloque or "")}


def _ficha_desde_marcxml(xml):
    ficha = {"titulo": None, "autor": None, "isbn": None, "cdu": None,
             "editorial": None, "anio": None, "edicion": None, "materias": [],
             "notas": []}

    campos245 = _campos(xml, "245")
    if campos245:
        sub = _subcampos(campos245[0])
        titulo = " ".join(v for k, v in sub.items() if k in ("a", "b") and v)
        ficha["titulo"] = titulo.strip(" /:;,") or None
        if sub.get("c"):
            ficha["mencion_responsabilidad"] = sub["c"]

    for tag in ("100", "110", "700"):
        campos = _campos(xml, tag)
        if campos:
            sub = _subcampos(campos[0])
            if sub.get("a"):
                ficha["autor"] = sub["a"].strip(" .,")
                break

    campos020 = _campos(xml, "020")
    if campos020:
        ficha["isbn"] = _subcampos(campos020[0]).get("a")

    campos080 = _campos(xml, "080")
    if campos080:
        ficha["cdu"] = _subcampos(campos080[0]).get("a")

    for tag in ("260", "264"):
        campos = _campos(xml, tag)
        if campos:
            sub = _subcampos(campos[0])
            ficha["editorial"] = sub.get("b")
            ficha["anio"] = sub.get("c")
            break

    for tag, clave in CAMPOS_FICHA.items():
        valores = [" ".join(v for v in _subcampos(c).values() if v) for c in _campos(xml, tag)]
        valores = [v for v in valores if v]
        if not valores:
            continue
        if clave == "edicion":
            ficha["edicion"] = valores[0]
        else:
            ficha["notas"].append({"etiqueta": clave, "valores": valores})

    for tag in ("650", "651", "600"):
        for campo in _campos(xml, tag):
            sub = _subcampos(campo)
            texto = " -- ".join(v for k, v in sub.items() if k in "axyz" and v)
            if texto:
                ficha["materias"].append(texto)

    return ficha
