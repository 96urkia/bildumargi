# -*- coding: utf-8 -*-
"""Configuración de Bildumargi: una sola, la de la biblioteca.

Reúne lo que en la 1.x estaba repartido entre la configuración de la red
(administración) y las preferencias de cada biblioteca:

    biblioteca    nombre, población, superficie y el código de sucursal de
                  sus listados (lo apunta Bildumargi en la primera carga)
    apariencia    idioma, tema, paleta, pestañas ocultas y de inicio
    historial     si se guardan las cargas y cuántas
    signaturas    tabla propia prefijo -> sección (None = la estándar)
    dilve         descarga de novedades y freno de llamadas
    sugerencias   ajustes de «Autores más prestados» y «Novedades»

Vive en datos/configuracion.json. Si falta y existe la configuración de la
red de la 1.x (configuracion_red.json), se parte de ella.
"""

import json
import os
import threading

PESTANAS = ("diagnostico", "secciones", "series", "compras", "seguimiento")
IDIOMAS = ("es", "eu", "ca", "gl", "en")
TEMAS = ("oscuro", "claro")
PALETAS = ("okabe", "viridis", "azules")

POR_DEFECTO = {
    "biblioteca": {
        "nombre": "",
        "red": None,                # red a la que pertenece (None = NOMBRE_RED de config.py)
        "poblacion": None,          # habitantes atendidos
        "metros": None,             # superficie útil
        "sucursal": None,           # código «Suc.» de los listados (lo pone Bildumargi)
        "carpeta": None,            # carpeta de su historial en datos/bibliotecas/
    },
    "idioma": None,                 # None = IDIOMA_POR_DEFECTO de config.py
    "tema": "oscuro",
    "paleta": "okabe",
    "pestanas_ocultas": [],
    "inicio": "diagnostico",
    "historial": True,              # guardar los listados de cada carga
    "max_cargas": 12,               # cargas que se conservan
    # Tabla de signaturas (prefijo -> sección) para el análisis. None = la estándar.
    "signaturas": None,
    # Colecciones de DILVE que parecen series y no lo son: no se enseñan
    "series_ocultas": [],
    # Catálogo MARC (.db de conversor.py) del que se extrae el idioma
    "marc": {"ruta": ""},
    # Novedades del libro español (DILVE). Sin credenciales no se hace nada.
    "dilve": {
        "activo": False,
        "descarga_inicial": True,   # si falta la base, descargarla sola
        "cada_dias": 7,             # cada cuánto se actualiza
        "solo_libros": True,        # sugerir solo libro en papel
        "max_llamadas_dia": 300,    # freno: llamadas a DILVE por día como máximo
        "pausa_llamadas": 6.0,      # segundos entre dos llamadas (DILVE recomienda 6; es el mínimo)
        "meses_novedades": 3,       # ventana de novedades: lo que se descarga y se conserva
    },
    # Qué fuentes de sugerencias de compra se ven y cómo se calculan
    "sugerencias": {
        "autores": True,            # obras del mismo autor de lo más prestado (DILVE)
        "novedades": True,          # novedades recientes de DILVE
        "sugeridos_editorial": False,   # relacionados sin coincidencia de autor (catálogo del editor)
        "anios_recientes": 5,
        "max_por_autor": 3,
        "fraccion_nucleo": 0.5,     # mitad de los préstamos de cada sección (Bradford)
        "excluir_especiales": True,
        "excluir_texto": True,
    },
}


class ErrorConfiguracion(Exception):
    pass


def _copia(valor):
    return json.loads(json.dumps(valor))


def _entero(valor, minimo=None, maximo=None):
    if valor is None or str(valor).strip() == "":
        return None
    try:
        n = int(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return None
    if minimo is not None:
        n = max(minimo, n)
    if maximo is not None:
        n = min(maximo, n)
    return n


def _validar_biblioteca(entrada, actual=None):
    b = _copia(POR_DEFECTO["biblioteca"])
    b.update({k: v for k, v in (actual or {}).items() if k in b})
    entrada = entrada or {}
    if "nombre" in entrada:
        b["nombre"] = " ".join(str(entrada.get("nombre") or "").split())[:120]
    if "red" in entrada:
        b["red"] = " ".join(str(entrada.get("red") or "").split())[:120]
    if "poblacion" in entrada:
        b["poblacion"] = _entero(entrada.get("poblacion"), 0, 50_000_000)
    if "metros" in entrada:
        metros = _entero(entrada.get("metros"), 0, 1_000_000)
        b["metros"] = metros or None
    # Sucursal y carpeta las pone Bildumargi, no la pantalla de configuración
    for campo in ("sucursal", "carpeta"):
        if campo in entrada and actual is None:
            b[campo] = entrada[campo]
    return b


def validar(entrada, actual=None):
    """Configuración completa y válida a partir de lo recibido. Lo
    desconocido se descarta; lo que falta toma el valor por defecto (o el de
    `actual`, si se da: así se puede cambiar solo una parte)."""
    c = _copia(actual) if actual else _copia(POR_DEFECTO)
    entrada = entrada or {}
    if "biblioteca" in entrada or actual is None:
        c["biblioteca"] = _validar_biblioteca(entrada.get("biblioteca"),
                                              (actual or {}).get("biblioteca") if actual else None)
    if entrada.get("idioma") in IDIOMAS or ("idioma" in entrada and entrada["idioma"] is None):
        c["idioma"] = entrada["idioma"]
    if entrada.get("tema") in TEMAS:
        c["tema"] = entrada["tema"]
    if entrada.get("paleta") in PALETAS:
        c["paleta"] = entrada["paleta"]
    if "pestanas_ocultas" in entrada:
        ocultas = [x for x in (entrada.get("pestanas_ocultas") or []) if x in PESTANAS]
        if len(set(ocultas)) >= len(PESTANAS):
            raise ErrorConfiguracion("Tiene que quedar al menos una pestaña visible.")
        c["pestanas_ocultas"] = sorted(set(ocultas), key=PESTANAS.index)
    visibles = [x for x in PESTANAS if x not in c["pestanas_ocultas"]]
    inicio = entrada.get("inicio", c.get("inicio"))
    c["inicio"] = inicio if inicio in visibles else visibles[0]
    if "historial" in entrada:
        c["historial"] = bool(entrada["historial"])
    if "max_cargas" in entrada:
        c["max_cargas"] = _entero(entrada.get("max_cargas"), 1, 60) or c["max_cargas"]
    if "signaturas" in entrada:
        from backend.clasificacion import normalizar_reglas
        try:
            c["signaturas"] = normalizar_reglas(entrada["signaturas"])
        except ValueError as exc:
            raise ErrorConfiguracion(str(exc))
    if "series_ocultas" in entrada:
        c["series_ocultas"] = sorted({" ".join(str(x).split())[:200]
                                      for x in (entrada.get("series_ocultas") or []) if str(x).strip()})[:500]
    if "marc" in entrada or actual is None:
        ruta_marc = str((entrada.get("marc") or {}).get("ruta", (c.get("marc") or {}).get("ruta", "")) or "")
        c["marc"] = {"ruta": ruta_marc.strip().strip('"')[:500]}
    if "dilve" in entrada or actual is None:
        c["dilve"] = _validar_dilve(entrada.get("dilve"), c.get("dilve"))
    if "sugerencias" in entrada or actual is None:
        c["sugerencias"] = _validar_sugerencias(entrada.get("sugerencias"), c.get("sugerencias"))
    return c


def _validar_sugerencias(entrada, actual=None):
    s = _copia(POR_DEFECTO["sugerencias"])
    s.update({k: v for k, v in (actual or {}).items() if k in s})
    entrada = entrada or {}
    for campo in ("autores", "novedades", "sugeridos_editorial", "excluir_especiales", "excluir_texto"):
        if campo in entrada:
            s[campo] = bool(entrada[campo])
    for campo, minimo, maximo in (("anios_recientes", 1, 30), ("max_por_autor", 1, 20)):
        if campo in entrada:
            s[campo] = _entero(entrada.get(campo), minimo, maximo) or s[campo]
    try:
        s["fraccion_nucleo"] = max(.1, min(1.0, float(entrada.get("fraccion_nucleo", s["fraccion_nucleo"]))))
    except (TypeError, ValueError):
        pass
    return s


def _validar_dilve(entrada, actual=None):
    d = _copia(POR_DEFECTO["dilve"])
    d.update({k: v for k, v in (actual or {}).items() if k in d})
    entrada = entrada or {}
    for campo in ("activo", "descarga_inicial", "solo_libros"):
        if campo in entrada:
            d[campo] = bool(entrada[campo])
    for campo, minimo, maximo in (("cada_dias", 1, 90), ("max_llamadas_dia", 20, 5000),
                                  ("meses_novedades", 1, 24)):
        if campo in entrada:
            d[campo] = _entero(entrada.get(campo), minimo, maximo) or d[campo]
    try:
        d["pausa_llamadas"] = max(6.0, min(60.0, float(entrada.get("pausa_llamadas", d["pausa_llamadas"]))))
    except (TypeError, ValueError):
        pass
    return d


def desde_configuracion_red(red):
    """La configuración de la red de la 1.x, traducida a la de la 2.0."""
    red = red or {}
    activas = red.get("pestanas_activas")
    entrada = {
        "idioma": red.get("idioma_defecto"),
        "tema": red.get("tema_defecto"),
        "paleta": red.get("paleta_defecto"),
        "historial": red.get("historial", True),
        "max_cargas": red.get("max_cargas", 12),
        "dilve": red.get("dilve") or {},
        "sugerencias": red.get("sugerencias") or {},
    }
    if red.get("signaturas"):
        entrada["signaturas"] = red["signaturas"]
    if isinstance(activas, list):
        entrada["pestanas_ocultas"] = [p for p in PESTANAS if p not in activas]
    try:
        return validar(entrada)
    except ErrorConfiguracion:
        return validar({k: v for k, v in entrada.items() if k != "pestanas_ocultas"})


class Configuracion:
    def __init__(self, ruta, ruta_red_antigua=None):
        self.ruta = ruta
        self.ruta_red_antigua = ruta_red_antigua
        self._candado = threading.Lock()

    def _leer_json(self, ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def leer(self):
        guardada = self._leer_json(self.ruta)
        if guardada is not None:
            try:
                return validar(guardada)
            except ErrorConfiguracion:
                pass
        elif self.ruta_red_antigua:
            antigua = self._leer_json(self.ruta_red_antigua)
            if antigua:
                return desde_configuracion_red(antigua)
        return _copia(POR_DEFECTO)

    def _escribir(self, c):
        temporal = f"{self.ruta}.tmp"
        try:
            os.makedirs(os.path.dirname(self.ruta) or ".", exist_ok=True)
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
            os.replace(temporal, self.ruta)
        except OSError as exc:
            raise ErrorConfiguracion(f"No se ha podido guardar la configuración: {exc}")

    def guardar(self, entrada):
        """Lo que llega de la pantalla de configuración. Lo que no se envía se
        conserva; la sucursal y la carpeta de la biblioteca no se tocan."""
        with self._candado:
            c = validar(entrada, self.leer())
            self._escribir(c)
        return c

    def guardar_biblioteca(self, **datos):
        """Lo que apunta el propio Bildumargi (sucursal, carpeta, datos
        importados de la 1.x)."""
        with self._candado:
            c = self.leer()
            c["biblioteca"].update(datos)
            c = validar(c)
            self._escribir(c)
        return c
