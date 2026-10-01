# -*- coding: utf-8 -*-
"""Servidor de Bildumargi.

Publica una API JSON en /api y sirve la interfaz web desde frontend/.
Arráncalo con `python iniciar.py` desde la carpeta del proyecto.
"""

import collections
import hashlib
import hmac
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from backend import absysnet, analisis, basedatos, bibliotecas, clasificacion  # noqa: E402
from backend import valoraciones as mod_valoraciones  # noqa: E402
from backend import preferencias as mod_preferencias  # noqa: E402
from backend import almacen as mod_almacen, configuracion_red as mod_config_red  # noqa: E402
from backend import dilve as mod_dilve, materias as mod_materias, sugerencias as mod_sugerencias  # noqa: E402
from backend import idiomas as mod_idiomas, recomendaciones, utils  # noqa: E402
from backend import thema as mod_thema  # noqa: E402
from backend import afinidad as mod_afinidad  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(RAIZ, "frontend")

app = FastAPI(title="Bildumargi", docs_url=None, redoc_url=None)

# --- Estado global (se prepara una vez al arrancar) ------------------------
# Si los datos van en otra carpeta (BILDUMARGI_DATOS, como en el paquete de
# Linux), se crea y se le copian los ficheros de partida que falten.
if hasattr(config, "preparar_carpeta_datos"):
    config.preparar_carpeta_datos()

BASE = basedatos.BaseRed(config.url_base_datos(), config.RUTA_CACHE)

VALORACIONES = mod_valoraciones.Valoraciones(
    config.RUTA_VALORACIONES, getattr(config, "VALORACIONES_ACTIVAS", True))

ALMACEN = mod_almacen.Almacen(
    getattr(config, "RUTA_BIBLIOTECAS_DATOS", os.path.join(config.RAIZ, "datos", "bibliotecas")))
PREFERENCIAS = mod_preferencias.Preferencias(ALMACEN, getattr(config, "RUTA_PREFERENCIAS", None))
CONFIG_RED = mod_config_red.ConfiguracionRed(
    getattr(config, "RUTA_CONFIG_RED", os.path.join(config.RAIZ, "datos", "configuracion_red.json")))

# ---------------------------------------------------------------------------
# Novedades de DILVE: espejo local, credenciales y tarea de fondo
# ---------------------------------------------------------------------------
RUTA_DILVE = getattr(config, "RUTA_DILVE", os.path.join(config.RAIZ, "datos", "dilve", "novedades.db"))
RUTA_DILVE_CREDENCIALES = getattr(config, "RUTA_DILVE_CREDENCIALES",
                                  os.path.join(config.RAIZ, "datos", "dilve", "credenciales.json"))
# ¿Existía ya la base al arrancar? Es lo que decide si hay que descargarla
# (abrirla la crea vacía, así que hay que mirarlo antes).
DILVE_EXISTIA = os.path.exists(RUTA_DILVE)
DILVE = None            # se abre a demanda, para no crear el fichero sin motivo
FICHAS = None           # caché de fichas de DILVE, común a toda la red
RUTA_DILVE_FICHAS = getattr(config, "RUTA_DILVE_FICHAS",
                            os.path.join(config.RAIZ, "datos", "dilve", "fichas.db"))
TABLAS_MATERIAS = mod_materias.cargar_tabla(getattr(config, "RUTA_MATERIAS", None))
# Encabezados THEMA (opcionales): datos/thema_<idioma>.json|xml|csv, de EDItEUR
ENCABEZADOS_THEMA = mod_thema.Encabezados(getattr(config, "RUTA_DATOS", None))
# Parámetros del modelo de afinidad (opcionales): datos/afinidad.json
PARAMETROS_AFINIDAD = mod_afinidad.cargar_parametros(
    os.path.join(getattr(config, "RUTA_DATOS", ""), "afinidad.json"))
TAREA_DILVE = {"en_curso": False, "fase": None, "progreso": {}, "error": None, "ultimo": None}
_PARAR_DILVE = threading.Event()
_CANDADO_DILVE = threading.Lock()


def base_dilve():
    global DILVE
    if DILVE is None:
        DILVE = mod_dilve.BaseNovedades(RUTA_DILVE)
    return DILVE


def _base_fichas():
    global FICHAS
    if FICHAS is None:
        FICHAS = mod_dilve.BaseNovedades(RUTA_DILVE_FICHAS)
    return FICHAS


class CacheCombinada:
    """Todo lo descargado de DILVE, en un solo sitio: las fichas guardadas
    (datos/dilve/fichas.db) y el espejo de novedades (datos/dilve/novedades.db).
    Antes de pedir una ficha a DILVE se mira en los dos; lo que se pide se
    guarda en fichas.db para toda la red."""

    def __init__(self, fichas, novedades):
        self.base = fichas
        self.novedades = novedades

    def leer_fichas(self, isbns=None):
        encontradas = self.base.leer_fichas(isbns)
        if isbns is not None and self.novedades is not None and self.novedades.conn:
            faltan = [i for i in isbns if i not in encontradas]
            if faltan:
                encontradas.update(self.novedades.leer_fichas(faltan))
        return encontradas

    def sin_ficha(self):
        return self.base.sin_ficha()

    def fichas(self, isbns, cliente=None, progreso=None):
        encontradas = self.leer_fichas(isbns)
        faltan = [i for i in isbns if i not in encontradas]
        if faltan:
            encontradas.update(self.base.fichas(faltan, cliente, progreso))
        return encontradas

    def estadisticas(self):
        return self.base.estadisticas()


def cache_fichas():
    return CacheCombinada(_base_fichas(), base_dilve() if os.path.exists(RUTA_DILVE) else None)


# Freno común a todas las llamadas a DILVE: pausa mínima, máximo diario y
# parada de 24 horas si DILVE deniega el acceso. Los valores los fija la red.
CUOTA_DILVE = None


def cuota_dilve():
    global CUOTA_DILVE
    conf = CONFIG_RED.leer()["dilve"]
    if CUOTA_DILVE is None:
        CUOTA_DILVE = mod_dilve.Cuota(os.path.join(os.path.dirname(RUTA_DILVE), "cuota.json"),
                                      conf.get("max_llamadas_dia", 300), conf.get("pausa_llamadas", 6.0))
    CUOTA_DILVE.maximo_diario = int(conf.get("max_llamadas_dia", 300))
    CUOTA_DILVE.pausa = max(mod_dilve.PAUSA_MINIMA, float(conf.get("pausa_llamadas", 6.0)))
    return CUOTA_DILVE


def credenciales_dilve():
    """Primero las variables de entorno; si no, el fichero que guarda el panel
    de administración. Devuelve (usuario, clave, origen)."""
    usuario = getattr(config, "DILVE_USUARIO", "") or ""
    clave = getattr(config, "DILVE_CLAVE", "") or ""
    if usuario and clave:
        return usuario, clave, "entorno"
    try:
        with open(RUTA_DILVE_CREDENCIALES, encoding="utf-8") as f:
            datos = json.load(f)
        if datos.get("usuario") and datos.get("clave"):
            return datos["usuario"], datos["clave"], "fichero"
    except (OSError, ValueError):
        pass
    return "", "", None


def _huella_credenciales():
    usuario, clave, _ = credenciales_dilve()
    if not (usuario and clave):
        return None
    import hashlib
    return hashlib.sha256(f"{usuario}\n{clave}".encode("utf-8")).hexdigest()[:16]


def cliente_dilve():
    usuario, clave, _ = credenciales_dilve()
    if not (usuario and clave):
        return None
    # La forma de enviar varios ISBN ya averiguada se reutiliza: sin ella, cada
    # tarea gastaba llamadas de prueba.
    forma = (base_dilve().leer("forma_lista") if os.path.exists(RUTA_DILVE) else None) \
        or _base_fichas().leer("forma_lista")
    return mod_dilve.ClienteDILVE(usuario, clave, getattr(config, "DILVE_BASE", mod_dilve.BASE_DAPI),
                                  cuota=cuota_dilve(), forma_lista=forma or None)


def _tarea_dilve(modo):
    """Descarga inicial o actualización, en segundo plano."""
    cliente = cliente_dilve()
    conf = CONFIG_RED.leer()["dilve"]
    base = base_dilve()
    if cliente is None or base.error:
        TAREA_DILVE.update({"en_curso": False, "error": base.error or "Faltan las credenciales de DILVE."})
        return
    TAREA_DILVE.update({"en_curso": True, "error": None, "fase": modo, "progreso": {}})
    _PARAR_DILVE.clear()
    try:
        avance = lambda p: TAREA_DILVE.update({"progreso": p})
        if modo == "inicial":
            resultado = mod_dilve.descargar_inicial(base, cliente,
                                                 conf["meses_novedades"], avance, _PARAR_DILVE)
        else:
            resultado = mod_dilve.actualizar(base, cliente, conf["meses_novedades"],
                                             avance, _PARAR_DILVE)
        TAREA_DILVE["ultimo"] = resultado
    except mod_dilve.ErrorDILVE as exc:
        TAREA_DILVE["error"] = str(exc)
        base.escribir("ultimo_resultado", f"Error: {exc}")
    except Exception as exc:                                    # noqa: BLE001
        TAREA_DILVE["error"] = f"Fallo inesperado: {exc}"
    finally:
        TAREA_DILVE.update({"en_curso": False, "fase": None})


def lanzar_tarea_dilve(modo):
    """Una sola tarea a la vez. Devuelve False si ya había una en marcha."""
    if not _CANDADO_DILVE.acquire(blocking=False):
        return False
    if TAREA_DILVE["en_curso"]:
        _CANDADO_DILVE.release()
        return False

    def envoltorio():
        try:
            _tarea_dilve(modo)
        finally:
            _CANDADO_DILVE.release()

    threading.Thread(target=envoltorio, daemon=True, name=f"dilve-{modo}").start()
    return True


def toca_dilve():
    """Qué corresponde hacer ahora con DILVE: "inicial", "actualizar" o None.

    - Sin base y con descarga automática activada: descarga inicial. Si la
      base ya estaba al arrancar (copiada de otra versión), no se descarga:
      se actualiza cuando toque.
    - Con base: actualización cuando hayan pasado `cada_dias` (7 por defecto).
    """
    conf = CONFIG_RED.leer()["dilve"]
    usuario, clave, _ = credenciales_dilve()
    if not (conf["activo"] and usuario and clave) or TAREA_DILVE["en_curso"]:
        return None
    base = base_dilve()
    if base.error:
        return None
    ultima = base.leer("ultima_sincronizacion")
    if not ultima:
        # Una descarga inicial a medias (parada o cortada) se reanuda sola.
        if conf["descarga_inicial"] and (not DILVE_EXISTIA or base.leer("inicial_hasta")):
            return "inicial"
        return None
    try:
        fecha = datetime.strptime(ultima, mod_dilve.FORMATO_FECHA).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if datetime.now(timezone.utc) - fecha >= timedelta(days=conf["cada_dias"]):
        return "actualizar"
    return None


def _vigilante_dilve():
    """Cada media hora comprueba si toca descargar o actualizar."""
    while True:
        try:
            modo = toca_dilve()
            if modo:
                lanzar_tarea_dilve(modo)
        except Exception:                                        # noqa: BLE001
            pass                                                 # el vigilante nunca tumba el servidor
        time.sleep(1800)


@app.on_event("startup")
def arrancar_vigilante():
    threading.Thread(target=_vigilante_dilve, daemon=True, name="dilve-vigilante").start()


# Accesos de administración abiertos: token -> caducidad. Duran dos horas.
_ADMIN = {}
_ADMIN_DURACION = 2 * 3600

DIRECTORIO = None
ERROR_DIRECTORIO = None
try:
    DIRECTORIO = bibliotecas.Directorio(config.RUTA_BIBLIOTECAS)
except bibliotecas.ErrorDirectorio as exc:
    ERROR_DIRECTORIO = str(exc)


def directorio_al_dia():
    """Vuelve a leer bibliotecas.xlsx si el administrador lo ha cambiado (una
    clave nueva, una biblioteca más), sin reiniciar la aplicación. Si el
    fichero nuevo tiene un error, se sigue con el que había."""
    global DIRECTORIO, ERROR_DIRECTORIO
    if DIRECTORIO is not None and not DIRECTORIO.cambiado():
        return DIRECTORIO
    try:
        DIRECTORIO, ERROR_DIRECTORIO = bibliotecas.Directorio(config.RUTA_BIBLIOTECAS), None
    except bibliotecas.ErrorDirectorio as exc:
        if DIRECTORIO is None:
            ERROR_DIRECTORIO = str(exc)
    return DIRECTORIO


def acceso_con_clave_disponible():
    """El acceso con clave tiene sentido si alguna biblioteca tiene clave y
    se guardan las cargas (es lo que se abre al entrar)."""
    d = directorio_al_dia()
    return bool(d and d.hay_claves and CONFIG_RED.leer()["historial"] and ALMACEN.error is None)


# --- Tabla de signaturas (Configuración) ------------------------------------
def signaturas_de(biblioteca):
    """(tabla en vigor o None, origen): la de la biblioteca si tiene, si no la
    de la red, si no ninguna (clasificación estándar)."""
    propia = ALMACEN.leer_json(biblioteca, "signaturas.json") if biblioteca and ALMACEN.error is None else None
    if isinstance(propia, dict) and propia.get("reglas"):
        try:
            return clasificacion.normalizar_reglas(propia["reglas"]), "biblioteca"
        except ValueError:
            pass
    red = CONFIG_RED.leer().get("signaturas")
    if red:
        return red, "red"
    return None, "defecto"


# --- Sesiones de análisis --------------------------------------------------
class Sesion:
    def __init__(self, registros, fichas, biblioteca, huerfanos):
        self.registros = registros
        self.fichas = fichas
        self.biblioteca = biblioteca
        self.huerfanos = huerfanos
        self.creada = time.time()
        self.tocada = time.time()
        self.indice_fondo = analisis.construir_indice_fondo(registros, fichas)
        self.poblacion = DIRECTORIO.habitantes(biblioteca) if DIRECTORIO else 0
        self.superficie = DIRECTORIO.metros(biblioteca) if DIRECTORIO else None
        # Candidatos de compra ya preparados (lo lento del panel), por
        # combinación de años/texto/opciones. Cambiar de sección, de idioma o
        # de fuente solo filtra esta lista en memoria.
        self.candidatos = {}
        self.perfil_secciones = {}
        self.candado_candidatos = threading.Lock()


SESIONES = {}
_CANDADO = threading.Lock()


def _purgar():
    limite = time.time() - config.MINUTOS_SESION * 60
    with _CANDADO:
        for clave in [k for k, s in SESIONES.items() if s.tocada < limite]:
            SESIONES.pop(clave, None)


def obtener_sesion(token) -> Sesion:
    _purgar()
    sesion = SESIONES.get(token)
    if sesion is None:
        raise HTTPException(status_code=404, detail="sesion_caducada")
    sesion.tocada = time.time()
    return sesion


# ===========================================================================
# API
# ===========================================================================
@app.get("/api/config")
def api_config():
    """Lo que la interfaz necesita saber antes de pintar nada: si hay base de
    datos enlazada (y por tanto si se muestran las recomendaciones de compra),
    cuántas bibliotecas hay en el directorio y cómo se llama la red."""
    estado = BASE.estado()
    return {
        "nombre_red": config.NOMBRE_RED,
        "idioma": config.IDIOMA_POR_DEFECTO,
        "anio_actual": config.ANIO_ACTUAL,
        "autoria": config.AUTORIA,
        "version": config.VERSION,
        "licencia": config.LICENCIA,
        "url_codigo": config.URL_CODIGO_FUENTE,
        # Pesos del orden por afinidad, para explicarlo en la interfaz tal como está
        "pesos_afinidad": PARAMETROS_AFINIDAD["beta"],
        "afinidad_ajustada": os.path.exists(os.path.join(getattr(config, "RUTA_DATOS", ""), "afinidad.json")),
        "base_datos": estado,
        "recomendaciones_activas": estado["disponible"],
        # Nombres de las lenguas en euskera («Castellano» → «Gaztelania»): la
        # interfaz los necesita para rotular idiomas cuando se usa en euskera.
        "nombres_idioma_eu": mod_idiomas.IDIOMAS_LABELS_EU,
        "valoraciones": VALORACIONES.estado(),
        "red": CONFIG_RED.leer(),
        # Hay novedades de DILVE utilizables: módulo activo y credenciales puestas
        # Para las sugerencias basta con tener credenciales (autores) o novedades
        # ya descargadas (novedades): la casilla «activo» solo rige la descarga
        # automática semanal.
        "dilve_activo": bool(CONFIG_RED.leer()["dilve"]["activo"] and credenciales_dilve()[0]),
        "dilve_credenciales": bool(credenciales_dilve()[0]),
        "dilve_novedades": (base_dilve().estadisticas().get("registros") or 0)
                           if os.path.exists(RUTA_DILVE) else 0,
        "admin_disponible": clave_admin_configurada(),
        "acceso_clave": acceso_con_clave_disponible(),
        "signaturas_defecto": clasificacion.reglas_defecto(),
        "directorio": {
            "cargado": DIRECTORIO is not None,
            "bibliotecas": len(DIRECTORIO) if DIRECTORIO else 0,
            "avisos": DIRECTORIO.avisos[:10] if DIRECTORIO else [],
            "error": ERROR_DIRECTORIO,
            "ruta": config.RUTA_BIBLIOTECAS,
        },
    }


def _a_subidos(por_tipo):
    """{tipo: [(nombre, bytes)…]} (como se guardan) → formato de validar_ficheros."""
    primero = lambda tipo: (por_tipo.get(tipo) or [None])[0]
    return {"topo": primero("topografico"), "catalogo": por_tipo.get("catalogo") or None,
            "nunca": primero("no_prestados"), "mas2": primero("mas_prestados")}


def _resumen_carga(registros, sesion, sin_no_prestados, modo_reducido):
    """Indicadores de una carga para la pestaña de seguimiento."""
    total = len(registros)
    prestados = sum(1 for r in registros if r["prestado"])
    anios = [int(r["year"]) for r in registros if r.get("year")]
    recientes = sum(1 for a in anios if a >= config.ANIO_ACTUAL - 4)
    antiguos = sum(1 for a in anios if a < config.ANIO_ACTUAL - 20)
    return {
        "volumenes": total,
        "pct_prestamos": round(prestados / total * 100, 1) if total and not sin_no_prestados else None,
        "anio_medio": round(sum(anios) / len(anios)) if anios else None,
        "pct_recientes": round(recientes / len(anios) * 100, 1) if anios else None,
        "pct_antiguos": round(antiguos / len(anios) * 100, 1) if anios else None,
        "docs_habitante": round(total / sesion.poblacion, 2) if sesion.poblacion else None,
        "secciones": len({r["categoria"] for r in registros}),
        "sin_no_prestados": sin_no_prestados, "modo_reducido": modo_reducido,
    }


def _analizar_subidos(subidos):
    """Todo el análisis a partir de los ficheros. Lo usan la subida normal y
    la reapertura de una carga guardada. Devuelve (respuesta, sesion) o
    (JSONResponse de error, None)."""
    asignados, avisos, errores = absysnet.validar_ficheros(subidos)
    if errores:
        return JSONResponse(status_code=400, content={"errores": errores, "avisos": avisos}), None

    # La biblioteca no se elige a mano: se detecta por el código de sucursal
    # que traen los propios listados, para que no puedan analizarse por error
    # los datos de otro centro.
    directorio = directorio_al_dia()
    textos = [utils.decodificar_bytes(asignados[h])
              for h in ("topo", "nunca", "mas2") if asignados.get(h)]
    sucursal = absysnet.detectar_sucursal(*textos)
    biblioteca = directorio.nombre_de_sucursal(sucursal)
    if biblioteca is None:
        detalle = (f"El código de sucursal detectado ({sucursal}) no figura en el "
                   f"directorio de bibliotecas." if sucursal is not None else
                   "No se ha podido leer el código de sucursal de los listados.")
        return JSONResponse(status_code=400, content={
            "errores": [detalle + " Revisa la columna Sucursal del fichero bibliotecas.xlsx."],
            "avisos": avisos}), None

    registros, huerfanos, fichas = absysnet.procesar_datos(
        asignados.get("topo"), asignados.get("nunca"), asignados.get("mas2"),
        asignados.get("catalogo"), config.ANIO_ACTUAL)
    if registros is None:
        return JSONResponse(status_code=400, content={"errores": [huerfanos], "avisos": avisos}), None
    # Secciones del análisis según la tabla de signaturas de la biblioteca o
    # de la red (Configuración); la estándar se conserva para las compras
    clasificacion.aplicar_reglas(registros, signaturas_de(biblioteca)[0])

    # Identificador del registro en la base de la red (id_sistema), cruzando
    # por código de barras. Sirve para saber con certeza qué títulos de la red
    # ya están en el fondo (no depende de cómo se escriban título y autor) y,
    # si la base trae el MARC, para el idioma, que no viene en los .txt.
    biblioteca_base = None
    if BASE.disponible:
        codigos = sorted({utils.clave_id(r["record_id"]) for r in registros})
        traduccion = BASE.mapa_codbar_a_id(codigos)
        mapa = BASE.idiomas_de(sorted({v for v in traduccion.values() if v})) if BASE.hay_idiomas else {}
        for r in registros:
            id_sistema = traduccion.get(utils.clave_id(r["record_id"]))
            r["idioma"] = mapa.get(id_sistema) or mod_idiomas.IDIOMA_SIN_DATO
            r["id_sistema"] = id_sistema
        biblioteca_base = BASE.biblioteca_de_codigos(codigos)
    else:
        for r in registros:
            r["idioma"] = mod_idiomas.IDIOMA_SIN_DATO
            r["id_sistema"] = None

    token = uuid.uuid4().hex
    with _CANDADO:
        SESIONES[token] = Sesion(registros, fichas, biblioteca, huerfanos)
    sesion = SESIONES[token]
    # Nombre con el que figura en la base de la red (puede no ser idéntico al
    # del directorio): es el que usan las consultas de la base
    sesion.biblioteca_base = biblioteca_base or biblioteca

    return {
        "sesion": token,
        "biblioteca": biblioteca,
        "sucursal": sucursal,
        "avisos": avisos,
        "modo_reducido": not asignados.get("catalogo"),
        # Sin el listado de no prestados, todos los ejemplares cuentan como
        # prestados: la circulación y el uso relativo no serían reales.
        "sin_no_prestados": not asignados.get("nunca"),
        "hay_idiomas": BASE.hay_idiomas,
        "metricas": analisis.metricas_cabecera(registros, sesion.poblacion, sesion.superficie),
        "filtros": analisis.opciones_filtros(registros),
    }, sesion




@app.post("/api/analizar")
async def api_analizar(
    topografico: UploadFile = File(None),
    catalogo: list[UploadFile] = File(None),
    no_prestados: UploadFile = File(None),
    mas_prestados: UploadFile = File(None),
    idioma: str = Form("es"),
):
    if DIRECTORIO is None:
        raise HTTPException(status_code=500, detail=ERROR_DIRECTORIO or "directorio_no_cargado")

    async def leer(f):
        return (f.filename, await f.read()) if f is not None else None

    por_tipo = {
        "topografico": [await leer(topografico)] if topografico else [],
        "catalogo": [await leer(f) for f in catalogo] if catalogo else [],
        "no_prestados": [await leer(no_prestados)] if no_prestados else [],
        "mas_prestados": [await leer(mas_prestados)] if mas_prestados else [],
    }
    if not any(por_tipo.values()):
        raise HTTPException(status_code=400, detail="sin_ficheros")

    respuesta, sesion = _analizar_subidos(_a_subidos(por_tipo))
    if sesion is None:
        return respuesta
    _precargar_sugerencias(respuesta["sesion"])
    _precargar_candidatos(respuesta["sesion"])
    # Historial: si la red lo tiene activo, se guardan los listados de esta
    # carga en la carpeta de la biblioteca, con sus indicadores.
    red = CONFIG_RED.leer()
    respuesta["carga"] = None
    if red["historial"] and ALMACEN.error is None:
        try:
            respuesta["carga"] = ALMACEN.guardar_carga(
                sesion.biblioteca, por_tipo,
                _resumen_carga(sesion.registros, sesion, respuesta["sin_no_prestados"], respuesta["modo_reducido"]),
                red["max_cargas"])
        except OSError as exc:
            respuesta["avisos"] = list(respuesta.get("avisos") or []) + [f"No se ha podido guardar esta carga: {exc}"]
    return respuesta


@app.get("/api/sesion/{token}/idiomas")
def api_idiomas(token: str, ui: str = "es"):
    sesion = obtener_sesion(token)
    if not BASE.hay_idiomas:
        return {"disponible": False}
    datos = analisis.tabla_idiomas(sesion.registros, sesion.poblacion, ui)
    datos["disponible"] = True
    return datos


@app.get("/api/sesion/{token}/buscar")
def api_buscar(token: str, campo: str = "signatura", texto: str = "",
               prestamos: str = "todos", anio_desde: int = None,
               anio_hasta: int = None, publico: str = "todo",
               idioma: str = "__TODOS__", loc: str = "__TODAS__",
               categoria: str = "", anio: int = None,
               ui: str = "es",
               pagina: int = 1, por_pagina: int = 10, orden: str = "", descendente: bool = False,
               ligero: bool = False):
    """Datos del panel de colección.

    Con `ligero` solo se devuelven los agregados (sin filas ni listado completo
    para CSV): es lo que pide el Diagnóstico, que no muestra ejemplares.

    Cada cuadro se calcula sobre la selección SIN su propia dimensión. Es lo
    que permite que al filtrar por euskera el cuadro de idiomas siga
    mostrando los demás: si se calculara sobre la selección final, al elegir
    un valor desaparecerían todos los otros y no habría forma de cambiar de
    idioma sin quitar antes el filtro.
    """
    sesion = obtener_sesion(token)

    comun = dict(campo=campo, texto=texto, prestamos=prestamos,
                 anio_desde=anio_desde, anio_hasta=anio_hasta,
                 publico=publico, idioma=idioma, loc=loc,
                 categoria=categoria or None, anio=anio)

    def seleccionar(**cambios):
        parametros = dict(comun)
        parametros.update(cambios)
        return analisis.buscar(sesion.registros, **parametros)[0]

    seleccion, sin_anio = analisis.buscar(sesion.registros, **comun)

    if orden:
        # Se ordena sobre TODOS los ejemplares, no sobre la página que se ve.
        # Los que no tienen ese dato quedan siempre al final, se ordene hacia
        # arriba o hacia abajo: si no, al ordenar por año descendente lo
        # primero serían los ejemplares sin año.
        con_dato = [r for r in seleccion if r.get(orden) is not None and r.get(orden) != ""]
        sin_dato = [r for r in seleccion if r.get(orden) is None or r.get(orden) == ""]
        def clave(r):
            valor = r.get(orden)
            return (0, valor, "") if isinstance(valor, (int, float)) else (1, 0, str(valor).lower())
        seleccion = sorted(con_dato, key=clave, reverse=descendente) + sin_dato

    total = len(seleccion)
    por_pagina = max(5, min(int(por_pagina), 500))
    paginas = max(1, (total - 1) // por_pagina + 1) if total else 1
    pagina = max(1, min(int(pagina), paginas))
    inicio = (pagina - 1) * por_pagina
    visibles = seleccion[inicio: inicio + por_pagina]

    campos = ("record_id", "signatura_real", "titulo", "autor", "year",
              "categoria", "idioma", "prestamos", "loc")

    # Bases sin la dimensión propia de cada cuadro.
    sin_categoria = seleccionar(categoria=None)
    sin_idioma = seleccionar(idioma="__TODOS__")
    sin_loc = seleccionar(loc="__TODAS__")
    sin_anio_sel = seleccionar(anio=None)

    return {
        "total": total,
        "categorias_lista": analisis.reparto(sin_categoria, lambda r: r["categoria"]),
        "idiomas_lista": analisis.reparto(sin_idioma, lambda r: r.get("idioma") or "Sin determinar"),
        "localizaciones": analisis.reparto(sin_loc, lambda r: r.get("loc") or "Sin dato"),
        "publicos": analisis.reparto(seleccion, lambda r: r["macro_seccion"]),
        "estados_prestamo": analisis.reparto(
            seleccion, lambda r: {0: "nunca", 1: "prestado", 2: "alta"}[r["prestamos"]]),
        "anios": analisis.histograma_anual(sin_anio_sel),
        "pagina": pagina,
        "paginas": paginas,
        "por_pagina": por_pagina,
        "desde": inicio + 1 if total else 0,
        "hasta": min(inicio + por_pagina, total),
        "sin_anio": sin_anio,
        "resumen": analisis.resumen_seleccion(seleccion),
        # En modo ligero, además, el perfil de cada sección (actualidad): lo
        # usa el informe imprimible, que no necesita filas pero sí ese dato.
        "perfil_secciones": analisis.perfil_secciones(sin_categoria, config.ANIO_ACTUAL) if ligero else None,
        "filas": [] if ligero else [{c: r.get(c) for c in campos} for r in visibles],
        "todas": None if ligero or total > 20000 else [{c: r.get(c) for c in campos}
                                                       for r in seleccion],
    }


@app.get("/api/sesion/{token}/ficha/{record_id}")
def api_ficha(token: str, record_id: int):
    """Ficha catalográfica del ejemplar, reconstruida a partir del catálogo
    subido en esta sesión."""
    sesion = obtener_sesion(token)
    fila = next((r for r in sesion.registros if r["record_id"] == record_id), None)
    if fila is None:
        raise HTTPException(status_code=404, detail="registro_no_encontrado")
    ficha = sesion.fichas.get(record_id, {})
    return {
        "titulo": fila["titulo"],
        "autor": ficha.get("autor"),
        "signatura": fila["signatura_real"],
        "categoria": fila["categoria"],
        "anio": fila.get("year"),
        "isbn": ficha.get("isbn"),
        "detalle_isbd": ficha.get("resto_isbd"),
        "materias": ficha.get("materias") or [],
        "idioma": fila.get("idioma"),
        "loc": fila.get("loc"),
        "prestamos": fila.get("prestamos"),
        # Enlace con el catálogo de la red: permite valorar el propio fondo.
        "id_sistema": fila.get("id_sistema"),
        "fuente": "sesion",
    }


# --- Recomendaciones de compra (solo si hay base de datos) -----------------
def _exigir_base():
    if not BASE.disponible:
        raise HTTPException(status_code=409, detail=BASE.error or "sin_base_de_datos")


def _anotar_valoraciones(filas):
    """Añade a cada fila la media y el número de valoraciones de la red."""
    if not filas or not VALORACIONES.disponible:
        return filas
    resumen = VALORACIONES.resumen_de([f.get("id_sistema") for f in filas])
    for fila in filas:
        v = resumen.get(str(fila.get("id_sistema")))
        fila["valoracion_media"] = v["media"] if v else None
        fila["valoracion_n"] = v["n_puntuaciones"] if v else 0
        fila["valoracion_comentarios"] = v["n_comentarios"] if v else 0
    return filas


@app.get("/api/sesion/{token}/recomendaciones/generales")
def api_rec_generales(token: str, limite: int = 50, anio_minimo: int = 2015,
                      idioma: str = "__TODOS__", excluir_fondo: bool = True,
                      solo_bibliografico: bool = True):
    _exigir_base()
    sesion = obtener_sesion(token)
    datos = recomendaciones.generales(
        BASE, _nombre_en_base(sesion), sesion.indice_fondo, limite, anio_minimo,
        None if idioma == "__TODOS__" else idioma, excluir_fondo, solo_bibliografico)
    datos["idiomas_red"] = BASE.idiomas_disponibles()
    _anotar_valoraciones(datos["filas"])
    return datos


MAX_CANDIDATOS_POR_SESION = 6      # combinaciones distintas que se recuerdan


def _nombre_en_base(sesion):
    return getattr(sesion, "biblioteca_base", None) or sesion.biblioteca


def candidatos_sesion(sesion, anio_minimo, texto="", campo="titulo",
                      excluir_fondo=True, solo_bibliografico=True):
    """Candidatos de compra preparados para esta sesión, calculados una sola
    vez por combinación. El candado evita que dos peticiones simultáneas (o la
    precarga y el primer clic) hagan el mismo trabajo a la vez."""
    clave = (int(anio_minimo), (texto or "").strip().lower(), campo, bool(excluir_fondo), bool(solo_bibliografico))
    with sesion.candado_candidatos:
        guardado = sesion.candidatos.get(clave)
        if guardado is None:
            guardado = recomendaciones.preparar_candidatos(
                BASE, _nombre_en_base(sesion), sesion.indice_fondo, anio_minimo, texto, campo,
                excluir_fondo, solo_bibliografico)
            if len(sesion.candidatos) >= MAX_CANDIDATOS_POR_SESION:
                sesion.candidatos.pop(next(iter(sesion.candidatos)))    # el más antiguo
            sesion.candidatos[clave] = guardado
        return guardado


def perfil_secciones_sesion(sesion):
    anio = config.ANIO_ACTUAL
    if anio not in sesion.perfil_secciones:
        sesion.perfil_secciones[anio] = analisis.perfil_secciones(sesion.registros, anio)
    return sesion.perfil_secciones[anio]


def _precargar_candidatos(token):
    """Prepara en segundo plano los candidatos con las opciones por defecto de
    la pestaña (últimos 5 años, sin buscar texto), para que el primer clic en
    «Sugerencias de compra» sea inmediato."""
    if not (BASE and BASE.disponible):
        return
    try:
        sesion = obtener_sesion(token)
    except HTTPException:
        return

    def trabajo():
        try:
            candidatos_sesion(sesion, config.ANIO_ACTUAL - 4)
            perfil_secciones_sesion(sesion)
        except Exception:                                       # noqa: BLE001
            pass                                                # se calculará al primer clic
    threading.Thread(target=trabajo, daemon=True, name="precarga-candidatos").start()


@app.get("/api/sesion/{token}/recomendaciones/panel")
def api_rec_panel(token: str, limite: int = 200, anio_minimo: int = 2015,
                  seccion: str = "", idioma: str = "__TODOS__",
                  campo: str = "titulo", texto: str = "",
                  excluir_fondo: bool = True, solo_bibliografico: bool = True):
    _exigir_base()
    sesion = obtener_sesion(token)
    candidatos = candidatos_sesion(sesion, anio_minimo, texto, campo, excluir_fondo, solo_bibliografico)
    datos = recomendaciones.panel(
        BASE, _nombre_en_base(sesion), sesion.indice_fondo, limite, anio_minimo,
        seccion or None, idioma, texto, campo, excluir_fondo, solo_bibliografico,
        candidatos=candidatos)
    _anotar_valoraciones(datos["filas"])
    datos["idiomas_red"] = BASE.idiomas_disponibles()
    # Demanda y actualidad del fondo propio, sección a sección: el panel las
    # cruza con la oferta de la red para señalar dónde hace más falta comprar.
    datos["propias"] = perfil_secciones_sesion(sesion)
    return datos


@app.get("/api/ficha-red/{id_sistema}")
def api_ficha_red(id_sistema: str):
    _exigir_base()
    ficha = BASE.ficha(id_sistema)
    if ficha is None:
        raise HTTPException(status_code=404, detail="registro_no_encontrado")
    ficha["fuente_red"] = True
    return ficha


# ===========================================================================
# Valoraciones entre bibliotecas
# ===========================================================================
class EntradaValoracion(BaseModel):
    puntuacion: int | None = None
    comentario: str | None = None


@app.get("/api/sesion/{token}/valoraciones/{id_sistema}")
def api_valoraciones(token: str, id_sistema: str):
    """Valoraciones de un título y la de esta biblioteca, si la hay."""
    sesion = obtener_sesion(token)
    datos = VALORACIONES.de_titulo(id_sistema)
    datos["mia"] = VALORACIONES.mia(id_sistema, sesion.biblioteca)
    datos["biblioteca"] = sesion.biblioteca
    datos["disponible"] = VALORACIONES.disponible
    datos["error"] = VALORACIONES.error
    return datos


@app.put("/api/sesion/{token}/valoraciones/{id_sistema}")
def api_guardar_valoracion(token: str, id_sistema: str, entrada: EntradaValoracion):
    """La biblioteca que firma es la detectada en la sesión, no una que se
    envíe desde el navegador: así nadie puede valorar en nombre de otra."""
    sesion = obtener_sesion(token)
    try:
        datos = VALORACIONES.guardar(id_sistema, sesion.biblioteca,
                                     entrada.puntuacion, entrada.comentario)
    except mod_valoraciones.ErrorValoracion as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    datos["mia"] = VALORACIONES.mia(id_sistema, sesion.biblioteca)
    datos["biblioteca"] = sesion.biblioteca
    datos["disponible"] = True
    return datos


@app.delete("/api/sesion/{token}/valoraciones/{id_sistema}")
def api_borrar_valoracion(token: str, id_sistema: str):
    sesion = obtener_sesion(token)
    try:
        datos = VALORACIONES.borrar(id_sistema, sesion.biblioteca)
    except mod_valoraciones.ErrorValoracion as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    datos["mia"] = None
    datos["biblioteca"] = sesion.biblioteca
    datos["disponible"] = True
    return datos


class EntradaRespuesta(BaseModel):
    id_valoracion: int
    texto: str


def _hilo(id_sistema, sesion):
    datos = VALORACIONES.de_titulo(id_sistema)
    datos["mia"] = VALORACIONES.mia(id_sistema, sesion.biblioteca)
    datos["biblioteca"] = sesion.biblioteca
    datos["disponible"] = True
    return datos


@app.post("/api/sesion/{token}/respuestas")
def api_responder(token: str, entrada: EntradaRespuesta):
    """Responder a un comentario. Firma la biblioteca de la sesión."""
    sesion = obtener_sesion(token)
    try:
        id_sistema = VALORACIONES.responder(entrada.id_valoracion, sesion.biblioteca, entrada.texto)
    except mod_valoraciones.ErrorValoracion as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _hilo(id_sistema, sesion)


@app.delete("/api/sesion/{token}/respuestas/{id_respuesta}")
def api_borrar_respuesta(token: str, id_respuesta: int):
    sesion = obtener_sesion(token)
    try:
        id_sistema = VALORACIONES.borrar_respuesta(id_respuesta, sesion.biblioteca)
    except mod_valoraciones.ErrorValoracion as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _hilo(id_sistema, sesion)


@app.get("/api/sesion/{token}/red")
def api_red(token: str, filtro: str = "todo", limite: int = 60):
    """Todo lo que necesita la pestaña «Red»: participación, actividad,
    mejor valorados y más comentados, con título y autor resueltos contra el
    catálogo de la red y marcados si están en el fondo de esta biblioteca."""
    sesion = obtener_sesion(token)
    desde = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
    actividad = VALORACIONES.actividad(limite, sesion.biblioteca, filtro)
    mejores = VALORACIONES.mejor_valorados()
    comentados = VALORACIONES.mas_comentados()
    ids = {f["id_sistema"] for f in actividad + mejores + comentados}
    titulos = BASE.titulos_de(ids) if BASE.disponible else {}
    propios = {r.get("id_sistema") for r in sesion.registros if r.get("id_sistema")}
    for f in actividad + mejores + comentados:
        info = titulos.get(utils.clave_id(f["id_sistema"])) or {}
        f.update({"titulo": info.get("titulo"), "autor": info.get("autor"), "anio": info.get("anio"),
                  "en_fondo": f["id_sistema"] in propios})
    return {
        "biblioteca": sesion.biblioteca,
        "estadisticas": VALORACIONES.estadisticas(desde),
        "bibliotecas_red": len(BASE.bibliotecas_en_base()) if BASE.disponible else 0,
        "respuestas_a_mi": len(VALORACIONES.actividad(500, sesion.biblioteca, "a_mi")),
        "actividad": actividad, "mejor_valorados": mejores, "mas_comentados": comentados,
        "disponible": VALORACIONES.disponible, "error": VALORACIONES.error,
    }


# ===========================================================================
# Administración de la red
# ===========================================================================
class EntradaClave(BaseModel):
    clave: str


def _exigir_admin(token):
    ahora = time.time()
    for t_, caduca in list(_ADMIN.items()):
        if caduca < ahora:
            _ADMIN.pop(t_, None)
    if not token or token not in _ADMIN:
        raise HTTPException(status_code=403, detail="Hace falta entrar con la clave de administración.")


def clave_admin_configurada():
    return bool(getattr(config, "CLAVE_ADMIN", ""))


@app.post("/api/admin/entrar")
def api_admin_entrar(entrada: EntradaClave):
    clave = getattr(config, "CLAVE_ADMIN", "")
    if not clave:
        raise HTTPException(status_code=403, detail=(
            "La administración está desactivada: define CLAVE_ADMIN en config.py "
            "o la variable de entorno BILDUMARGI_CLAVE_ADMIN."))
    if not hmac.compare_digest(entrada.clave.encode("utf-8"), clave.encode("utf-8")):
        time.sleep(1)   # frena los intentos a ciegas
        raise HTTPException(status_code=403, detail="Clave incorrecta.")
    token = uuid.uuid4().hex
    _ADMIN[token] = time.time() + _ADMIN_DURACION
    return {"token": token, "configuracion": CONFIG_RED.leer()}


@app.put("/api/admin/configuracion")
def api_admin_guardar(entrada: dict, x_admin: str = Header(None)):
    _exigir_admin(x_admin)
    try:
        return {"configuracion": CONFIG_RED.guardar(entrada)}
    except mod_config_red.ErrorConfiguracion as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class EntradaCredenciales(BaseModel):
    usuario: str
    clave: str


def _ruta_legible(ruta):
    """Relativa a la carpeta del programa si está dentro (instalación de
    siempre); completa si los datos están en otro sitio."""
    absoluta = os.path.abspath(ruta)
    if absoluta.startswith(os.path.abspath(config.RAIZ) + os.sep):
        return os.path.relpath(absoluta, config.RAIZ)
    return absoluta


def _estado_dilve():
    usuario, _clave, origen = credenciales_dilve()
    base = base_dilve()
    return {
        "configuracion": CONFIG_RED.leer()["dilve"],
        "credenciales": {"hay": bool(usuario), "usuario": usuario, "origen": origen},
        "base": {"ruta": _ruta_legible(RUTA_DILVE), "existia_al_arrancar": DILVE_EXISTIA,
                 **base.estadisticas()},
        "cache": {"ruta": _ruta_legible(RUTA_DILVE_FICHAS),
                  "registros": cache_fichas().estadisticas().get("registros", 0)},
        "cuota": {"hoy": cuota_dilve().usadas_hoy(), "maximo": cuota_dilve().maximo_diario,
                  "pausa": cuota_dilve().pausa, "bloqueo": cuota_dilve().bloqueo(),
                  # Solo si el aviso corresponde a las credenciales que hay ahora
                  "credenciales_erroneas": cuota_dilve().credenciales_erroneas(_huella_credenciales())},
        "tarea": TAREA_DILVE,
    }


@app.get("/api/admin/dilve")
def api_admin_dilve(x_admin: str = Header(None)):
    _exigir_admin(x_admin)
    return _estado_dilve()


@app.post("/api/admin/dilve/credenciales")
def api_admin_dilve_credenciales(entrada: EntradaCredenciales, x_admin: str = Header(None)):
    """Guarda usuario y contraseña de la cuenta DILVE de la red, y comprueba
    que funcionan antes de darlos por buenos."""
    _exigir_admin(x_admin)
    cliente = mod_dilve.ClienteDILVE(entrada.usuario.strip(), entrada.clave,
                                     getattr(config, "DILVE_BASE", mod_dilve.BASE_DAPI),
                                     cuota=cuota_dilve())
    try:
        cliente.comprobar()
    except mod_dilve.ErrorDILVE as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        os.makedirs(os.path.dirname(RUTA_DILVE_CREDENCIALES), exist_ok=True)
        with open(RUTA_DILVE_CREDENCIALES, "w", encoding="utf-8") as f:
            json.dump({"usuario": entrada.usuario.strip(), "clave": entrada.clave}, f)
        os.chmod(RUTA_DILVE_CREDENCIALES, 0o600)   # solo quien ejecuta el servidor
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"No se han podido guardar las credenciales: {exc}")
    return _estado_dilve()


@app.post("/api/admin/dilve/{accion}")
def api_admin_dilve_accion(accion: str, x_admin: str = Header(None)):
    """accion: inicial (último año) · actualizar (desde la última vez) · parar."""
    _exigir_admin(x_admin)
    if accion == "parar":
        _PARAR_DILVE.set()
        return _estado_dilve()
    if accion == "desbloquear":
        cuota_dilve().quitar_bloqueo()
        return _estado_dilve()
    if accion not in ("inicial", "actualizar"):
        raise HTTPException(status_code=404, detail="Acción desconocida.")
    if not cliente_dilve():
        raise HTTPException(status_code=400, detail="Faltan las credenciales de DILVE.")
    if not lanzar_tarea_dilve(accion):
        raise HTTPException(status_code=409, detail="Ya hay una descarga en marcha.")
    return _estado_dilve()


# ===========================================================================
# Sugerencias de compra con DILVE
# ===========================================================================
SUGERENCIAS = {}          # token de sesión -> {estado, resultado} de «autores»
_CANDADO_SUG = threading.Lock()


def _calibracion(sesion, fichas_propias):
    """Traduce la edad que declara la editorial al tramo de esta biblioteca,
    comparando los títulos que ya tiene."""
    pares = []
    por_isbn = {(r.get("isbn") or "").strip(): r for r in sesion.registros if r.get("isbn")}
    for isbn, ficha in fichas_propias.items():
        registro = por_isbn.get(isbn)
        if not registro:
            continue
        edad, _ = mod_materias.edad_declarada(ficha)
        pares.append((edad, mod_materias.seccion_de_signatura(
            registro.get("categoria_estandar") or registro.get("categoria"))))
    return mod_materias.calibrar_tramos(pares)


def _opciones_sugerencias(sesion, calibracion=None, perfil=None, filtros=None):
    red = CONFIG_RED.leer()
    s, d = red["sugerencias"], red["dilve"]
    return {
        # Sin filtro de idioma de red: se descarga y se propone todo, y cada
        # biblioteca filtra en su panel (hay libros sin ese dato en la ficha).
        "idiomas": (filtros or {}).get("idiomas") or [], "solo_papel": d["solo_libros"], "solo_en_venta": True,
        "incluir_sin_idioma": True, "excluir_especiales": s["excluir_especiales"],
        "excluir_texto": s["excluir_texto"], "anios_recientes": s["anios_recientes"],
        "max_por_autor": s["max_por_autor"], "fraccion_nucleo": s["fraccion_nucleo"],
        "sugeridos_editorial": s["sugeridos_editorial"], "tablas": TABLAS_MATERIAS,
        "encabezados_thema": ENCABEZADOS_THEMA,
        "calibracion": calibracion or {}, "perfil": perfil or {}, "filtros": filtros or {},
    }


def _huella_nucleo(sesion, opciones):
    """Identifica el núcleo de préstamo: si no ha cambiado, el resultado
    guardado sigue valiendo y no hace falta volver a calcular nada."""
    nucleo = mod_sugerencias.nucleo_prestamo(sesion.registros, opciones["fraccion_nucleo"])
    isbns = sorted(t["isbn"] for t in nucleo if t.get("isbn"))
    return hashlib.sha1(("|".join(isbns)).encode("utf-8")).hexdigest()[:16], len(nucleo)


def _autores_guardados(sesion, huella):
    """Resultado de una sesión anterior de esta misma biblioteca, si el núcleo
    de préstamo no ha cambiado."""
    guardado = ALMACEN.leer_json(sesion.biblioteca, "sugerencias_autores.json")
    if guardado and guardado.get("huella") == huella:
        # Si quedaban fichas por pedir (tope por cálculo, cuota diaria o un
        # bloqueo), se recalcula para completarlas: lo ya descargado no se
        # vuelve a pedir, solo lo que falta, y siempre dentro de la cuota.
        if (guardado.get("resultado") or {}).get("pendientes"):
            return None
        return guardado
    return None


def _guardar_autores(sesion, datos):
    try:
        ALMACEN.escribir_json(sesion.biblioteca, "sugerencias_autores.json", datos)
    except OSError:
        pass          # sin permisos de escritura se recalcula la próxima vez


def _calcular_autores(token, forzar=False):
    sesion = SESIONES.get(token)
    cliente = cliente_dilve()
    estado = SUGERENCIAS.setdefault(token, {})
    if sesion is None or cliente is None:
        estado.update({"en_curso": False, "error": "Faltan las credenciales de DILVE."})
        return
    estado.update({"en_curso": True, "error": None, "progreso": {}})
    try:
        cache = cache_fichas()
        avance = lambda p: estado.update({"progreso": p})
        propios = [(r.get("isbn") or "").strip() for r in sesion.registros if r.get("isbn")]
        fichas_propias = cache.leer_fichas(propios)
        calibracion = _calibracion(sesion, fichas_propias)
        opciones = _opciones_sugerencias(sesion, calibracion)
        huella, _ = _huella_nucleo(sesion, opciones)
        # Si esta biblioteca ya lo calculó y su núcleo de préstamo no ha
        # cambiado, se reutiliza: ni una llamada a DILVE.
        guardado = None if forzar else _autores_guardados(sesion, huella)
        if guardado:
            estado.update({"resultado": guardado["resultado"], "perfil": guardado.get("perfil", {}),
                           "calibracion": guardado.get("calibracion", {}),
                           "calculado": guardado.get("calculado"), "reutilizado": True})
            return
        estado["reutilizado"] = False
        resultado = mod_sugerencias.autores_mas_prestados(cache, cliente, sesion.registros, opciones, avance)
        if cliente is not None and cliente.forma_lista:
            _base_fichas().escribir("forma_lista", cliente.forma_lista)
        # El perfil de la biblioteca (materias, palabras clave, editoriales) se
        # guarda para ordenar después las novedades por parecido.
        nucleo = mod_sugerencias.nucleo_prestamo(sesion.registros, opciones["fraccion_nucleo"])
        fichas_nucleo = cache.leer_fichas([t["isbn"] for t in nucleo])
        estado["perfil"] = mod_sugerencias.perfil(fichas_nucleo, nucleo)
        estado.pop("modelo_afinidad", None)          # hay fichas nuevas: se rehace al pedirlo
        estado["calibracion"] = calibracion
        estado["resultado"] = resultado
        estado["calculado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _guardar_autores(sesion, {"huella": huella, "resultado": resultado,
                                  "perfil": estado["perfil"], "calibracion": calibracion,
                                  "calculado": estado["calculado"]})
    except mod_dilve.ErrorDILVE as exc:
        estado["error"] = str(exc)
    except Exception as exc:                                   # noqa: BLE001
        estado["error"] = f"Fallo inesperado: {exc}"
    finally:
        estado["en_curso"] = False


def _precargar_sugerencias(token):
    """Deja listas las sugerencias de autores nada más cargar los listados.

    Descarga en segundo plano las fichas que falten (las de los títulos más
    prestados y las de sus obras relacionadas) y guarda el resultado, de modo
    que al abrir la pestaña no haya que esperar ni pedir nada a DILVE."""
    conf = CONFIG_RED.leer()
    if not conf["sugerencias"].get("autores", True) or cliente_dilve() is None:
        return
    estado = SUGERENCIAS.setdefault(token, {})
    if estado.get("en_curso"):
        return
    estado["en_curso"] = True
    threading.Thread(target=_calcular_autores, args=(token, False), daemon=True,
                     name="precarga-autores").start()


@app.get("/api/sesion/{token}/sugerencias/autores")
def api_sugerencias_autores(token: str, recalcular: bool = False, idioma: str = None,
                            seccion: str = None, tramo: str = None, solo_publicados: bool = True):
    """Obras del mismo autor de los títulos más prestados que no están en el
    fondo. La primera vez hay que pedir fichas a DILVE, así que se calcula en
    segundo plano y se consulta el avance."""
    obtener_sesion(token)
    estado = SUGERENCIAS.setdefault(token, {})
    if recalcular or ("resultado" not in estado and not estado.get("en_curso")):
        with _CANDADO_SUG:
            if not estado.get("en_curso"):
                estado["en_curso"] = True
                threading.Thread(target=_calcular_autores, args=(token, bool(recalcular)),
                                 daemon=True, name="sugerencias-autores").start()
    resultado = dict(estado.get("resultado") or {"propuestas": []})
    # Los filtros se aplican aquí, sobre lo ya calculado: cambiarlos es
    # inmediato y no vuelve a pedir nada a DILVE. Los recuentos se calculan
    # antes de filtrar, para que enseñen lo que hay disponible.
    propuestas = resultado.get("propuestas") or []
    # Solo lo ya publicado (fecha de DILVE frente al día de hoy): se aplica
    # antes de contar, para que los desplegables enseñen lo disponible.
    if solo_publicados:
        propuestas = [p for p in propuestas if mod_sugerencias.publicado_a_dia_de_hoy(p.get("fecha"))]
    cuenta = lambda clave: dict(collections.Counter(
        (p.get(clave) or "__SIN__") for p in propuestas).most_common())
    resultado["idiomas"] = cuenta("idioma")
    # Un libro cuenta en su sección y en las que le dan sus otras materias
    resultado["secciones"] = dict(collections.Counter(
        s or "__SIN__" for p in propuestas for s in mod_sugerencias.secciones_de(p)).most_common())
    # Edad: los tramos infantiles y juveniles, «sin edad» y «adultos» (todo lo
    # demás), para poder quedarse solo con el fondo de adultos.
    def franja(p):
        seccion = p.get("seccion") or ""
        if seccion in mod_materias.TRAMOS_VALIDOS:
            return seccion
        if seccion.startswith("Infantil") or seccion in ("IC", "IP", "IT") or seccion.startswith("I "):
            return "__INFANTIL__"
        return "__ADULTOS__"
    resultado["edades"] = dict(collections.Counter(franja(p) for p in propuestas).most_common())
    if idioma:
        propuestas = [p for p in propuestas if (p.get("idioma") or "__SIN__") == idioma]
    if seccion:
        propuestas = [p for p in propuestas if seccion in mod_sugerencias.secciones_de(p)]
    if tramo:
        propuestas = [p for p in propuestas if franja(p) == tramo]
    resultado["propuestas"] = propuestas
    return {"en_curso": estado.get("en_curso", False), "error": estado.get("error"),
            "progreso": estado.get("progreso", {}), "calculado": estado.get("calculado"),
            "reutilizado": estado.get("reutilizado", False),
            "calibracion": estado.get("calibracion", {}), **resultado}


def _fichas_propias(sesion):
    propios = [mod_sugerencias.isbn13(r.get("isbn")) for r in sesion.registros if r.get("isbn")]
    return cache_fichas().leer_fichas([i for i in propios if i])


def _modelo_afinidad(token, sesion):
    """Modelo de afinidad de la sesión. No llama a DILVE: usa el catálogo
    propio y las fichas ya guardadas. Se rehace cuando el cálculo de autores
    trae fichas nuevas."""
    estado = SUGERENCIAS.setdefault(token, {})
    if "modelo_afinidad" not in estado:
        estado["modelo_afinidad"] = mod_afinidad.construir(
            sesion.registros, _fichas_propias(sesion), config.ANIO_ACTUAL, PARAMETROS_AFINIDAD)
    return estado["modelo_afinidad"]


@app.get("/api/sesion/{token}/sugerencias/evaluacion")
def api_sugerencias_evaluacion(token: str, corte: int = None):
    """Prueba retrospectiva: con lo editado antes de `corte` se predice el
    préstamo de lo editado después, y se compara el modelo con el orden
    anterior, con el orden por sección y con el azar."""
    sesion = obtener_sesion(token)
    opciones = _opciones_sugerencias(sesion)
    return mod_afinidad.evaluar(
        sesion.registros, _fichas_propias(sesion), config.ANIO_ACTUAL, corte, PARAMETROS_AFINIDAD,
        perfil_v1=mod_sugerencias.perfil, parecido_v1=mod_sugerencias.parecido,
        nucleo_v1=lambda regs: mod_sugerencias.nucleo_prestamo(regs, opciones["fraccion_nucleo"]))


@app.get("/api/sesion/{token}/sugerencias/novedades")
def api_sugerencias_novedades(token: str, seccion: str = None, idioma: str = None,
                              editorial: str = None, forma: str = None, texto: str = "", thema: str = None,
                              personalizadas: bool = False, ocultar_propios: bool = True,
                              solo_publicados: bool = True, proximos_3_meses: bool = True,
                              pagina: int = 1, por_pagina: int = 48, limite: int = 300):
    sesion = obtener_sesion(token)
    estado = SUGERENCIAS.get(token, {})
    filtros = {"seccion": seccion, "idioma": idioma, "editorial": editorial, "forma": forma,
               "texto": texto, "thema": thema, "personalizadas": personalizadas,
               "ocultar_propios": ocultar_propios,
               "solo_publicados": solo_publicados, "proximos_3_meses": proximos_3_meses}
    opciones = _opciones_sugerencias(sesion, estado.get("calibracion"), estado.get("perfil"), filtros)
    opciones["limite"] = limite
    opciones["pagina"], opciones["por_pagina"] = pagina, max(12, min(200, por_pagina))
    if personalizadas:
        opciones["modelo_afinidad"] = _modelo_afinidad(token, sesion)
    datos = mod_sugerencias.novedades(base_dilve(), sesion.registros, opciones)
    modelo = opciones.get("modelo_afinidad")
    # El modelo solo necesita el catálogo propio
    datos["hay_perfil"] = bool(modelo) if personalizadas else bool(estado.get("perfil"))
    if modelo:
        datos["cobertura_modelo"] = modelo["cobertura"]
    datos["ventana_meses"] = CONFIG_RED.leer()["dilve"]["meses_novedades"]
    return datos


@app.get("/api/thema")
def api_thema(ui: str = "es"):
    """Encabezados THEMA en el idioma de la interfaz (o el más cercano que
    haya), para rotular los códigos de las fichas. Vacío si la red no ha
    dejado la lista de EDItEUR en la carpeta de datos."""
    return {"idioma": ENCABEZADOS_THEMA.idioma_servido(ui), "ficheros": ENCABEZADOS_THEMA.ficheros,
            "nombres": ENCABEZADOS_THEMA.tabla(ui)}


# ===========================================================================
# Acceso con clave: abrir el último análisis guardado sin subir ficheros
# ===========================================================================
class EntradaAcceso(BaseModel):
    biblioteca: str
    clave: str


# Intentos fallidos por (IP, biblioteca escrita): tras 5 en 10 minutos, espera
_FALLOS_ACCESO = {}
_MAX_FALLOS, _VENTANA_FALLOS = 5, 600


@app.post("/api/entrar")
def api_entrar(entrada: EntradaAcceso, request: Request):
    """La biblioteca escribe su nombre y la clave que le ha dado el
    administrador (columna Clave de bibliotecas.xlsx) y se abre su última
    carga guardada, como si acabara de subir los ficheros."""
    directorio = directorio_al_dia()
    if directorio is None:
        raise HTTPException(status_code=500, detail=ERROR_DIRECTORIO or "directorio_no_cargado")
    if not acceso_con_clave_disponible():
        raise HTTPException(status_code=404, detail="acceso_inactivo")
    ip = request.client.host if request.client else "?"
    llave = (ip, bibliotecas.nucleo_nombre(entrada.biblioteca))
    ahora = time.time()
    fallos = [t for t in _FALLOS_ACCESO.get(llave, []) if ahora - t < _VENTANA_FALLOS]
    if len(fallos) >= _MAX_FALLOS:
        raise HTTPException(status_code=429, detail="acceso_intentos")
    nombre = directorio.buscar(entrada.biblioteca)
    esperada = directorio.clave_de(nombre) if nombre else None
    if not (esperada and hmac.compare_digest(entrada.clave.strip().encode("utf-8"), esperada.encode("utf-8"))):
        _FALLOS_ACCESO[llave] = fallos + [ahora]
        time.sleep(0.5)                     # frena los intentos en bucle
        # Mismo mensaje en los dos casos: no se revela qué bibliotecas existen.
        # Los detalles son claves de texto: la interfaz los traduce.
        raise HTTPException(status_code=403, detail="acceso_incorrecto")
    _FALLOS_ACCESO.pop(llave, None)
    cargas = ALMACEN.cargas(nombre)
    if not cargas:
        raise HTTPException(status_code=404, detail="acceso_sin_carga")
    ultima = cargas[0]
    por_tipo = ALMACEN.leer_carga(nombre, ultima["id"])
    if not por_tipo:
        raise HTTPException(status_code=404, detail="acceso_carga_ilegible")
    respuesta, sesion = _analizar_subidos(_a_subidos(por_tipo))
    if sesion is None:
        return respuesta
    if sesion.biblioteca != nombre:          # los listados guardados son de otro centro
        raise HTTPException(status_code=409, detail="acceso_carga_ajena")
    respuesta["carga"] = ultima["id"]
    respuesta["fecha_carga"] = ultima.get("fecha")
    _precargar_sugerencias(respuesta["sesion"])
    _precargar_candidatos(respuesta["sesion"])
    return respuesta


# ===========================================================================
# Historial de cargas (seguimiento)
# ===========================================================================
@app.get("/api/sesion/{token}/historial")
def api_historial(token: str):
    sesion = obtener_sesion(token)
    red = CONFIG_RED.leer()
    return {"activo": red["historial"], "max_cargas": red["max_cargas"],
            "cargas": ALMACEN.cargas(sesion.biblioteca), "error": ALMACEN.error}


@app.post("/api/sesion/{token}/historial/{id_carga}/abrir")
def api_abrir_carga(token: str, id_carga: str):
    """Vuelve a analizar una carga guardada, sin subir de nuevo los ficheros.
    Solo las de la propia biblioteca: la carpeta sale de la sesión."""
    sesion = obtener_sesion(token)
    por_tipo = ALMACEN.leer_carga(sesion.biblioteca, id_carga)
    if not por_tipo:
        raise HTTPException(status_code=404, detail="No se encuentra esa carga.")
    respuesta, nueva = _analizar_subidos(_a_subidos(por_tipo))
    if nueva is None:
        return respuesta
    respuesta["carga"] = id_carga
    _precargar_sugerencias(respuesta["sesion"])
    _precargar_candidatos(respuesta["sesion"])
    return respuesta


@app.delete("/api/sesion/{token}/historial/{id_carga}")
def api_borrar_carga(token: str, id_carga: str):
    sesion = obtener_sesion(token)
    if not ALMACEN.borrar_carga(sesion.biblioteca, id_carga):
        raise HTTPException(status_code=404, detail="No se encuentra esa carga.")
    return {"cargas": ALMACEN.cargas(sesion.biblioteca)}


# ===========================================================================
# Preferencias de la biblioteca
# ===========================================================================
class EntradaSignaturas(BaseModel):
    reglas: Optional[list] = None   # None = volver a la tabla de la red o la estándar


@app.get("/api/sesion/{token}/signaturas")
def api_signaturas(token: str):
    sesion = obtener_sesion(token)
    reglas, origen = signaturas_de(sesion.biblioteca)
    return {"reglas": reglas or clasificacion.reglas_defecto(), "origen": origen,
            "red": CONFIG_RED.leer().get("signaturas"), "guardables": ALMACEN.error is None}


@app.put("/api/sesion/{token}/signaturas")
def api_guardar_signaturas(token: str, entrada: EntradaSignaturas):
    """Guarda la tabla de la biblioteca y reclasifica al momento el fondo de
    la sesión, para que los gráficos la reflejen sin volver a subir nada."""
    sesion = obtener_sesion(token)
    if ALMACEN.error is not None:
        raise HTTPException(status_code=503, detail=ALMACEN.error)
    try:
        reglas = clasificacion.normalizar_reglas(entrada.reglas)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Igual que la de la red (o la estándar): no hace falta guardar una copia
    red = CONFIG_RED.leer().get("signaturas") or clasificacion.reglas_defecto()
    if reglas is not None and reglas == clasificacion.normalizar_reglas(red):
        reglas = None
    ALMACEN.escribir_json(sesion.biblioteca, "signaturas.json", {"reglas": reglas})
    en_vigor, origen = signaturas_de(sesion.biblioteca)
    clasificacion.aplicar_reglas(sesion.registros, en_vigor)
    return {"reglas": en_vigor or clasificacion.reglas_defecto(), "origen": origen,
            "secciones": len({r["categoria"] for r in sesion.registros})}


@app.get("/api/sesion/{token}/preferencias")
def api_preferencias(token: str):
    sesion = obtener_sesion(token)
    return {"biblioteca": sesion.biblioteca, "preferencias": PREFERENCIAS.de(sesion.biblioteca),
            "guardables": PREFERENCIAS.error is None, "error": PREFERENCIAS.error}


@app.put("/api/sesion/{token}/preferencias")
def api_guardar_preferencias(token: str, entrada: dict):
    """Firma la biblioteca de la sesión: nadie cambia la configuración de otra."""
    sesion = obtener_sesion(token)
    try:
        prefs = PREFERENCIAS.guardar(sesion.biblioteca, entrada)
    except mod_preferencias.ErrorPreferencias as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"biblioteca": sesion.biblioteca, "preferencias": prefs, "guardables": True, "error": None}


@app.delete("/api/sesion/{token}")
def api_cerrar(token: str):
    with _CANDADO:
        SESIONES.pop(token, None)
    return {"ok": True}


# ===========================================================================
# Interfaz web
# ===========================================================================
SIN_CACHE = {"Cache-Control": "no-cache, must-revalidate", "Pragma": "no-cache"}


class SinCache:
    """Evita que el navegador sirva una versión antigua de la interfaz.

    Sin esto, al actualizar Bildumargi el navegador sigue ejecutando el
    JavaScript que tenía guardado y la aplicación parece no haber cambiado.
    El coste es nulo: los ficheros se sirven desde el propio ordenador.

    Está escrito como middleware ASGI y no con @app.middleware("http"): ese
    otro envuelve cada petición en una tarea aparte y, al cerrar el servidor
    con Ctrl+C mientras el navegador tiene algo pidiendo, la terminal se llena
    de trazas de cancelación que parecen un error y no lo son."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                cabeceras = list(mensaje.get("headers") or [])
                for clave, valor in SIN_CACHE.items():
                    cabeceras.append((clave.lower().encode("latin-1"), valor.encode("latin-1")))
                mensaje = {**mensaje, "headers": cabeceras}
            await send(mensaje)

        await self.app(scope, receive, enviar)


app.add_middleware(SinCache)


@app.get("/")
def raiz():
    return FileResponse(os.path.join(FRONTEND, "index.html"), headers=SIN_CACHE)


app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
