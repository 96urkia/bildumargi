# -*- coding: utf-8 -*-
"""Encabezados de los códigos Thema, para enseñarlos y buscar por ellos.

Las fichas de DILVE traen solo el código (FRD, XQG…). El encabezado que le
corresponde («Novela romántica», «Novela gráfica»…) está en las listas que
publica EDItEUR, gratuitas y de uso libre, con traducción oficial al
castellano facilitada por la FGEE, bajo la licencia de EDItEUR
(https://doi.org/10.4400/nwgj): se pueden redistribuir sin modificar, pero no
extractos ni versiones alteradas sin permiso. Bildumargi NO las trae dentro:
cada red descarga la versión que quiera y la deja en la carpeta de datos con el
nombre `thema_<idioma>.<ext>` (thema_es.json, thema_en.xml…); un fichero
llamado solo `thema.<ext>` cuenta como castellano.

Formatos admitidos:
  - El JSON y el XML de EDItEUR (elementos con CodeValue y CodeDescription).
  - Un JSON sencillo: {"FRD": "Novela romántica", ...}.
  - Un CSV o TSV con el código en la primera columna y el encabezado en la
    segunda.

Sin fichero, todo funciona igual: se enseñan los códigos, con enlace al
buscador de EDItEUR, y se puede buscar por código.
"""

import csv
import glob
import io
import json
import os
import re

_CODIGO = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")     # materias (los calificadores empiezan por cifra)
_NOMBRE_FICHERO = re.compile(r"^thema(?:_([a-z]{2}))?\.(json|xml|csv|tsv|txt)$", re.I)


def _anadir(destino, codigo, nombre):
    codigo = str(codigo or "").strip().upper()
    nombre = " ".join(str(nombre or "").split())
    if _CODIGO.match(codigo) and nombre:
        destino.setdefault(codigo, nombre)


def _desde_json(texto):
    datos, pares = json.loads(texto), {}
    # Formato sencillo: {"código": "encabezado"}
    if isinstance(datos, dict) and datos and all(isinstance(v, str) for v in datos.values()):
        for codigo, nombre in datos.items():
            _anadir(pares, codigo, nombre)
        return pares
    # Formato de EDItEUR: se recorre entero buscando CodeValue/CodeDescription,
    # para no depender de cómo anide cada versión la lista.
    pendientes = [datos]
    while pendientes:
        nodo = pendientes.pop()
        if isinstance(nodo, dict):
            if "CodeValue" in nodo and "CodeDescription" in nodo:
                _anadir(pares, nodo["CodeValue"], nodo["CodeDescription"])
            pendientes.extend(nodo.values())
        elif isinstance(nodo, list):
            pendientes.extend(nodo)
    return pares


def _desde_xml(contenido):
    from lxml import etree
    pares = {}
    raiz = etree.fromstring(contenido)
    for elemento in raiz.iter():
        hijos = {etree.QName(h).localname: (h.text or "") for h in elemento if isinstance(h.tag, str)}
        if "CodeValue" in hijos and "CodeDescription" in hijos:
            _anadir(pares, hijos["CodeValue"], hijos["CodeDescription"])
    return pares


def _desde_csv(texto):
    pares = {}
    muestra = texto[:4096]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=";,\t")
    except csv.Error:
        dialecto = csv.excel_tab if "\t" in muestra else csv.excel
    for fila in csv.reader(io.StringIO(texto), dialecto):
        if len(fila) >= 2:
            _anadir(pares, fila[0], fila[1])      # la cabecera no pasa el filtro de código
    return pares


def leer_fichero(ruta):
    """Diccionario código -> encabezado de un fichero. Vacío si no se entiende."""
    extension = os.path.splitext(ruta)[1].lower()
    try:
        with open(ruta, "rb") as f:
            contenido = f.read()
        if extension == ".xml":
            return _desde_xml(contenido)
        texto = contenido.decode("utf-8-sig", errors="replace")
        return _desde_json(texto) if extension == ".json" else _desde_csv(texto)
    except (OSError, ValueError, ImportError, Exception):   # un fichero roto no tumba el servidor
        return {}


class Encabezados:
    """Encabezados por idioma, con vuelta al castellano y al inglés."""

    def __init__(self, ruta_datos=None):
        self.por_idioma, self.ficheros = {}, []
        if ruta_datos and os.path.isdir(ruta_datos):
            for ruta in sorted(glob.glob(os.path.join(ruta_datos, "thema*"))):
                m = _NOMBRE_FICHERO.match(os.path.basename(ruta))
                if not m:
                    continue
                pares = leer_fichero(ruta)
                if pares:
                    idioma = (m.group(1) or "es").lower()
                    self.por_idioma.setdefault(idioma, {}).update(pares)
                    self.ficheros.append(os.path.basename(ruta))

    def __bool__(self):
        return bool(self.por_idioma)

    def tabla(self, idioma):
        """Todos los encabezados en ese idioma, completados con los de otros."""
        salida = {}
        for i in (idioma, "es", "en", *self.por_idioma):
            for codigo, nombre in (self.por_idioma.get(i) or {}).items():
                salida.setdefault(codigo, nombre)
        return salida

    def idioma_servido(self, idioma):
        return next((i for i in (idioma, "es", "en", *self.por_idioma) if i in self.por_idioma), None)

    def es_codigo(self, texto):
        return any(texto in tabla for tabla in self.por_idioma.values())

    def nombres(self, codigo):
        """Encabezados del código en todos los idiomas cargados (para buscar)."""
        return [t[codigo] for t in self.por_idioma.values() if codigo in t]
