# -*- coding: utf-8 -*-
"""Servidor de Bildumargi.

Publica una API JSON en /api y sirve la interfaz web desde frontend/.
Arráncalo con `python iniciar.py` desde la carpeta del proyecto.
"""

import collections
import hashlib
import hmac
import json
import math
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from backend import absysnet, analisis, bibliotecas, clasificacion  # noqa: E402
from backend import almacen as mod_almacen, configuracion as mod_configuracion  # noqa: E402
from backend import dilve as mod_dilve, materias as mod_materias, sugerencias as mod_sugerencias  # noqa: E402
from backend import idiomas as mod_idiomas, utils  # noqa: E402
from backend import thema as mod_thema  # noqa: E402
from backend import afinidad as mod_afinidad  # noqa: E402
from backend import cambios as mod_cambios  # noqa: E402
from backend import series as mod_series  # noqa: E402
from backend import marc as mod_marc  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(RAIZ, "frontend")

app = FastAPI(title="Bildumargi", docs_url=None, redoc_url=None)

# --- Estado global (se prepara una vez al arrancar) ------------------------
# Si los datos van en otra carpeta (BILDUMARGI_DATOS, como en el paquete de
# Linux), se crea y se le copian los ficheros de partida que falten.
if hasattr(config, "preparar_carpeta_datos"):
    config.preparar_carpeta_datos()

ALMACEN = mod_almacen.Almacen(
    getattr(config, "RUTA_BIBLIOTECAS_DATOS", os.path.join(config.RAIZ, "datos", "bibliotecas")))
# Una sola configuración, la de la biblioteca (datos/configuracion.json). Si
# falta, se parte de la configuración de la red de la 1.x.
CONFIG = mod_configuracion.Configuracion(
    config.RUTA_CONFIGURACION, os.path.join(config.RUTA_DATOS, "configuracion_red.json"))

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

    def idiomas_de(self, isbns):
        """{isbn: código de idioma} de todo lo descargado (fichas y novedades)."""
        encontrados = self.base.idiomas_de(isbns)
        if self.novedades is not None and self.novedades.conn:
            faltan = [i for i in isbns if i not in encontrados]
            if faltan:
                encontrados.update(self.novedades.idiomas_de(faltan))
        return encontrados

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
    conf = CONFIG.leer()["dilve"]
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
    conf = CONFIG.leer()["dilve"]
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
                                                 conf["meses_novedades"], avance, _PARAR_DILVE,
                                                 conservar=_conservar_tomos_de_series)
        else:
            resultado = mod_dilve.actualizar(base, cliente, conf["meses_novedades"],
                                             avance, _PARAR_DILVE, conservar=_conservar_tomos_de_series)
        TAREA_DILVE["ultimo"] = resultado
    except mod_dilve.ErrorDILVE as exc:
        TAREA_DILVE["error"] = str(exc)
        base.escribir("ultimo_resultado", f"Error: {exc}")
    except Exception as exc:                                    # noqa: BLE001
        TAREA_DILVE["error"] = f"Fallo inesperado: {exc}"
    finally:
        TAREA_DILVE.update({"en_curso": False, "fase": None})


def _conservar_tomos_de_series(base, isbns):
    """Antes de que una novedad salga de la ventana de meses, si es un tomo
    numerado de una serie de la que hay fichas, pasa a la caché de fichas:
    así, con el tiempo, se van conociendo los tomos de las series aunque
    DILVE no permita pedir una serie entera."""
    fichas = _base_fichas()
    try:
        series = set(json.loads(fichas.leer("series_biblioteca") or "[]"))
    except ValueError:
        series = set()
    if not series:
        return
    candidatas = [f for f in base.leer_fichas(isbns).values()
                  if f.get("coleccion") in series
                  and mod_series.numero_de(f, f.get("coleccion")) is not None]
    if candidatas:
        fichas.guardar(candidatas)


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
    conf = CONFIG.leer()["dilve"]
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

# --- La biblioteca -----------------------------------------------------------
def nombre_red():
    """La red que se ve en la cabecera: la de Configuración o, si no se ha
    escrito nunca, la de config.py."""
    red = biblioteca_actual().get("red")
    return config.NOMBRE_RED if red is None else red


def biblioteca_actual():
    return CONFIG.leer()["biblioteca"]


def carpeta_biblioteca():
    """Carpeta de su historial en datos/bibliotecas/. No cambia aunque se
    cambie el nombre, para no perder las cargas guardadas."""
    return biblioteca_actual().get("carpeta") or "biblioteca"


def _importar_de_la_1x(sucursal):
    """Primera carga tras pasar de la 1.x: si el antiguo directorio de la red
    (bibliotecas.xlsx) tiene esa sucursal, se toman de él nombre, población y
    superficie, y se sigue usando su carpeta (historial, preferencias y tabla
    de signaturas)."""
    try:
        directorio = bibliotecas.Directorio(config.RUTA_BIBLIOTECAS)
        nombre = directorio.nombre_de_sucursal(sucursal)
    except (bibliotecas.ErrorDirectorio, OSError, ValueError):
        return {}
    if not nombre:
        return {}
    datos = {"nombre": nombre, "poblacion": directorio.habitantes(nombre) or None,
             "metros": directorio.metros(nombre), "carpeta": mod_almacen.slug(nombre)}
    # Su configuración propia de la 1.x pasa a ser la configuración
    previas = ALMACEN.leer_json(datos["carpeta"], "preferencias.json") or {}
    cambios = {k: previas[k] for k in ("idioma", "tema", "paleta", "inicio") if previas.get(k)}
    if previas.get("pestanas_ocultas"):
        cambios["pestanas_ocultas"] = [p for p in previas["pestanas_ocultas"] if p in mod_configuracion.PESTANAS]
    tabla = (ALMACEN.leer_json(datos["carpeta"], "signaturas.json") or {}).get("reglas")
    if tabla:
        cambios["signaturas"] = tabla
    if cambios:
        try:
            CONFIG.guardar(cambios)
        except mod_configuracion.ErrorConfiguracion:
            pass
    return datos


def registrar_biblioteca(sucursal):
    """La primera carga apunta la sucursal de los listados. Devuelve los datos
    de la biblioteca y, si los listados son de otra sucursal, la apuntada."""
    b = biblioteca_actual()
    if b.get("sucursal") is None and sucursal is not None:
        datos = {"sucursal": sucursal}
        if not b.get("carpeta"):
            importados = _importar_de_la_1x(sucursal)
            datos.update({k: v for k, v in importados.items() if v is not None and not b.get(k)})
        datos.setdefault("carpeta", b.get("carpeta") or "biblioteca")
        return CONFIG.guardar_biblioteca(**datos)["biblioteca"], None
    if not b.get("carpeta"):
        b = CONFIG.guardar_biblioteca(carpeta="biblioteca")["biblioteca"]
    if sucursal is not None and b.get("sucursal") is not None and str(sucursal) != str(b["sucursal"]):
        return b, b["sucursal"]
    return b, None


def importar_al_arrancar():
    """Al pasar de la 1.x: si el antiguo directorio tiene una sola biblioteca
    con cargas guardadas, es esta. Así su último análisis se puede abrir
    desde el primer momento, sin subir antes los listados."""
    if biblioteca_actual().get("carpeta") or ALMACEN.error is not None:
        return
    try:
        directorio = bibliotecas.Directorio(config.RUTA_BIBLIOTECAS)
    except (bibliotecas.ErrorDirectorio, OSError, ValueError):
        return
    con_cargas = [(suc, nombre) for suc, nombre in directorio.por_sucursal.items()
                  if ALMACEN.cargas(mod_almacen.slug(nombre))]
    if len(con_cargas) == 1:
        registrar_biblioteca(con_cargas[0][0])


def _leer_ini(ruta):
    """El instalador de Windows escribe un .ini (en UTF-16 o en la página de
    códigos de Windows, según el caso)."""
    import configparser
    bruto = open(ruta, "rb").read()
    for codificacion in ("utf-16", "utf-8-sig", "cp1252"):
        if codificacion == "utf-16" and not bruto.startswith((b"\xff\xfe", b"\xfe\xff")):
            continue
        try:
            texto = bruto.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    ini = configparser.ConfigParser(interpolation=None)
    ini.read_string(texto)
    return ini["Bildumargi"] if ini.has_section("Bildumargi") else {}


def aplicar_instalacion():
    """Lo que se escribió en el instalador de Windows (datos/instalacion.ini):
    datos de la biblioteca, cuenta de DILVE y ruta del catálogo MARC. Se
    aplica una vez y el fichero se borra (lleva la contraseña de DILVE, que
    pasa a datos/dilve/credenciales.json, como si se guardara en Configuración)."""
    ruta = os.path.join(config.RUTA_DATOS, "instalacion.ini")
    if not os.path.exists(ruta):
        return
    try:
        datos = _leer_ini(ruta)
        actual = CONFIG.leer()
        biblioteca = {}
        if datos.get("nombre", "").strip() and not actual["biblioteca"].get("nombre"):
            biblioteca["nombre"] = datos["nombre"].strip()
        if datos.get("red", "").strip() and actual["biblioteca"].get("red") is None:
            biblioteca["red"] = datos["red"].strip()
        for campo in ("poblacion", "metros"):
            if datos.get(campo, "").strip() and not actual["biblioteca"].get(campo):
                biblioteca[campo] = datos[campo].strip()
        cambios = {"biblioteca": biblioteca} if biblioteca else {}
        if datos.get("marc", "").strip():
            cambios["marc"] = {"ruta": datos["marc"].strip()}
        usuario, clave = datos.get("dilve_usuario", "").strip(), datos.get("dilve_clave", "")
        if usuario and clave:
            os.makedirs(os.path.dirname(RUTA_DILVE_CREDENCIALES), exist_ok=True)
            with open(RUTA_DILVE_CREDENCIALES, "w", encoding="utf-8") as f:
                json.dump({"usuario": usuario, "clave": clave}, f)
            try:
                os.chmod(RUTA_DILVE_CREDENCIALES, 0o600)
            except OSError:
                pass
            cambios["dilve"] = {"activo": True}            # novedades semanales
        if cambios:
            CONFIG.guardar(cambios)
    except Exception as exc:                                    # noqa: BLE001
        print(f"No se han podido aplicar los datos de la instalación: {exc}")
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass


@app.on_event("startup")
def arrancar_importacion():
    try:
        aplicar_instalacion()
        importar_al_arrancar()
    except Exception:                                            # noqa: BLE001
        pass                                                     # se hará en la primera carga


def _ultima_carga():
    """La última carga guardada, si hay historial."""
    if not CONFIG.leer()["historial"] or ALMACEN.error is not None:
        return None
    cargas = ALMACEN.cargas(carpeta_biblioteca())
    return {"id": cargas[0]["id"], "fecha": cargas[0].get("fecha")} if cargas else None


# --- Tabla de signaturas (Configuración) ------------------------------------
def signaturas_de():
    """(tabla en vigor o None, origen): la de la biblioteca o la estándar."""
    tabla = CONFIG.leer().get("signaturas")
    return (tabla, "biblioteca") if tabla else (None, "defecto")


# --- Sesiones de análisis --------------------------------------------------
class Sesion:
    def __init__(self, registros, fichas, biblioteca, huerfanos):
        self.registros = registros
        self.fichas = fichas
        self.huerfanos = huerfanos
        self.creada = time.time()
        self.tocada = time.time()
        self.perfil_secciones = {}
        self.topo = None             # listado topográfico, para comparar cargas
        self.id_carga = None         # carga guardada que se está viendo, si la hay
        self.cambios = None          # altas y bajas respecto a la carga anterior
        self.cuenta_idiomas = {}
        self.series = None           # series detectadas (se calculan al pedirlas)
        self.poner_biblioteca(biblioteca)

    def poner_biblioteca(self, biblioteca):
        """Nombre, carpeta, población y superficie (cambian al guardar la
        configuración, sin volver a subir nada)."""
        self.biblioteca = biblioteca.get("nombre") or ""
        self.carpeta = biblioteca.get("carpeta") or "biblioteca"
        self.poblacion = biblioteca.get("poblacion") or 0
        self.superficie = biblioteca.get("metros")


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
    """Lo que la interfaz necesita saber antes de pintar nada: la
    configuración, si hay DILVE (y por tanto sugerencias de compra) y si hay
    un análisis guardado que abrir."""
    return {
        "nombre_red": nombre_red(),
        "idioma": config.IDIOMA_POR_DEFECTO,
        "anio_actual": config.ANIO_ACTUAL,
        "autoria": config.AUTORIA,
        "version": config.VERSION,
        "licencia": config.LICENCIA,
        "url_codigo": config.URL_CODIGO_FUENTE,
        # Pesos del orden por afinidad, para explicarlo en la interfaz tal como está
        "pesos_afinidad": PARAMETROS_AFINIDAD["beta"],
        "afinidad_ajustada": os.path.exists(os.path.join(getattr(config, "RUTA_DATOS", ""), "afinidad.json")),
        # Nombres de las lenguas en euskera («Castellano» → «Gaztelania»): la
        # interfaz los necesita para rotular idiomas cuando se usa en euskera.
        "nombres_idioma_eu": mod_idiomas.IDIOMAS_LABELS_EU,
        "configuracion": CONFIG.leer(),
        # Hay novedades de DILVE utilizables: módulo activo y credenciales puestas
        # Para las sugerencias basta con tener credenciales (autores) o novedades
        # ya descargadas (novedades): la casilla «activo» solo rige la descarga
        # automática semanal.
        "dilve_activo": bool(CONFIG.leer()["dilve"]["activo"] and credenciales_dilve()[0]),
        "dilve_credenciales": bool(credenciales_dilve()[0]),
        "dilve_novedades": (base_dilve().estadisticas().get("registros") or 0)
                           if os.path.exists(RUTA_DILVE) else 0,
        # Con CLAVE_ADMIN, la configuración solo se cambia con esa clave
        "clave_configuracion": clave_admin_configurada(),
        "ultima_carga": _ultima_carga(),
        "signaturas_defecto": clasificacion.reglas_defecto(),
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


def hay_idiomas(registros):
    """¿Se conoce el idioma de algún ejemplar? Si no, se ocultan sus filtros."""
    return any(r.get("idioma") not in (None, mod_idiomas.IDIOMA_SIN_DATO) for r in registros)


def _extraer_marc_si_falta(topo, registros):
    ruta = (CONFIG.leer().get("marc") or {}).get("ruta", "")
    if not ruta or os.path.exists(config.RUTA_MARC_IDIOMAS) or not os.path.exists(ruta):
        return
    try:
        codigos = [r["record_id"] for r in absysnet.leer_topografico(topo)] if topo else \
            [r["record_id"] for r in registros]
        autores = {mod_series.autor_normalizado(r.get("autor")) for r in registros if r.get("autor")}
        mod_marc.extraer(ruta, codigos, config.RUTA_MARC_IDIOMAS, autores)
    except (mod_marc.ErrorMarc, OSError) as exc:
        print(f"No se ha podido extraer el idioma del catálogo MARC: {exc}")


def asignar_idiomas(registros):
    """Idioma de cada ejemplar. La cuenta dice también cuántos ISBN quedan
    por pedir a DILVE (si no queda ninguno, no tiene sentido ofrecerlo)."""
    isbns = sorted({r["isbn"] for r in registros if r.get("isbn")})
    try:
        cache = cache_fichas()
        mapa = cache.idiomas_de(isbns) if isbns else {}
        sin = cache.sin_ficha()
    except Exception:                                           # noqa: BLE001
        mapa, sin = {}, set()                                   # sin caché de DILVE: solo la signatura
    marc = mod_marc.idiomas_de(config.RUTA_MARC_IDIOMAS, [r["record_id"] for r in registros])
    cuenta = mod_idiomas.asignar_idiomas(registros, mapa, marc)
    cuenta["por_pedir"] = sum(1 for i in isbns if mod_dilve.isbn13_valido(i) and i not in mapa and i not in sin)
    return cuenta


# --- Altas y bajas respecto a la carga anterior ------------------------------
def _carga_anterior(sesion):
    """La carga guardada justo antes de la que se ve (o la última guardada,
    si lo que se ve aún no se ha guardado)."""
    if ALMACEN.error is not None:
        return None
    cargas = ALMACEN.cargas(sesion.carpeta)
    if sesion.id_carga:
        cargas = [c for c in cargas if c["id"] < sesion.id_carga]
    return cargas[0] if cargas else None


def _topografico_de_carga(carpeta, id_carga):
    ficheros = (ALMACEN.leer_carga(carpeta, id_carga) or {}).get("topografico") or []
    return ficheros[0][1] if ficheros else None


def cambios_sesion(sesion):
    """Altas y bajas de la carga que se ve respecto a la anterior (None si
    no hay anterior). Se calcula una vez por sesión."""
    if sesion.cambios is None:
        anterior = _carga_anterior(sesion)
        topo_anterior = _topografico_de_carga(sesion.carpeta, anterior["id"]) if anterior else None
        if anterior and topo_anterior and sesion.topo:
            c = mod_cambios.comparar(topo_anterior, sesion.topo, signaturas_de()[0])
            c["anterior"] = {"id": anterior["id"], "fecha": anterior.get("fecha")}
            sesion.cambios = c
        else:
            sesion.cambios = {}
    return sesion.cambios or None


def _resumen_cambios(c):
    return {"altas": c["altas"], "bajas": c["bajas"], "anterior": c["anterior"]} if c else None


def _completar_cambios(carpeta, cargas):
    """Altas y bajas de las cargas guardadas antes de que Bildumargi las
    calculara: se calculan una vez y se apuntan en su resumen."""
    for actual, anterior in zip(cargas, cargas[1:]):
        if "altas" in actual:
            continue
        topo_actual = _topografico_de_carga(carpeta, actual["id"])
        topo_anterior = _topografico_de_carga(carpeta, anterior["id"])
        if not (topo_actual and topo_anterior):
            continue
        c = mod_cambios.comparar(topo_anterior, topo_actual)
        datos = {"altas": c["altas"], "bajas": c["bajas"], "anterior": anterior["id"]}
        actual.update(datos)
        try:
            ALMACEN.actualizar_resumen(carpeta, actual["id"], datos)
        except OSError:
            pass


def _analizar_subidos(subidos):
    """Todo el análisis a partir de los ficheros. Lo usan la subida normal y
    la reapertura de una carga guardada. Devuelve (respuesta, sesion) o
    (JSONResponse de error, None)."""
    asignados, avisos, errores = absysnet.validar_ficheros(subidos)
    if errores:
        return JSONResponse(status_code=400, content={"errores": errores, "avisos": avisos}), None

    # La primera carga apunta el código de sucursal de los listados; si un día
    # llegan los de otra sucursal, se avisa y no se mezclan en el historial.
    textos = [utils.decodificar_bytes(asignados[h])
              for h in ("topo", "nunca", "mas2") if asignados.get(h)]
    sucursal = absysnet.detectar_sucursal(*textos)
    biblioteca, sucursal_apuntada = registrar_biblioteca(sucursal)
    if sucursal_apuntada is not None:
        avisos = list(avisos or []) + [
            f"Estos listados son de la sucursal {sucursal}, pero Bildumargi tiene apuntada la "
            f"{sucursal_apuntada}. Se analizan igual, pero no se guardan en el historial, para no "
            f"mezclar dos bibliotecas. Si has cambiado de biblioteca, pulsa «Olvidar la sucursal» "
            f"en Configuración y vuelve a cargarlos."]

    registros, huerfanos, fichas = absysnet.procesar_datos(
        asignados.get("topo"), asignados.get("nunca"), asignados.get("mas2"),
        asignados.get("catalogo"), config.ANIO_ACTUAL)
    if registros is None:
        return JSONResponse(status_code=400, content={"errores": [huerfanos], "avisos": avisos}), None
    # Secciones del análisis según la tabla de signaturas de la biblioteca o
    # de la red (Configuración); la estándar se conserva para las compras
    clasificacion.aplicar_reglas(registros, signaturas_de()[0])

    # El idioma no viene en los listados de AbsysNet: sale del catálogo MARC
    # extraído, de las fichas de DILVE ya descargadas o de la signatura (sin
    # llamar a DILVE). Si hay ruta del MARC y aún no se ha extraído (recién
    # instalado), se extrae ahora, una vez.
    _extraer_marc_si_falta(asignados.get("topo"), registros)
    cuenta_idiomas = asignar_idiomas(registros)

    token = uuid.uuid4().hex
    with _CANDADO:
        SESIONES[token] = Sesion(registros, fichas, biblioteca, huerfanos)
    sesion = SESIONES[token]
    sesion.topo = asignados.get("topo")
    sesion.cuenta_idiomas = cuenta_idiomas

    return {
        "sesion": token,
        "biblioteca": sesion.biblioteca,
        "sucursal": sucursal,
        "sucursal_distinta": sucursal_apuntada is not None,
        "falta_poblacion": not sesion.poblacion,
        "avisos": avisos,
        "modo_reducido": not asignados.get("catalogo"),
        # Sin el listado de no prestados, todos los ejemplares cuentan como
        # prestados: la circulación y el uso relativo no serían reales.
        "sin_no_prestados": not asignados.get("nunca"),
        "hay_idiomas": hay_idiomas(registros),
        "idiomas": cuenta_idiomas,
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
    # Historial: si está activo, se guardan los listados de esta carga en la
    # carpeta de la biblioteca, con sus indicadores.
    red = CONFIG.leer()
    respuesta["carga"] = None
    cambios = None if respuesta["sucursal_distinta"] else cambios_sesion(sesion)
    respuesta["cambios"] = _resumen_cambios(cambios)
    if red["historial"] and ALMACEN.error is None and not respuesta["sucursal_distinta"]:
        resumen = _resumen_carga(sesion.registros, sesion, respuesta["sin_no_prestados"], respuesta["modo_reducido"])
        if cambios:
            resumen.update({"altas": cambios["altas"], "bajas": cambios["bajas"],
                            "anterior": cambios["anterior"]["id"]})
        try:
            respuesta["carga"] = ALMACEN.guardar_carga(sesion.carpeta, por_tipo, resumen, red["max_cargas"])
            sesion.id_carga = respuesta["carga"]
        except OSError as exc:
            respuesta["avisos"] = list(respuesta.get("avisos") or []) + [f"No se ha podido guardar esta carga: {exc}"]
    return respuesta


@app.get("/api/sesion/{token}/idiomas")
def api_idiomas(token: str, ui: str = "es"):
    sesion = obtener_sesion(token)
    if not hay_idiomas(sesion.registros):
        return {"disponible": False}
    datos = analisis.tabla_idiomas(sesion.registros, sesion.poblacion, ui)
    datos["disponible"] = True
    return datos


@app.get("/api/sesion/{token}/metricas")
def api_metricas(token: str):
    """Indicadores de cabecera de nuevo, tras cambiar población o superficie
    en la configuración."""
    sesion = obtener_sesion(token)
    return {"biblioteca": sesion.biblioteca, "falta_poblacion": not sesion.poblacion,
            "hay_idiomas": hay_idiomas(sesion.registros), "idiomas": sesion.cuenta_idiomas,
            "metricas": analisis.metricas_cabecera(sesion.registros, sesion.poblacion, sesion.superficie)}


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
        "idioma_origen": fila.get("idioma_origen"),
        "loc": fila.get("loc"),
        "prestamos": fila.get("prestamos"),
        "fuente": "sesion",
    }


# --- Sugerencias de compra: perfil del fondo propio --------------------------
def perfil_secciones_sesion(sesion):
    anio = config.ANIO_ACTUAL
    if anio not in sesion.perfil_secciones:
        sesion.perfil_secciones[anio] = analisis.perfil_secciones(sesion.registros, anio)
    return sesion.perfil_secciones[anio]


@app.get("/api/sesion/{token}/compras/panel")
def api_compras_panel(token: str):
    """Demanda y actualidad del fondo propio, sección a sección: con ellas el
    panel de sugerencias señala dónde hace más falta comprar."""
    sesion = obtener_sesion(token)
    return {"propias": perfil_secciones_sesion(sesion)}


# ===========================================================================
# Configuración. Si hay CLAVE_ADMIN (config_local.py o BILDUMARGI_CLAVE_ADMIN),
# solo se cambia con esa clave; si no, la cambia cualquiera que use Bildumargi.
# ===========================================================================
class EntradaClave(BaseModel):
    clave: str


def _exigir_admin(token):
    if not clave_admin_configurada():
        return
    ahora = time.time()
    for t_, caduca in list(_ADMIN.items()):
        if caduca < ahora:
            _ADMIN.pop(t_, None)
    if not token or token not in _ADMIN:
        raise HTTPException(status_code=403, detail="Hace falta la clave de configuración.")


def clave_admin_configurada():
    return bool(getattr(config, "CLAVE_ADMIN", ""))


@app.post("/api/admin/entrar")
def api_admin_entrar(entrada: EntradaClave):
    clave = getattr(config, "CLAVE_ADMIN", "")
    if not clave:
        raise HTTPException(status_code=403, detail="La configuración no tiene clave.")
    if not hmac.compare_digest(entrada.clave.encode("utf-8"), clave.encode("utf-8")):
        time.sleep(1)   # frena los intentos a ciegas
        raise HTTPException(status_code=403, detail="Clave incorrecta.")
    token = uuid.uuid4().hex
    _ADMIN[token] = time.time() + _ADMIN_DURACION
    return {"token": token, "configuracion": CONFIG.leer()}


@app.put("/api/configuracion")
def api_guardar_configuracion(entrada: dict, x_admin: str = Header(None)):
    """Guarda la configuración y la aplica al momento a los análisis abiertos:
    datos de la biblioteca y, si cambia, la tabla de signaturas."""
    _exigir_admin(x_admin)
    antes = CONFIG.leer()
    try:
        if (entrada.get("biblioteca") or {}).get("olvidar_sucursal"):
            CONFIG.guardar_biblioteca(sucursal=None)
        conf = CONFIG.guardar(entrada)
    except mod_configuracion.ErrorConfiguracion as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    with _CANDADO:
        sesiones = list(SESIONES.values())
    for sesion in sesiones:
        sesion.poner_biblioteca(conf["biblioteca"])
        if conf.get("series_ocultas") != antes.get("series_ocultas"):
            sesion.series = None
        if conf["signaturas"] != antes["signaturas"]:
            clasificacion.aplicar_reglas(sesion.registros, signaturas_de()[0])
            sesion.perfil_secciones = {}
            sesion.cambios = None
    return {"configuracion": conf, "ultima_carga": _ultima_carga(), "nombre_red": nombre_red()}


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
        "configuracion": CONFIG.leer()["dilve"],
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
# Fichas de DILVE de todo el catálogo (idioma de cada ejemplar y modelo de
# afinidad). Solo se lanza a mano, después de ver cuántas llamadas supone.
# ===========================================================================
TAREA_CATALOGO = {"en_curso": False, "progreso": {}, "error": None, "parada": False, "resultado": None,
                  "tipo": None}     # «catalogo» o «series»: una sola descarga de DILVE a la vez
_PARAR_CATALOGO = threading.Event()
_CANDADO_CATALOGO = threading.Lock()


def _isbns_catalogo(sesion):
    return sorted({r["isbn"] for r in sesion.registros
                   if r.get("isbn") and mod_dilve.isbn13_valido(r["isbn"])})


def _pendientes_catalogo(sesion):
    """(ISBN del catálogo, ya descargados, que DILVE no tiene, por pedir, por
    volver a leer). Se vuelven a leer las fichas guardadas antes de que se
    leyera el número de tomo de las series."""
    isbns = _isbns_catalogo(sesion)
    cache = cache_fichas()
    tienen = set(cache.idiomas_de(isbns))
    sin = (cache.sin_ficha() & set(isbns)) - tienen
    releer = sorted(_base_fichas().por_releer(isbns))
    return isbns, tienen, sin, [i for i in isbns if i not in tienen and i not in sin], releer


def estimar_catalogo(sesion):
    isbns, tienen, sin, pendientes, releer = _pendientes_catalogo(sesion)
    cuota = cuota_dilve()
    llamadas = (math.ceil(len(pendientes) / mod_dilve.MAX_POR_LLAMADA)
                + math.ceil(len(releer) / mod_dilve.MAX_POR_LLAMADA))
    quedan_hoy = max(0, cuota.maximo_diario - cuota.usadas_hoy())
    if not llamadas:
        dias = 0
    elif llamadas <= quedan_hoy:
        dias = 1
    else:
        dias = (1 if quedan_hoy else 0) + math.ceil((llamadas - quedan_hoy) / max(1, cuota.maximo_diario))
    return {
        "ejemplares": len(sesion.registros),
        "sin_isbn": sum(1 for r in sesion.registros if not r.get("isbn")),
        "isbn": len(isbns), "descargados": len(tienen), "sin_ficha": len(sin), "pendientes": len(pendientes),
        "releer": len(releer),
        "llamadas": llamadas, "minutos": math.ceil(llamadas * cuota.pausa / 60), "pausa": cuota.pausa,
        "cuota": cuota.maximo_diario, "quedan_hoy": quedan_hoy, "dias": dias,
        "credenciales": bool(credenciales_dilve()[0]), "bloqueo": bool(cuota.bloqueo()),
    }


def _lanzar_descarga(pendientes, releer, tipo):
    """Arranca una descarga de fichas de DILVE en segundo plano (una a la vez)."""
    if cliente_dilve() is None:
        raise HTTPException(status_code=400, detail="cat_sin_credenciales")
    if cuota_dilve().bloqueo():
        raise HTTPException(status_code=409, detail="cat_bloqueo")
    if not _CANDADO_CATALOGO.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="cat_en_marcha")
    try:
        if TAREA_CATALOGO["en_curso"]:
            raise HTTPException(status_code=409, detail="cat_en_marcha")
        if pendientes or releer:
            _PARAR_CATALOGO.clear()
            TAREA_CATALOGO.update({"en_curso": True, "tipo": tipo})
            threading.Thread(target=_tarea_catalogo, args=(pendientes, releer, tipo), daemon=True,
                             name=f"dilve-{tipo}").start()
    finally:
        _CANDADO_CATALOGO.release()


def _actualizar_idiomas_sesiones():
    """Con fichas nuevas: idioma de todos los análisis abiertos y, para el
    orden por afinidad, el modelo se rehace la próxima vez que se pida."""
    with _CANDADO:
        sesiones = list(SESIONES.values())
    for sesion in sesiones:
        sesion.cuenta_idiomas = asignar_idiomas(sesion.registros)
        sesion.series = None
    for estado in list(SUGERENCIAS.values()):
        estado.pop("modelo_afinidad", None)


def _tarea_catalogo(isbns, releer=(), tipo="catalogo"):
    """Primero las fichas que faltan; después, las que hay que volver a leer."""
    TAREA_CATALOGO["tipo"] = tipo
    cliente = cliente_dilve()
    base = _base_fichas()
    tam = mod_dilve.MAX_POR_LLAMADA
    lotes = ([("nuevas", isbns[i: i + tam]) for i in range(0, len(isbns), tam)]
             + [("releer", list(releer)[i: i + tam]) for i in range(0, len(releer), tam)])
    total = len(isbns) + len(releer)
    TAREA_CATALOGO.update({"en_curso": True, "error": None, "parada": False, "resultado": None,
                           "progreso": {"pedidas": 0, "total": total, "llamadas": 0, "recibidas": 0}})
    recibidas = pedidas = 0
    try:
        for llamada, (tipo, lote) in enumerate(lotes, start=1):
            if _PARAR_CATALOGO.is_set():
                TAREA_CATALOGO["parada"] = True
                break
            if tipo == "nuevas":
                base.fichas(lote, cliente)
                recibidas += len(base.idiomas_de(lote))
            else:
                recibidas += base.releer(lote, cliente)
            pedidas += len(lote)
            TAREA_CATALOGO["progreso"] = {"pedidas": pedidas, "total": total,
                                          "llamadas": llamada, "recibidas": recibidas}
            if cliente.interrupcion is not None:            # cuota del día, bloqueo o contraseña
                TAREA_CATALOGO["error"] = str(cliente.interrupcion)
                break
        if cliente.forma_lista:
            base.escribir("forma_lista", cliente.forma_lista)
        TAREA_CATALOGO["resultado"] = {"recibidas": recibidas}
    except mod_dilve.ErrorDILVE as exc:
        TAREA_CATALOGO["error"] = str(exc)
    except Exception as exc:                                    # noqa: BLE001
        TAREA_CATALOGO["error"] = f"Fallo inesperado: {exc}"
    finally:
        TAREA_CATALOGO["en_curso"] = False
        _actualizar_idiomas_sesiones()


@app.get("/api/sesion/{token}/catalogo-dilve")
def api_catalogo_dilve(token: str):
    """Cuánto supone pedir a DILVE las fichas de todo el catálogo, y cómo va."""
    sesion = obtener_sesion(token)
    return {**estimar_catalogo(sesion), "tarea": TAREA_CATALOGO, "idiomas": sesion.cuenta_idiomas,
            "hay_idiomas": hay_idiomas(sesion.registros)}


@app.post("/api/sesion/{token}/catalogo-dilve/{accion}")
def api_catalogo_dilve_accion(token: str, accion: str, x_admin: str = Header(None)):
    sesion = obtener_sesion(token)
    if accion == "parar":
        _PARAR_CATALOGO.set()
        return api_catalogo_dilve(token)
    if accion != "iniciar":
        raise HTTPException(status_code=404, detail="Acción desconocida.")
    _exigir_admin(x_admin)
    _, _, _, pendientes, releer = _pendientes_catalogo(sesion)
    _lanzar_descarga(pendientes, releer, "catalogo")
    return api_catalogo_dilve(token)


# ===========================================================================
# Catálogo MARC: idioma de los ejemplares, extraído una vez de un .db grande
# ===========================================================================
class EntradaMarc(BaseModel):
    ruta: str


def _estado_marc():
    est = mod_marc.estado(config.RUTA_MARC_IDIOMAS)
    if est and est.get("origen") and os.path.exists(est["origen"]):
        # ¿Se ha actualizado el .db desde la extracción?
        actual = datetime.fromtimestamp(os.path.getmtime(est["origen"]), timezone.utc).isoformat(timespec="seconds")
        est["desactualizado"] = actual != est.get("fecha_origen")
    elif est:
        est["origen_no_encontrado"] = True
    return {"extraccion": est, "ruta": (CONFIG.leer().get("marc") or {}).get("ruta", "")}


@app.get("/api/marc")
def api_marc():
    return _estado_marc()


@app.post("/api/sesion/{token}/marc/extraer")
def api_marc_extraer(token: str, entrada: EntradaMarc, x_admin: str = Header(None)):
    """Extrae del .db el idioma de los ejemplares de esta biblioteca (la
    reconoce por los códigos de barras del análisis abierto) y lo aplica."""
    _exigir_admin(x_admin)
    sesion = obtener_sesion(token)
    codigos = [r["record_id"] for r in absysnet.leer_topografico(sesion.topo)] if sesion.topo \
        else [r["record_id"] for r in sesion.registros]
    try:
        autores = {mod_series.autor_normalizado(r.get("autor")) for r in sesion.registros if r.get("autor")}
        mod_marc.extraer(entrada.ruta, codigos, config.RUTA_MARC_IDIOMAS, autores)
        CONFIG.guardar({"marc": {"ruta": entrada.ruta}})
    except mod_marc.ErrorMarc as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"No se ha podido guardar el idioma extraído: {exc}")
    _actualizar_idiomas_sesiones()
    return {**_estado_marc(), "idiomas": sesion.cuenta_idiomas}


@app.delete("/api/marc")
def api_marc_quitar(x_admin: str = Header(None)):
    """Deja de usar el catálogo MARC (borra solo el fichero pequeño extraído)."""
    _exigir_admin(x_admin)
    try:
        if os.path.exists(config.RUTA_MARC_IDIOMAS):
            os.remove(config.RUTA_MARC_IDIOMAS)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    _actualizar_idiomas_sesiones()
    return _estado_marc()


# ===========================================================================
# Series (a partir de las fichas de DILVE ya descargadas; no llama a DILVE)
# ===========================================================================
def series_sesion(sesion):
    if sesion.series is None:
        isbns = sorted({r["isbn"] for r in sesion.registros if r.get("isbn")})
        fichas = _base_fichas()
        novedades = base_dilve() if os.path.exists(RUTA_DILVE) else None
        propias = fichas.colecciones_de(isbns)
        if novedades is not None and novedades.conn:
            for isbn, f in novedades.colecciones_de([i for i in isbns if i not in propias]).items():
                propias[isbn] = f
        nombres = {f["coleccion"] for f in propias.values()}
        conocidas = fichas.colecciones(nombres)
        if novedades is not None and novedades.conn:
            for nombre, lista in novedades.colecciones(nombres).items():
                conocidas.setdefault(nombre, []).extend(lista)
        sesion.series = mod_series.detectar(sesion.registros, propias, conocidas,
                                            CONFIG.leer().get("series_ocultas") or [])
        # Se apuntan, para conservar sus tomos cuando salgan de las novedades
        try:
            fichas.escribir("series_biblioteca", json.dumps(
                sorted({n for x in sesion.series for n in conocidas if mod_series._clave(n) == x["clave"]}),
                ensure_ascii=False))
        except Exception:                                       # noqa: BLE001
            pass
    return sesion.series


# --- Completar las series: los tomos que la biblioteca no tiene ---------------
DIAS_RELEER_SERIES = 30      # las fichas de los tomos propios se renuevan al mes


def _candidatos_series(sesion):
    """ISBN que pueden ser tomos de las series de la biblioteca y aún no
    tienen ficha: los «del mismo autor» que dan las fichas de DILVE de los
    tomos propios y los libros de esos autores en el catálogo de la red (si
    se extrajo del MARC). Y los tomos propios cuya ficha tiene más de un mes,
    para que su lista de «otras obras del autor» recoja los tomos nuevos.
    Devuelve (por pedir, por releer, cuántos de cada vía, hay red)."""
    lista = series_sesion(sesion)
    fichas = _base_fichas()
    propios_series = sorted({f["isbn"] for x in lista for f in x["filas"]
                             if f["estado"] == "propio" and f.get("isbn")})
    de_dilve = fichas.relacionados_de(propios_series, "22")
    red = mod_marc.isbns_de_autores(config.RUTA_MARC_IDIOMAS, {x["autor"] for x in lista if x.get("autor")})
    de_red = set().union(*red.values()) if red else set()
    del_fondo = {r["isbn"] for r in sesion.registros if r.get("isbn")}
    candidatos = sorted(i for i in (de_dilve | de_red) - del_fondo if mod_dilve.isbn13_valido(i))
    cache = cache_fichas()
    tienen = set(cache.idiomas_de(candidatos))
    sin = cache.sin_ficha()
    pendientes = [i for i in candidatos if i not in tienen and i not in sin]
    releer = sorted(fichas.antiguas(propios_series, DIAS_RELEER_SERIES))
    hay_red = os.path.exists(config.RUTA_MARC_IDIOMAS) and bool((mod_marc.estado(config.RUTA_MARC_IDIOMAS) or {}).get("red_libros"))
    return pendientes, releer, {"dilve": len(de_dilve), "red": len(de_red), "series": len(lista)}, hay_red


@app.get("/api/sesion/{token}/series/completar")
def api_series_completar(token: str):
    """Cuánto supone buscar los tomos que faltan, y cómo va."""
    sesion = obtener_sesion(token)
    pendientes, releer, vias, hay_red = _candidatos_series(sesion)
    cuota = cuota_dilve()
    llamadas = math.ceil(len(pendientes) / mod_dilve.MAX_POR_LLAMADA) + math.ceil(len(releer) / mod_dilve.MAX_POR_LLAMADA)
    quedan_hoy = max(0, cuota.maximo_diario - cuota.usadas_hoy())
    dias = 0 if not llamadas else 1 if llamadas <= quedan_hoy else \
        (1 if quedan_hoy else 0) + math.ceil((llamadas - quedan_hoy) / max(1, cuota.maximo_diario))
    return {"pendientes": len(pendientes), "releer": len(releer), **vias, "hay_red": hay_red,
            "llamadas": llamadas, "minutos": math.ceil(llamadas * cuota.pausa / 60), "pausa": cuota.pausa,
            "cuota": cuota.maximo_diario, "quedan_hoy": quedan_hoy, "dias": dias,
            "credenciales": bool(credenciales_dilve()[0]), "bloqueo": bool(cuota.bloqueo()),
            "tarea": TAREA_CATALOGO}


@app.post("/api/sesion/{token}/series/completar/{accion}")
def api_series_completar_accion(token: str, accion: str, x_admin: str = Header(None)):
    sesion = obtener_sesion(token)
    if accion == "parar":
        _PARAR_CATALOGO.set()
        return api_series_completar(token)
    if accion != "iniciar":
        raise HTTPException(status_code=404, detail="Acción desconocida.")
    _exigir_admin(x_admin)
    pendientes, releer, _, _ = _candidatos_series(sesion)
    _lanzar_descarga(pendientes, releer, "series")
    return api_series_completar(token)


@app.get("/api/sesion/{token}/series")
def api_series(token: str):
    """Series de la biblioteca, cada una con sus tomos (propios, que faltan y
    posiblemente propios) y lo que hay que saber para fiarse del resultado:
    cuántas fichas faltan por descargar o por volver a leer."""
    sesion = obtener_sesion(token)
    _, _, _, pendientes, releer = _pendientes_catalogo(sesion)
    return {"series": series_sesion(sesion), "ocultas": CONFIG.leer().get("series_ocultas") or [],
            "fichas_pendientes": len(pendientes), "fichas_releer": len(releer),
            "credenciales": bool(credenciales_dilve()[0])}


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
    red = CONFIG.leer()
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
    # Los libros de los autores del núcleo (con sus préstamos): si cambian,
    # el resultado guardado ya no vale
    nucleo = mod_sugerencias.nucleo_autores(sesion.registros, opciones["fraccion_nucleo"])
    firma = sorted(f"{clave}:{a['prestamos']}:{a['prestados']}:{a['ejemplares']}" for clave, a in nucleo)
    firma += sorted(isbn for isbn, _ in mod_sugerencias.semillas_autores(nucleo))
    return hashlib.sha1(("autores|" + "|".join(firma)).encode("utf-8")).hexdigest()[:16], len(nucleo)


def _autores_guardados(sesion, huella):
    """Resultado de una sesión anterior de esta misma biblioteca, si el núcleo
    de préstamo no ha cambiado."""
    guardado = ALMACEN.leer_json(sesion.carpeta, "sugerencias_autores.json")
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
        ALMACEN.escribir_json(sesion.carpeta, "sugerencias_autores.json", datos)
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
    conf = CONFIG.leer()
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
    datos["ventana_meses"] = CONFIG.leer()["dilve"]["meses_novedades"]
    return datos


@app.get("/api/thema")
def api_thema(ui: str = "es"):
    """Encabezados THEMA en el idioma de la interfaz (o el más cercano que
    haya), para rotular los códigos de las fichas. Vacío si la red no ha
    dejado la lista de EDItEUR en la carpeta de datos."""
    return {"idioma": ENCABEZADOS_THEMA.idioma_servido(ui), "ficheros": ENCABEZADOS_THEMA.ficheros,
            "nombres": ENCABEZADOS_THEMA.tabla(ui)}


# ===========================================================================
# Abrir el último análisis guardado sin volver a subir los ficheros
# ===========================================================================
@app.post("/api/abrir-ultima")
def api_abrir_ultima():
    ultima = _ultima_carga()
    if not ultima:
        raise HTTPException(status_code=404, detail="acceso_sin_carga")
    por_tipo = ALMACEN.leer_carga(carpeta_biblioteca(), ultima["id"])
    if not por_tipo:
        raise HTTPException(status_code=404, detail="acceso_carga_ilegible")
    respuesta, sesion = _analizar_subidos(_a_subidos(por_tipo))
    if sesion is None:
        return respuesta
    sesion.id_carga = ultima["id"]
    respuesta["carga"] = ultima["id"]
    respuesta["fecha_carga"] = ultima.get("fecha")
    respuesta["cambios"] = _resumen_cambios(cambios_sesion(sesion))
    _precargar_sugerencias(respuesta["sesion"])
    return respuesta


# ===========================================================================
# Historial de cargas (seguimiento)
# ===========================================================================
@app.get("/api/sesion/{token}/historial")
def api_historial(token: str):
    sesion = obtener_sesion(token)
    red = CONFIG.leer()
    cargas = ALMACEN.cargas(sesion.carpeta)
    _completar_cambios(sesion.carpeta, cargas)
    return {"activo": red["historial"], "max_cargas": red["max_cargas"],
            "cargas": cargas, "error": ALMACEN.error}


@app.get("/api/sesion/{token}/cambios")
def api_cambios(token: str):
    """Altas y bajas, ejemplar a ejemplar, respecto a la carga anterior."""
    sesion = obtener_sesion(token)
    return cambios_sesion(sesion) or {"anterior": None}


@app.post("/api/sesion/{token}/historial/{id_carga}/abrir")
def api_abrir_carga(token: str, id_carga: str):
    """Vuelve a analizar una carga guardada, sin subir de nuevo los ficheros.
    Solo las de la propia biblioteca: la carpeta sale de la sesión."""
    sesion = obtener_sesion(token)
    por_tipo = ALMACEN.leer_carga(sesion.carpeta, id_carga)
    if not por_tipo:
        raise HTTPException(status_code=404, detail="No se encuentra esa carga.")
    respuesta, nueva = _analizar_subidos(_a_subidos(por_tipo))
    if nueva is None:
        return respuesta
    nueva.id_carga = id_carga
    respuesta["carga"] = id_carga
    respuesta["cambios"] = _resumen_cambios(cambios_sesion(nueva))
    _precargar_sugerencias(respuesta["sesion"])
    return respuesta


@app.delete("/api/sesion/{token}/historial/{id_carga}")
def api_borrar_carga(token: str, id_carga: str):
    sesion = obtener_sesion(token)
    if not ALMACEN.borrar_carga(sesion.carpeta, id_carga):
        raise HTTPException(status_code=404, detail="No se encuentra esa carga.")
    return {"cargas": ALMACEN.cargas(sesion.carpeta)}


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
