# -*- coding: utf-8 -*-
"""Novedades del libro español: cliente de la API de DILVE y espejo local.

DILVE (Distribuidor de Información del Libro Español en Venta, de la FGEE) es
la base de datos del libro en venta en España, alimentada por las editoriales.
Su API de llamadas HTTP («DAPI») se usa aquí para dos cosas:

  getRecordStatusX.do   qué ISBN se han dado de alta, modificado o borrado
                        entre dos fechas (formato 2026-08-21T10:25:50Z)
  getRecordsX.do        la ficha completa de hasta 128 ISBN por llamada,
                        en ONIX 3.1

De todo eso, Bildumargi guarda **solo las altas** (novedades) en un espejo
SQLite propio, `datos/dilve/novedades.db`, con los campos que sirven para
sugerir compras: título, autoría, editorial, colección, idioma, materias,
público, fecha, precio, disponibilidad, resumen y la URL de la cubierta.

Las credenciales son las de la cuenta DILVE de la red. El uso para bibliotecas
es gratuito, pero hay que solicitarlo a la FGEE, y sus condiciones de uso
mandan sobre lo que se puede mostrar o redistribuir.
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import requests
from lxml import etree

BASE_DAPI = "https://www.dilve.es/dilve/dilve/"
FORMATO_FECHA = "%Y-%m-%dT%H:%M:%SZ"
MAX_POR_LLAMADA = 128        # tope documentado de getRecordsX
VENTANA_DIAS = 7
DIAS_SIN_FICHA = 60          # cuánto se recuerda que un ISBN no está en DILVE
PAUSA = 6.0                  # segundos entre llamadas: lo que recomienda DILVE
PAUSA_MINIMA = 6.0           # por debajo de esto no se baja, se configure lo que se configure

# Idiomas de referencia de la red (ONIX usa ISO 639-2/B). Ya no filtran la
# descarga: se usan al consultar y al sugerir compras.
IDIOMAS_DEFECTO = ("spa", "baq", "eus", "cat", "glg", "ara")


class ErrorDILVE(Exception):
    pass


class ErrorAcceso(ErrorDILVE):
    """DILVE deniega el acceso (códigos 11xx, como el 1120 «Solicitud
    denegada»). No se reintenta: insistir solo empeora las cosas. Hay que
    escribir a asistencia@dilve.es para que lo restablezcan."""


class ErrorCredenciales(ErrorDILVE):
    """DILVE rechaza el usuario o la contraseña. Insistir con los mismos datos
    puede hacer que DILVE bloquee la cuenta, así que no se vuelve a llamar
    hasta que se cambien (en config.py, en las variables de entorno o en el
    panel de administración)."""


class ErrorCuota(ErrorDILVE):
    """Se ha alcanzado el máximo de llamadas diarias fijado por la red. No es
    un fallo: lo que falte se pedirá al día siguiente."""


class Cuota:
    """Freno común a todas las llamadas a DILVE de esta instalación.

    - Una pausa mínima entre dos llamadas cualesquiera.
    - Un máximo de llamadas por día, que se guarda en un fichero para que un
      reinicio no lo ponga a cero.
    - Si DILVE deniega el acceso (11xx), se deja de llamar durante 24 horas.

    Así ninguna parte de Bildumargi puede lanzar ráfagas de peticiones, que es
    lo que puede hacer que DILVE bloquee la cuenta."""

    def __init__(self, ruta, maximo_diario=300, pausa=PAUSA):
        self.ruta = ruta
        self.maximo_diario = int(maximo_diario)
        self.pausa = max(PAUSA_MINIMA, float(pausa))
        self._candado = __import__("threading").Lock()
        self._ultima = 0.0
        self.estado = self._leer()

    def _leer(self):
        try:
            import json
            with open(self.ruta, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _guardar(self):
        try:
            import json
            os.makedirs(os.path.dirname(os.path.abspath(self.ruta)), exist_ok=True)
            with open(self.ruta, "w", encoding="utf-8") as f:
                json.dump(self.estado, f)
        except OSError:
            pass

    def _hoy(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def bloqueo(self):
        """Mensaje del bloqueo vigente (menos de 24 horas) o None."""
        b = self.estado.get("bloqueo")
        if not b:
            return None
        try:
            desde = datetime.strptime(b["desde"], FORMATO_FECHA).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            return None
        return b if datetime.now(timezone.utc) - desde < timedelta(hours=24) else None

    def registrar_bloqueo(self, mensaje):
        with self._candado:
            self.estado["bloqueo"] = {"desde": _ahora(), "mensaje": mensaje}
            self._guardar()

    def quitar_bloqueo(self):
        with self._candado:
            self.estado.pop("bloqueo", None)
            self._guardar()

    # -- credenciales rechazadas ------------------------------------------
    # Se guarda solo una huella de usuario y contraseña, nunca la contraseña.
    def marcar_credenciales_erroneas(self, huella, mensaje):
        with self._candado:
            self.estado["credenciales_erroneas"] = {"huella": huella, "desde": _ahora(), "mensaje": mensaje}
            self._guardar()

    def credenciales_erroneas(self, huella=None):
        """El aviso de credenciales rechazadas, si sigue vigente para estas
        credenciales. Al cambiar la contraseña cambia la huella y el aviso
        deja de aplicarse solo."""
        c = self.estado.get("credenciales_erroneas")
        if not c:
            return None
        if huella is not None and c.get("huella") != huella:
            return None
        return c

    def olvidar_credenciales_erroneas(self):
        with self._candado:
            self.estado.pop("credenciales_erroneas", None)
            self._guardar()

    def usadas_hoy(self):
        return self.estado.get("llamadas", 0) if self.estado.get("dia") == self._hoy() else 0

    def antes_de_llamar(self, huella=None):
        with self._candado:
            c = self.estado.get("credenciales_erroneas")
            if c and huella is not None and c.get("huella") == huella:
                raise ErrorCredenciales(
                    "DILVE rechazó el usuario o la contraseña el " + c["desde"][:10] + ". "
                    "No se vuelve a llamar hasta que se cambien en config.py (o en las "
                    "variables de entorno) y se reinicie Bildumargi.")
            if c and huella is not None and c.get("huella") != huella:
                # Credenciales nuevas: se da otra oportunidad y se olvida el aviso
                self.estado.pop("credenciales_erroneas", None)
                self._guardar()
            b = self.bloqueo()
            if b:
                raise ErrorAcceso(f"DILVE denegó el acceso el {b['desde'][:10]} ({b['mensaje']}). "
                                  "No se vuelve a llamar hasta pasadas 24 horas o hasta que "
                                  "la administración lo desbloquee.")
            if self.estado.get("dia") != self._hoy():
                self.estado["dia"], self.estado["llamadas"] = self._hoy(), 0
            if self.estado["llamadas"] >= self.maximo_diario:
                raise ErrorCuota(f"Se ha alcanzado el máximo de {self.maximo_diario} llamadas a DILVE de hoy; "
                                 "lo que falte se pedirá mañana.")
            espera = max(PAUSA_MINIMA, self.pausa) - (time.time() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            self._ultima = time.time()
            self.estado["llamadas"] += 1
            self._guardar()


class ErrorNoEncontrado(ErrorDILVE):
    """DILVE 1501 «Record/s not found»: ninguno de los ISBN pedidos existe (la
    editorial lo retiró o corrigió después de darlo de alta). No es un fallo:
    esa ficha simplemente no está."""


def isbn13_valido(isbn):
    """Comprueba el dígito de control: DILVE rechaza los ISBN mal formados."""
    digitos = re.sub(r"[^0-9]", "", str(isbn or ""))
    if len(digitos) != 13:
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digitos[:12]))
    return (10 - total % 10) % 10 == int(digitos[12])


def _ahora():
    return datetime.now(timezone.utc).strftime(FORMATO_FECHA)


def _texto(nodo):
    return (nodo.text or "").strip() if nodo is not None else None


def _local(nodo):
    return etree.QName(nodo).localname


# ===========================================================================
# Cliente de la DAPI
# ===========================================================================
# Formas de pasar varios ISBN a getRecordsX. El manual (DAPI v1.14) admite
# hasta 128 por llamada pero no está claro el separador, y si no es el que
# espera DILVE, la llamada NO da error: devuelve solo la ficha del primero.
# Por eso se prueba con una muestra y se elige la forma que devuelve todas.
FORMAS_LISTA = ("|", ",", ";", " ", "repetido")


def _es_error_de_credenciales(codigo, texto):
    """El usuario o la contraseña no valen. DILVE responde «Incorrect login»
    (el manual deja el código 1101 para la identificación)."""
    t = (texto or "").lower()
    return (codigo == "1101"
            or "incorrect login" in t
            or re.search(r"(invalid|incorrect|wrong|err[oó]ne[ao]|incorrect[ao]).{0,20}"
                         r"(login|user|password|usuario|contrase)", t) is not None)


class ClienteDILVE:
    def __init__(self, usuario, clave, base=BASE_DAPI, tiempo_espera=120, cuota=None, forma_lista=None):
        self.usuario = usuario
        self.clave = clave
        self.base = base if base.endswith("/") else base + "/"
        self.tiempo_espera = tiempo_espera
        self.cuota = cuota
        # Cómo enviar varios ISBN: se averigua una vez y se recuerda entre
        # tareas (antes se volvía a probar en cada una, con llamadas de prueba).
        self.forma_lista = forma_lista
        self.llamadas = 0
        import hashlib
        self.huella = hashlib.sha256(f"{usuario}\n{clave}".encode("utf-8")).hexdigest()[:16]
        self.interrupcion = None    # ErrorAcceso o ErrorCuota que paró la última tanda

    def _llamar(self, endpoint, params):
        """Devuelve el cuerpo de la respuesta o lanza ErrorDILVE.

        Los errores de la DAPI llegan con HTTP 200 y un <error><code>/<text>
        dentro del XML, así que hay que mirar el contenido, no solo el código."""
        datos = [("user", self.usuario), ("password", self.clave)]
        for clave, valor in params:
            datos.append((clave, valor))
        if self.cuota is not None:
            self.cuota.antes_de_llamar(self.huella)    # pausa, máximo diario y bloqueos
        else:
            time.sleep(PAUSA)
        self.llamadas += 1
        try:
            r = requests.get(self.base + endpoint, params=datos, timeout=self.tiempo_espera)
        except requests.RequestException as exc:
            raise ErrorDILVE(f"No se ha podido contactar con DILVE: {exc}")
        if r.status_code != 200:
            raise ErrorDILVE(f"DILVE respondió HTTP {r.status_code} en {endpoint}.")
        cuerpo = r.content
        if b"<error" in cuerpo[:1000].lower():
            codigo = texto = None
            try:
                raiz = etree.fromstring(cuerpo)
                for n in raiz.iter():
                    if _local(n) == "code":
                        codigo = _texto(n)
                    elif _local(n) == "text":
                        texto = _texto(n)
            except etree.XMLSyntaxError:
                pass
            if codigo == "1501" or "not found" in (texto or "").lower():
                raise ErrorNoEncontrado(f"DILVE: registro no encontrado ({codigo})")
            if _es_error_de_credenciales(codigo, texto):
                mensaje = f"{codigo}: {texto}"
                if self.cuota is not None:
                    self.cuota.marcar_credenciales_erroneas(self.huella, mensaje)
                raise ErrorCredenciales(
                    f"DILVE rechaza el usuario o la contraseña ({mensaje}). Revisa la contraseña "
                    "en config.py (o en las variables de entorno) y reinicia Bildumargi. Mientras "
                    "tanto no se vuelve a llamar a DILVE.")
            if (codigo or "").startswith("11"):
                mensaje = f"{codigo}: {texto}"
                if self.cuota is not None:
                    self.cuota.registrar_bloqueo(mensaje)
                raise ErrorAcceso(f"DILVE deniega el acceso ({mensaje}). Hay que escribir a "
                                  "asistencia@dilve.es para que lo restablezcan.")
            raise ErrorDILVE(f"DILVE rechazó la petición ({codigo}): {texto}")
        return cuerpo

    def comprobar(self):
        """Una llamada mínima para validar usuario y contraseña."""
        hasta = datetime.now(timezone.utc)
        desde = hasta - timedelta(minutes=5)
        self.estado_registros(desde.strftime(FORMATO_FECHA), hasta.strftime(FORMATO_FECHA))
        return True

    def estado_registros(self, desde, hasta=None):
        """ISBN nuevos, modificados y borrados entre dos marcas de tiempo.

        Devuelve (dict por estado, marca de tiempo efectiva devuelta por DILVE).
        Esa marca es la que hay que usar como `desde` en la llamada siguiente."""
        params = [("fromDate", desde)]
        if hasta:
            params.append(("toDate", hasta))
        cuerpo = self._llamar("getRecordStatusX.do", params)
        raiz = etree.fromstring(cuerpo)
        salida = {"nuevos": [], "modificados": [], "borrados": []}
        contenedores = {"newRecords": "nuevos", "changedRecords": "modificados",
                        "deletedRecords": "borrados"}
        for nodo in raiz.iter():
            if _local(nodo) != "record":
                continue
            padre = nodo.getparent()
            grupo = contenedores.get(_local(padre) if padre is not None else "")
            if not grupo:
                continue
            for hijo in nodo.iter():
                if _local(hijo) == "id" and _texto(hijo):
                    salida[grupo].append(_texto(hijo))
        hasta_efectivo = None
        for nodo in raiz.iter():
            if _local(nodo) == "toDate":
                hasta_efectivo = _texto(nodo)
        return salida, hasta_efectivo or hasta or _ahora()

    def _params_lista(self, lote, forma):
        if len(lote) == 1 or forma == "uno":
            return [("identifier", lote[0])]
        if forma == "repetido":
            return [("identifier", i) for i in lote]
        return [("identifier", forma.join(lote))]

    def _pedir(self, lote, forma, version):
        params = self._params_lista(lote, forma)
        params += [("metadataformat", "ONIX"), ("version", version), ("encoding", "UTF-8")]
        try:
            return parsear_onix(self._llamar("getRecordsX.do", params))
        except ErrorNoEncontrado:
            return []

    def detectar_forma_lista(self, muestra, version="3.1"):
        """Prueba cada forma de enviar varios ISBN con una muestra y se queda
        con la que devuelve más fichas. Si ninguna devuelve más de una, se
        pedirán de una en una (más lento, pero completo)."""
        muestra = [i for i in muestra if isbn13_valido(i)][:6]
        if len(muestra) < 2:
            return self.forma_lista or "uno"
        mejor, cuantas = "uno", 1
        for forma in FORMAS_LISTA:
            try:
                n = len({p["isbn"] for p in self._pedir(muestra, forma, version)})
            except (ErrorAcceso, ErrorCuota, ErrorCredenciales):
                raise
            except ErrorDILVE:
                n = 0
            if n > cuantas:
                mejor, cuantas = forma, n
            if n >= len(muestra):
                break
        self.forma_lista = mejor
        return mejor

    def fichas(self, isbns, version="3.1"):
        """Fichas ONIX de una lista de ISBN (en lotes de 128).

        Lo que DILVE no devuelve de un lote se da por no disponible: ya NO se
        pide de uno en uno, porque convertía cada lote con ISBN antiguos en
        más de cien llamadas seguidas (probable causa del bloqueo 1120)."""
        self.interrupcion = None
        pendientes = [i for i in isbns if isbn13_valido(i)]
        if not pendientes:
            return []
        productos = []
        try:
            if self.forma_lista is None:
                self.detectar_forma_lista(pendientes, version)
            tam = MAX_POR_LLAMADA if self.forma_lista != "uno" else 1
            for inicio in range(0, len(pendientes), tam):
                lote = pendientes[inicio: inicio + tam]
                try:
                    productos.extend(self._pedir(lote, self.forma_lista, version))
                except (ErrorAcceso, ErrorCuota, ErrorCredenciales):
                    raise
                except ErrorDILVE:
                    continue            # lote fallido: se sigue con el siguiente
        except (ErrorAcceso, ErrorCuota, ErrorCredenciales) as exc:
            # Se para, pero lo recibido hasta aquí se devuelve y se guarda.
            self.interrupcion = exc
        return productos


# ===========================================================================
# ONIX 3.x -> diccionarios
# ===========================================================================
def _primero(nodo, camino):
    """Primer descendiente cuyo nombre local coincide (sin espacios de nombres)."""
    actual = [nodo]
    for paso in camino.split("/"):
        siguiente = []
        for n in actual:
            siguiente.extend(h for h in n if _local(h) == paso)
        if not siguiente:
            return None
        actual = siguiente
    return actual[0]


def _todos(nodo, nombre):
    return [h for h in nodo.iter() if _local(h) == nombre]


def _valor(nodo, camino):
    return _texto(_primero(nodo, camino))


def parsear_onix(xml):
    """Convierte un ONIXMessage en una lista de productos (diccionarios)."""
    raiz = etree.fromstring(xml) if isinstance(xml, (bytes, bytearray)) else xml
    productos = []
    for prod in (n for n in raiz.iter() if _local(n) == "Product"):
        p = _parsear_producto(prod)
        if p:
            productos.append(p)
    return productos


def _parsear_producto(prod):
    isbn = None
    for ident in _todos(prod, "ProductIdentifier"):
        tipo = _valor(ident, "ProductIDType")
        valor = _valor(ident, "IDValue")
        if tipo in ("15", "03") and valor:      # 15 ISBN-13, 03 GTIN-13
            isbn = re.sub(r"[^0-9Xx]", "", valor)
            if tipo == "15":
                break
    if not isbn:
        return None

    desc = _primero(prod, "DescriptiveDetail")
    publi = _primero(prod, "PublishingDetail")
    colat = _primero(prod, "CollateralDetail")

    p = {
        "isbn": isbn,
        "referencia": _valor(prod, "RecordReference"),
        "forma": _valor(desc, "ProductForm") if desc is not None else None,
        # ProductComposition (lista ONIX 2): 00 = producto único; 10/11/20/30/31 = multiobjeto,
        # estuche o pack. Sirve para no recomendar estuches y lotes.
        "composicion": _valor(desc, "ProductComposition") if desc is not None else None,
        "forma_detalle": _valor(desc, "ProductFormDetail") if desc is not None else None,
        "titulo": None, "subtitulo": None, "coleccion": None, "num_coleccion": None,
        "paginas": None, "edicion": None,
        "idioma": None, "idioma_original": None,
        "editorial": None, "sello": None, "estado": None, "fecha_publicacion": None,
        "disponibilidad": None,
        "resumen": None, "cubierta": None,
        "edad_min": None, "edad_max": None,
        "contribuidores": [], "materias": [], "premios": [],
        "relacionados": [],      # [{codigo (lista ONIX 51), isbn}]: 22 = mismo autor, 06 = formato alternativo
        "publico": [],           # códigos de público (lista ONIX 28)
        "idioma_declarado": False,
    }

    if desc is not None:
        for td in _todos(desc, "TitleDetail"):
            tipo = _valor(td, "TitleType")
            elem = _primero(td, "TitleElement")
            if elem is None:
                continue
            nivel = _valor(elem, "TitleElementLevel")
            titulo = _valor(elem, "TitleText") or _valor(elem, "TitleWithoutPrefix")
            if tipo == "01" and nivel in (None, "01"):          # título del producto
                p["titulo"] = titulo
                p["subtitulo"] = _valor(elem, "Subtitle")
        for col in _todos(desc, "Collection"):
            elem = _primero(col, "TitleDetail/TitleElement")
            if elem is not None and not p["coleccion"]:
                p["coleccion"] = _valor(elem, "TitleText") or _valor(elem, "TitleWithoutPrefix")
                p["num_coleccion"] = _valor(elem, "PartNumber")
        for ext in _todos(desc, "Extent"):
            if _valor(ext, "ExtentType") in ("00", "11") and not p["paginas"]:
                valor = _valor(ext, "ExtentValue")
                p["paginas"] = int(valor) if valor and valor.isdigit() else None
        p["edicion"] = _valor(desc, "EditionNumber")
        for lang in _todos(desc, "Language"):
            papel = _valor(lang, "LanguageRole")
            codigo = _valor(lang, "LanguageCode")
            if papel == "01" and not p["idioma"]:
                p["idioma"] = codigo
                p["idioma_declarado"] = bool(codigo)
            elif papel in ("02", "03") and not p["idioma_original"]:
                p["idioma_original"] = codigo
        for c in _todos(desc, "Contributor"):
            nombre = _valor(c, "PersonName") or _valor(c, "CorporateName")
            invertido = _valor(c, "PersonNameInverted")
            if not (nombre or invertido):
                continue
            isni = None
            for ni in _todos(c, "NameIdentifier"):
                if _valor(ni, "NameIDType") == "16":            # 16 = ISNI
                    isni = _valor(ni, "IDValue")
            p["contribuidores"].append({
                "rol": _valor(c, "ContributorRole"), "nombre": nombre,
                "invertido": invertido, "isni": isni,
            })
        for s in _todos(desc, "Subject"):
            codigo = _valor(s, "SubjectCode")
            texto = _valor(s, "SubjectHeadingText")
            if not (codigo or texto):
                continue
            p["materias"].append({
                "esquema": _valor(s, "SubjectSchemeIdentifier"),
                "codigo": codigo, "texto": texto,
                "principal": 1 if _primero(s, "MainSubject") is not None else 0,
            })
        for a in _todos(desc, "AudienceRange"):
            if _valor(a, "AudienceRangeQualifier") != "17":      # 17 = edad de interés
                continue
            precisiones = [_texto(n) for n in a if _local(n) == "AudienceRangePrecision"]
            valores = [_texto(n) for n in a if _local(n) == "AudienceRangeValue"]
            for prec, val in zip(precisiones, valores):
                if not (val or "").isdigit():
                    continue
                if prec in ("03", "01"):                          # desde / exacta
                    p["edad_min"] = int(val)
                if prec in ("04", "01"):                          # hasta / exacta
                    p["edad_max"] = int(val)

    for aud in _todos(prod, "Audience"):
        tipo = _valor(aud, "AudienceCodeType")
        valor = _valor(aud, "AudienceCodeValue")
        if tipo in (None, "01") and valor:
            p["publico"].append(valor)
    for codigo in _todos(prod, "AudienceCode"):         # forma antigua, por si acaso
        if _texto(codigo):
            p["publico"].append(_texto(codigo))

    for rp in _todos(prod, "RelatedProduct"):
        relacion = _valor(rp, "ProductRelationCode")
        isbn_rel = None
        for ident in _todos(rp, "ProductIdentifier"):
            if _valor(ident, "ProductIDType") in ("15", "03"):
                isbn_rel = re.sub(r"[^0-9Xx]", "", _valor(ident, "IDValue") or "")
                break
        if relacion and isbn_rel and isbn_rel != isbn:
            p["relacionados"].append({"codigo": relacion, "isbn": isbn_rel})

    if publi is not None:
        p["editorial"] = _valor(publi, "Publisher/PublisherName") or _valor(publi, "PublisherName")
        p["sello"] = _valor(publi, "Imprint/ImprintName")
        p["estado"] = _valor(publi, "PublishingStatus")
        for fecha in _todos(publi, "PublishingDate"):
            if _valor(fecha, "PublishingDateRole") in ("01", "11") and not p["fecha_publicacion"]:
                p["fecha_publicacion"] = _valor(fecha, "Date")

    if colat is not None:
        for tc in _todos(colat, "TextContent"):
            if _valor(tc, "TextType") in ("03", "02") and not p["resumen"]:   # descripción
                texto = _valor(tc, "Text")
                if texto:
                    p["resumen"] = re.sub(r"<[^>]+>", " ", texto)
                    p["resumen"] = re.sub(r"\s+", " ", p["resumen"]).strip()[:4000]
        for sr in _todos(colat, "SupportingResource"):
            if _valor(sr, "ResourceContentType") != "01":        # 01 = cubierta
                continue
            enlace = _valor(sr, "ResourceVersion/ResourceLink") or _valor(sr, "ResourceLink")
            if enlace and not p["cubierta"]:
                p["cubierta"] = enlace
        for premio in _todos(colat, "Prize"):
            nombre = _valor(premio, "PrizeName")
            if nombre:
                p["premios"].append({"nombre": nombre, "anio": _valor(premio, "PrizeYear"),
                                     "codigo": _valor(premio, "PrizeCode")})

    # De ONIX no se recogen precios: Bildumargi describe y sugiere, no compra.
    for sd in _todos(prod, "SupplyDetail"):
        if not p["disponibilidad"]:
            p["disponibilidad"] = _valor(sd, "ProductAvailability")
    return p


# ===========================================================================
# Espejo local: datos/dilve/novedades.db
# ===========================================================================
ESQUEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS novedades (
    isbn        TEXT PRIMARY KEY,
    referencia  TEXT,
    titulo      TEXT, subtitulo TEXT,
    editorial   TEXT, sello TEXT,
    coleccion   TEXT, num_coleccion TEXT,
    idioma      TEXT, idioma_original TEXT,
    forma       TEXT, forma_detalle TEXT,
    paginas     INTEGER, edicion TEXT,
    estado      TEXT, fecha_publicacion TEXT,
    composicion TEXT, publico TEXT, idioma_declarado INTEGER,
    disponibilidad TEXT,
    edad_min    INTEGER, edad_max INTEGER,
    resumen     TEXT, cubierta TEXT,
    alta_dilve  TEXT,        -- cuándo la vio Bildumargi por primera vez
    actualizado TEXT
);
CREATE INDEX IF NOT EXISTS idx_nov_fecha ON novedades(fecha_publicacion);
CREATE INDEX IF NOT EXISTS idx_nov_idioma ON novedades(idioma);
CREATE INDEX IF NOT EXISTS idx_nov_editorial ON novedades(editorial);
CREATE INDEX IF NOT EXISTS idx_nov_coleccion ON novedades(coleccion);

CREATE TABLE IF NOT EXISTS contribuidores (
    isbn TEXT NOT NULL, rol TEXT, nombre TEXT, invertido TEXT, isni TEXT, normalizado TEXT
);
CREATE INDEX IF NOT EXISTS idx_con_isbn ON contribuidores(isbn);
CREATE INDEX IF NOT EXISTS idx_con_norm ON contribuidores(normalizado);

CREATE TABLE IF NOT EXISTS materias (
    isbn TEXT NOT NULL, esquema TEXT, codigo TEXT, texto TEXT, principal INTEGER
);
CREATE INDEX IF NOT EXISTS idx_mat_isbn ON materias(isbn);
CREATE INDEX IF NOT EXISTS idx_mat_codigo ON materias(esquema, codigo);

CREATE TABLE IF NOT EXISTS relacionados (
    isbn TEXT NOT NULL, codigo TEXT, isbn_rel TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel_isbn ON relacionados(isbn);

CREATE TABLE IF NOT EXISTS premios (
    isbn TEXT NOT NULL, nombre TEXT, anio TEXT, codigo TEXT
);
CREATE INDEX IF NOT EXISTS idx_pre_isbn ON premios(isbn);

-- ISBN que DILVE no reconoce (retirados o corregidos por la editorial).
-- Se anotan para no volver a pedirlos en cada cálculo: sin esto, cada
-- consulta repetía las mismas llamadas fallidas.
CREATE TABLE IF NOT EXISTS sin_ficha (isbn TEXT PRIMARY KEY, fecha TEXT);

-- Clave/valor: última marca de tiempo sincronizada, estado de la descarga…
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT);
"""


def normalizar_nombre(nombre):
    """«Atxaga, Bernardo (1951-)» y «Bernardo Atxaga» → «atxaga bernardo».

    Sirve para casar la autoría de DILVE con la de los listados y la base de
    la red, que llevan la forma de autoridad de la BNE."""
    if not nombre:
        return None
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    texto = re.sub(r"\([^)]*\)", " ", texto)          # fechas y matices
    texto = re.sub(r"[^A-Za-z0-9,]+", " ", texto).strip().lower()
    if "," in texto:
        apellidos, _, nombre_pila = texto.partition(",")
        texto = f"{apellidos.strip()} {nombre_pila.strip()}"
    return re.sub(r"\s+", " ", texto).strip() or None


class BaseNovedades:
    """Espejo de las novedades de DILVE. Siempre en la misma ruta y con el
    mismo nombre, para poder copiarlo de una versión de Bildumargi a otra."""

    def __init__(self, ruta):
        self.ruta = ruta
        self.error = None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
            self.conn = sqlite3.connect(ruta, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.executescript(ESQUEMA)
            self.conn.commit()
        except (OSError, sqlite3.Error) as exc:
            self.conn = None
            self.error = f"No se ha podido abrir {ruta}: {exc}"

    # -- clave/valor -------------------------------------------------------
    def leer(self, clave, defecto=None):
        if not self.conn:
            return defecto
        fila = self.conn.execute("SELECT valor FROM meta WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else defecto

    def escribir(self, clave, valor):
        if not self.conn:
            return
        self.conn.execute("INSERT INTO meta (clave, valor) VALUES (?,?) "
                          "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                          (clave, str(valor)))
        self.conn.commit()

    # -- escritura ---------------------------------------------------------
    def guardar(self, productos):
        """Inserta o actualiza productos. Devuelve cuántos eran nuevos."""
        if not self.conn or not productos:
            return 0
        nuevos = 0
        ahora = _ahora()
        with self.conn:
            for p in productos:
                existe = self.conn.execute("SELECT 1 FROM novedades WHERE isbn = ?", (p["isbn"],)).fetchone()
                if not existe:
                    nuevos += 1
                self.conn.execute("""
                    INSERT INTO novedades (isbn, referencia, titulo, subtitulo, editorial, sello,
                        coleccion, num_coleccion, idioma, idioma_original, forma, forma_detalle,
                        paginas, edicion, estado, fecha_publicacion, composicion, publico,
                        idioma_declarado, disponibilidad,
                        edad_min, edad_max, resumen, cubierta, alta_dilve, actualizado)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(isbn) DO UPDATE SET
                        referencia=excluded.referencia, titulo=excluded.titulo, subtitulo=excluded.subtitulo,
                        editorial=excluded.editorial, sello=excluded.sello, coleccion=excluded.coleccion,
                        num_coleccion=excluded.num_coleccion, idioma=excluded.idioma,
                        idioma_original=excluded.idioma_original, forma=excluded.forma,
                        forma_detalle=excluded.forma_detalle, paginas=excluded.paginas,
                        edicion=excluded.edicion, estado=excluded.estado,
                        fecha_publicacion=excluded.fecha_publicacion,
                        composicion=excluded.composicion, publico=excluded.publico,
                        idioma_declarado=excluded.idioma_declarado, disponibilidad=excluded.disponibilidad,
                        edad_min=excluded.edad_min, edad_max=excluded.edad_max,
                        resumen=excluded.resumen, cubierta=excluded.cubierta,
                        actualizado=excluded.actualizado
                """, (p["isbn"], p["referencia"], p["titulo"], p["subtitulo"], p["editorial"], p["sello"],
                      p["coleccion"], p["num_coleccion"], p["idioma"], p["idioma_original"], p["forma"],
                      p["forma_detalle"], p["paginas"], p["edicion"], p["estado"], p["fecha_publicacion"],
                      p.get("composicion"), ",".join(p.get("publico") or []),
                      1 if p.get("idioma_declarado") else 0, p["disponibilidad"], p["edad_min"], p["edad_max"],
                      p["resumen"], p["cubierta"], ahora, ahora))
                for tabla in ("contribuidores", "materias", "premios", "relacionados"):
                    self.conn.execute(f"DELETE FROM {tabla} WHERE isbn = ?", (p["isbn"],))
                for c in p["contribuidores"]:
                    self.conn.execute(
                        "INSERT INTO contribuidores (isbn, rol, nombre, invertido, isni, normalizado) VALUES (?,?,?,?,?,?)",
                        (p["isbn"], c["rol"], c["nombre"], c["invertido"], c["isni"],
                         normalizar_nombre(c["invertido"] or c["nombre"])))
                for m in p["materias"]:
                    self.conn.execute(
                        "INSERT INTO materias (isbn, esquema, codigo, texto, principal) VALUES (?,?,?,?,?)",
                        (p["isbn"], m["esquema"], m["codigo"], m["texto"], m["principal"]))
                for rel in p.get("relacionados", []):
                    self.conn.execute("INSERT INTO relacionados (isbn, codigo, isbn_rel) VALUES (?,?,?)",
                                      (p["isbn"], rel["codigo"], rel["isbn"]))
                for pr in p["premios"]:
                    self.conn.execute("INSERT INTO premios (isbn, nombre, anio, codigo) VALUES (?,?,?,?)",
                                      (p["isbn"], pr["nombre"], pr["anio"], pr["codigo"]))
        return nuevos

    # -- lectura -----------------------------------------------------------
    def leer_fichas(self, isbns=None):
        """Devuelve las fichas guardadas, en el mismo formato que el lector de
        ONIX (materias, contribuidores, relacionados y premios incluidos)."""
        if not self.conn:
            return {}
        if isbns is not None:
            isbns = [i for i in isbns if i]
            if not isbns:
                return {}
            marcas = ",".join("?" * len(isbns))
            filas = self.conn.execute(f"SELECT * FROM novedades WHERE isbn IN ({marcas})", isbns).fetchall()
        else:
            filas = self.conn.execute("SELECT * FROM novedades").fetchall()
        fichas = {}
        for f in filas:
            ficha = dict(f)
            ficha["idioma_declarado"] = bool(ficha.get("idioma_declarado"))
            ficha["publico"] = (ficha.get("publico") or "").split(",") if ficha.get("publico") else []
            ficha["materias"], ficha["contribuidores"] = [], []
            ficha["relacionados"], ficha["premios"] = [], []
            fichas[ficha["isbn"]] = ficha
        if not fichas:
            return {}
        marcas = ",".join("?" * len(fichas))
        claves = list(fichas)
        for tabla, destino, campos in (
                ("materias", "materias", ("esquema", "codigo", "texto", "principal")),
                ("contribuidores", "contribuidores", ("rol", "nombre", "invertido", "isni", "normalizado")),
                ("relacionados", "relacionados", ("codigo", "isbn_rel")),
                ("premios", "premios", ("nombre", "anio", "codigo"))):
            for fila in self.conn.execute(f"SELECT * FROM {tabla} WHERE isbn IN ({marcas})", claves):
                d = {c: fila[c] for c in campos}
                if tabla == "relacionados":
                    d = {"codigo": d["codigo"], "isbn": d["isbn_rel"]}
                fichas[fila["isbn"]][destino].append(d)
        return fichas

    def todas(self):
        return list(self.leer_fichas().values())

    def sin_ficha(self, dias=DIAS_SIN_FICHA):
        """ISBN que DILVE no reconoció hace poco: no se vuelven a pedir."""
        if not self.conn:
            return set()
        limite = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime(FORMATO_FECHA)
        return {f["isbn"] for f in self.conn.execute(
            "SELECT isbn FROM sin_ficha WHERE fecha >= ?", (limite,))}

    def anotar_sin_ficha(self, isbns):
        if not self.conn or not isbns:
            return
        ahora = _ahora()
        with self.conn:
            self.conn.executemany(
                "INSERT INTO sin_ficha (isbn, fecha) VALUES (?,?) "
                "ON CONFLICT(isbn) DO UPDATE SET fecha = excluded.fecha",
                [(i, ahora) for i in isbns])

    def fichas(self, isbns, cliente=None, progreso=None):
        """Fichas de esos ISBN: primero las guardadas y, solo si falta alguna y
        hay cliente, esas pidiéndolas a DILVE (y guardándolas, para que la
        siguiente biblioteca de la red no las vuelva a pedir).

        Los ISBN que DILVE no reconoce se anotan aparte: si no, cada consulta
        repetiría las mismas llamadas fallidas."""
        isbns = [i for i in isbns if i]
        guardadas = self.leer_fichas(isbns)
        descartados = self.sin_ficha()
        faltan = [i for i in isbns if i not in guardadas and i not in descartados]
        if faltan and cliente is not None:
            for inicio in range(0, len(faltan), MAX_POR_LLAMADA):
                lote = faltan[inicio: inicio + MAX_POR_LLAMADA]
                nuevas = cliente.fichas(lote)
                self.guardar(nuevas)
                recibidos = {p["isbn"] for p in nuevas}
                for p in nuevas:
                    guardadas[p["isbn"]] = p
                if cliente.interrupcion is not None:
                    break               # cuota agotada o acceso denegado: se sigue otro día
                self.anotar_sin_ficha([i for i in lote if i not in recibidos])
                if progreso:
                    progreso({"fase": "fichas", "pedidas": min(inicio + len(lote), len(faltan)),
                              "total": len(faltan)})
        return guardadas

    def estadisticas(self):
        if not self.conn:
            return {"registros": 0, "error": self.error}
        fila = self.conn.execute("""
            SELECT COUNT(*) AS registros, MIN(fecha_publicacion) AS desde,
                   MAX(fecha_publicacion) AS hasta, COUNT(cubierta) AS con_cubierta,
                   COUNT(resumen) AS con_resumen
            FROM novedades""").fetchone()
        idiomas = [dict(f) for f in self.conn.execute(
            "SELECT idioma, COUNT(*) AS n FROM novedades GROUP BY idioma ORDER BY n DESC LIMIT 8")]
        return {**dict(fila), "idiomas": idiomas,
                "ultima_sincronizacion": self.leer("ultima_sincronizacion"),
                "ultimo_resultado": self.leer("ultimo_resultado"),
                "forma_lista": self.leer("forma_lista"), "error": self.error}


# ===========================================================================
# Descarga y actualización
# ===========================================================================
def purgar(base, meses=3):
    """Ventana móvil: se conservan las novedades vistas en los últimos `meses`.

    Así el fichero no crece sin fin y siempre contiene lo reciente, que es lo
    que sirve para sugerir compras."""
    if not base.conn:
        return 0
    corte = (datetime.now(timezone.utc) - timedelta(days=int(meses) * 31)).strftime(FORMATO_FECHA)
    with base.conn:
        viejas = [f["isbn"] for f in base.conn.execute(
            "SELECT isbn FROM novedades WHERE alta_dilve < ?", (corte,))]
        for tabla in ("contribuidores", "materias", "premios", "relacionados"):
            base.conn.execute(f"DELETE FROM {tabla} WHERE isbn IN (SELECT isbn FROM novedades WHERE alta_dilve < ?)",
                              (corte,))
        base.conn.execute("DELETE FROM novedades WHERE alta_dilve < ?", (corte,))
    base.conn.execute("VACUUM")
    return len(viejas)


def descargar_inicial(base, cliente, meses_ventana=3, progreso=None, parar=None):
    """Descarga TODAS las altas (novedades) de la ventana de la red.

    Solo se baja lo que se va a mostrar (tres meses por defecto). Pedir años
    enteros son decenas de miles de fichas que la ventana móvil borraría
    después, y tarda horas.

    No se filtra nada al descargar: los filtros (idioma, sección, formato,
    libros de texto…) se aplican al consultar, para no tener que volver a
    pedir las fichas cuando cambien las reglas.

    Se pide en ventanas de una semana, porque un intervalo largo en una sola
    llamada devuelve cientos de miles de identificadores. De cada ventana se
    toman solo los `newRecords`: las modificaciones de fichas antiguas no son
    novedades."""
    dias = max(7, int(meses_ventana) * 31)
    fin = datetime.now(timezone.utc)
    inicio = fin - timedelta(days=dias)
    total_ventanas = max(1, int((fin - inicio).days / VENTANA_DIAS + 0.999))
    guardados = altas = 0
    ventana = 0
    cursor = inicio
    # Reanudación: si una descarga anterior se paró o se cortó, se sigue desde
    # la última semana completada (lo ya guardado no se repite).
    previo = base.leer("inicial_hasta")
    if previo:
        try:
            reanudar = datetime.strptime(previo, FORMATO_FECHA).replace(tzinfo=timezone.utc)
            if inicio < reanudar < fin:
                ventana = int((reanudar - inicio).days / VENTANA_DIAS)
                cursor = reanudar
        except ValueError:
            pass
    completa = True
    while cursor < fin:
        if parar is not None and parar.is_set():
            completa = False
            break
        siguiente = min(cursor + timedelta(days=VENTANA_DIAS), fin)
        ventana += 1
        estados, _ = cliente.estado_registros(cursor.strftime(FORMATO_FECHA),
                                              siguiente.strftime(FORMATO_FECHA))
        isbns = estados["nuevos"]
        if progreso:
            progreso({"fase": "listando", "ventana": ventana, "ventanas": total_ventanas,
                      "isbn": len(isbns), "guardados": guardados})
        ventana_completa = True
        for inicio_lote in range(0, len(isbns), MAX_POR_LLAMADA):
            if parar is not None and parar.is_set():
                ventana_completa = False
                break
            lote = isbns[inicio_lote: inicio_lote + MAX_POR_LLAMADA]
            productos = cliente.fichas(lote)
            altas += base.guardar(productos)
            guardados += len(productos)
            if progreso:
                progreso({"fase": "fichas", "ventana": ventana, "ventanas": total_ventanas,
                          "isbn": len(isbns), "guardados": guardados, "forma": cliente.forma_lista})
            if cliente.interrupcion is not None:
                ventana_completa = False        # cuota o bloqueo: se reanuda desde esta semana
                break
        if not ventana_completa:
            completa = False
            break
        base.escribir("inicial_hasta", siguiente.strftime(FORMATO_FECHA))
        cursor = siguiente
    if cliente.forma_lista:
        base.escribir("forma_lista", cliente.forma_lista)
    if not completa:
        motivo = f" ({cliente.interrupcion})" if cliente.interrupcion is not None else ""
        base.escribir("ultimo_resultado", f"Descarga inicial parada en la semana {ventana} de "
                                          f"{total_ventanas}: {guardados} novedades en esta tanda. "
                                          f"Al reanudarla seguirá desde ahí.{motivo}")
        if cliente.interrupcion is not None:
            raise cliente.interrupcion
        return {"guardados": guardados, "nuevos": altas, "completa": False}
    base.escribir("ultima_sincronizacion", _ahora())
    base.escribir("inicial_hasta", "")
    borradas = purgar(base, meses_ventana)
    base.escribir("ultimo_resultado", f"Descarga inicial completa: {guardados} novedades guardadas "
                                      f"({altas} nuevas) de los últimos {int(meses_ventana)} meses"
                                      + (f"; {borradas} antiguas retiradas." if borradas else "."))
    return {"guardados": guardados, "nuevos": altas, "completa": True}


def actualizar(base, cliente, meses_ventana=3, progreso=None, parar=None):
    """Trae las altas desde la última sincronización (o los últimos meses si la
    base está vacía) y retira lo que queda fuera de la ventana. Es lo que se
    ejecuta cada semana."""
    ultima = base.leer("ultima_sincronizacion")
    if not ultima:
        return descargar_inicial(base, cliente, meses_ventana, progreso, parar)
    estados, hasta = cliente.estado_registros(ultima)   # toDate vacío: DILVE fija el corte
    isbns = estados["nuevos"]
    guardados = altas = 0
    for inicio in range(0, len(isbns), MAX_POR_LLAMADA):
        if parar is not None and parar.is_set():
            # Sin marcar la fecha: la próxima vez se repite desde el mismo
            # punto (lo ya guardado se sobrescribe, no se duplica).
            base.escribir("ultimo_resultado", f"Actualización parada: {guardados} novedades en esta tanda.")
            return {"guardados": guardados, "nuevos": altas, "revisados": len(isbns), "completa": False}
        lote = isbns[inicio: inicio + MAX_POR_LLAMADA]
        productos = cliente.fichas(lote)
        altas += base.guardar(productos)
        guardados += len(productos)
        if progreso:
            progreso({"fase": "fichas", "isbn": len(isbns), "guardados": guardados, "forma": cliente.forma_lista})
        if cliente.interrupcion is not None:
            # Sin marcar la fecha: la próxima actualización repite desde el
            # mismo punto y lo ya guardado se sobrescribe, no se duplica.
            base.escribir("ultimo_resultado", f"Actualización parada: {guardados} novedades en esta tanda "
                                              f"({cliente.interrupcion}).")
            raise cliente.interrupcion
    if cliente.forma_lista:
        base.escribir("forma_lista", cliente.forma_lista)
    base.escribir("ultima_sincronizacion", hasta)
    borradas = purgar(base, meses_ventana)
    base.escribir("ultimo_resultado", f"Actualización: {guardados} novedades ({altas} nuevas) desde "
                                      f"{ultima}" + (f"; {borradas} fuera de la ventana retiradas." if borradas else "."))
    return {"guardados": guardados, "nuevos": altas, "revisados": len(isbns)}
