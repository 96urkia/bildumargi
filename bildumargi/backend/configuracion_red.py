# -*- coding: utf-8 -*-
"""Configuración de la red: lo que decide la administración para todas las
bibliotecas (pestañas que existen, idiomas que se ofrecen, apariencia por
defecto, historial de cargas y novedades de DILVE). Cada biblioteca ajusta después lo suyo dentro
de ese marco (ver preferencias.py).

Vive en datos/configuracion_red.json y solo se modifica con la clave de
administración (CLAVE_ADMIN en config.py o BILDUMARGI_CLAVE_ADMIN).
"""

import json
import os
import threading

PESTANAS = ("diagnostico", "secciones", "compras", "red", "seguimiento")
IDIOMAS = ("es", "eu", "ca", "gl", "en")
TEMAS = ("oscuro", "claro")
PALETAS = ("okabe", "viridis", "azules")

POR_DEFECTO = {
    "pestanas_activas": list(PESTANAS),
    "idiomas": list(IDIOMAS),
    "idioma_defecto": None,        # None = IDIOMA_POR_DEFECTO de config.py
    "tema_defecto": "oscuro",
    "paleta_defecto": "okabe",
    "historial": True,             # guardar los listados de cada carga
    "max_cargas": 12,              # cargas que se conservan por biblioteca
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
    # Tabla de signaturas de la red (prefijo -> sección) para el análisis.
    # None = la de siempre; cada biblioteca puede tener la suya encima.
    "signaturas": None,
    # Qué fuentes de sugerencias de compra ve la biblioteca
    "sugerencias": {
        "presencia": True,          # títulos que tiene la red y esta biblioteca no
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


def validar(entrada):
    c = dict(POR_DEFECTO)
    entrada = entrada or {}
    activas = [p for p in (entrada.get("pestanas_activas") or []) if p in PESTANAS]
    if "pestanas_activas" in entrada:
        if not activas:
            raise ErrorConfiguracion("Tiene que quedar al menos una pestaña activa.")
        c["pestanas_activas"] = sorted(set(activas), key=PESTANAS.index)
    idiomas = [i for i in (entrada.get("idiomas") or []) if i in IDIOMAS]
    if "idiomas" in entrada:
        if not idiomas:
            raise ErrorConfiguracion("Tiene que quedar al menos un idioma.")
        c["idiomas"] = sorted(set(idiomas), key=IDIOMAS.index)
    if entrada.get("idioma_defecto") in c["idiomas"]:
        c["idioma_defecto"] = entrada["idioma_defecto"]
    if entrada.get("tema_defecto") in TEMAS:
        c["tema_defecto"] = entrada["tema_defecto"]
    if entrada.get("paleta_defecto") in PALETAS:
        c["paleta_defecto"] = entrada["paleta_defecto"]
    if "historial" in entrada:
        c["historial"] = bool(entrada["historial"])
    try:
        c["max_cargas"] = max(1, min(60, int(entrada.get("max_cargas", c["max_cargas"]))))
    except (TypeError, ValueError):
        pass
    if "signaturas" in entrada:
        from backend.clasificacion import normalizar_reglas
        try:
            c["signaturas"] = normalizar_reglas(entrada["signaturas"])
        except ValueError as exc:
            raise ErrorConfiguracion(str(exc))
    c["dilve"] = _validar_dilve(entrada.get("dilve"))
    c["sugerencias"] = _validar_sugerencias(entrada.get("sugerencias"))
    return c


def _validar_sugerencias(entrada):
    s = dict(POR_DEFECTO["sugerencias"])
    entrada = entrada or {}
    for campo in ("presencia", "autores", "novedades", "sugeridos_editorial",
                  "excluir_especiales", "excluir_texto"):
        if campo in entrada:
            s[campo] = bool(entrada[campo])
    for campo, minimo, maximo in (("anios_recientes", 1, 30), ("max_por_autor", 1, 20)):
        try:
            s[campo] = max(minimo, min(maximo, int(entrada.get(campo, s[campo]))))
        except (TypeError, ValueError):
            pass
    try:
        s["fraccion_nucleo"] = max(.1, min(1.0, float(entrada.get("fraccion_nucleo", s["fraccion_nucleo"]))))
    except (TypeError, ValueError):
        pass
    return s


# Códigos ONIX (ISO 639-2/B). «baq» y «eus» son el mismo idioma: las
# editoriales usan uno u otro, así que se ofrecen los dos.
def _validar_dilve(entrada):
    d = dict(POR_DEFECTO["dilve"])
    entrada = entrada or {}
    for campo in ("activo", "descarga_inicial", "solo_libros"):
        if campo in entrada:
            d[campo] = bool(entrada[campo])
    try:
        d["cada_dias"] = max(1, min(90, int(entrada.get("cada_dias", d["cada_dias"]))))
    except (TypeError, ValueError):
        pass
    try:
        d["max_llamadas_dia"] = max(20, min(5000, int(entrada.get("max_llamadas_dia", d["max_llamadas_dia"]))))
    except (TypeError, ValueError):
        pass
    try:
        d["pausa_llamadas"] = max(6.0, min(60.0, float(entrada.get("pausa_llamadas", d["pausa_llamadas"]))))
    except (TypeError, ValueError):
        pass
    try:
        d["meses_novedades"] = max(1, min(24, int(entrada.get("meses_novedades", d["meses_novedades"]))))
    except (TypeError, ValueError):
        pass
    return d


class ConfiguracionRed:
    def __init__(self, ruta):
        self.ruta = ruta
        self._candado = threading.Lock()

    def leer(self):
        try:
            with open(self.ruta, encoding="utf-8") as f:
                return validar(json.load(f))
        except (OSError, ValueError, ErrorConfiguracion):
            return dict(POR_DEFECTO)

    def guardar(self, entrada):
        c = validar(entrada)
        with self._candado:
            temporal = f"{self.ruta}.tmp"
            try:
                with open(temporal, "w", encoding="utf-8") as f:
                    json.dump(c, f, ensure_ascii=False, indent=2)
                os.replace(temporal, self.ruta)
            except OSError as exc:
                raise ErrorConfiguracion(f"No se ha podido guardar la configuración de la red: {exc}")
        return c
