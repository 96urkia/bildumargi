# -*- coding: utf-8 -*-
"""Preferencias de cada biblioteca: idioma, tema, paleta de los gráficos,
pestañas visibles y pestaña de inicio.

Se guardan en el servidor, por nombre de biblioteca, para que la configuración
sea la misma en cualquier ordenador de esa biblioteca. Es un JSON pequeño: se
reescribe entero de forma atómica (fichero temporal + reemplazo), así un corte
a mitad de escritura nunca deja el fichero a medias.
"""

import json

TEMAS = ("oscuro", "claro")
IDIOMAS = ("es", "eu", "ca", "gl", "en")
PALETAS = ("okabe", "viridis", "azules")
PESTANAS = ("diagnostico", "secciones", "compras", "red", "seguimiento")

# idioma None = el de la instalación (IDIOMA_POR_DEFECTO en config.py)
POR_DEFECTO = {"tema": "oscuro", "paleta": "okabe", "pestanas_ocultas": [], "inicio": "diagnostico",
               "idioma": None}


class ErrorPreferencias(Exception):
    pass


def validar(entrada):
    """Devuelve unas preferencias completas y válidas a partir de lo recibido.
    Lo desconocido se descarta; lo que falta toma el valor por defecto."""
    p = dict(POR_DEFECTO)
    entrada = entrada or {}
    if entrada.get("tema") in TEMAS:
        p["tema"] = entrada["tema"]
    if entrada.get("paleta") in PALETAS:
        p["paleta"] = entrada["paleta"]
    if entrada.get("idioma") in IDIOMAS:
        p["idioma"] = entrada["idioma"]
    ocultas = [x for x in (entrada.get("pestanas_ocultas") or []) if x in PESTANAS]
    if len(set(ocultas)) >= len(PESTANAS):
        raise ErrorPreferencias("Tiene que quedar al menos una pestaña visible.")
    p["pestanas_ocultas"] = sorted(set(ocultas), key=PESTANAS.index)
    inicio = entrada.get("inicio")
    visibles = [x for x in PESTANAS if x not in p["pestanas_ocultas"]]
    p["inicio"] = inicio if inicio in visibles else visibles[0]
    return p


class Preferencias:
    """Preferencias en la carpeta de cada biblioteca (almacen.py):
    datos/bibliotecas/<biblioteca>/preferencias.json.

    Si existe el datos/preferencias.json de versiones anteriores (todas las
    bibliotecas en un fichero), se lee como respaldo y se pasa a la carpeta
    de la biblioteca la primera vez que esta guarda."""

    def __init__(self, almacen, ruta_legado=None):
        self.almacen = almacen
        self.ruta_legado = ruta_legado
        self.error = almacen.error

    def _legado(self, biblioteca):
        if not self.ruta_legado:
            return None
        try:
            with open(self.ruta_legado, encoding="utf-8") as f:
                return (json.load(f) or {}).get(str(biblioteca or "").strip())
        except (OSError, ValueError, AttributeError):
            return None

    def de(self, biblioteca):
        guardadas = self.almacen.leer_json(biblioteca, "preferencias.json") or self._legado(biblioteca)
        if not guardadas:
            return None
        try:
            return validar(guardadas)
        except ErrorPreferencias:
            return None

    def guardar(self, biblioteca, entrada):
        biblioteca = str(biblioteca or "").strip()
        if not biblioteca:
            raise ErrorPreferencias("No se sabe de qué biblioteca son estas preferencias.")
        if self.error:
            raise ErrorPreferencias(self.error)
        prefs = validar(entrada)
        try:
            self.almacen.escribir_json(biblioteca, "preferencias.json", prefs)
        except OSError as exc:
            raise ErrorPreferencias(f"No se han podido guardar las preferencias: {exc}")
        return prefs
