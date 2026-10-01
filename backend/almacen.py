# -*- coding: utf-8 -*-
"""Carpeta de cada biblioteca: datos/bibliotecas/<biblioteca>/

    preferencias.json        su configuración (idioma, tema, pestañas…)
    cargas/<fecha>/          cada carga: los listados tal como se subieron
        topografico/…txt     (uno o varios ficheros por tipo)
        resumen.json         indicadores de esa carga, para el seguimiento

Los listados de AbsysNet que usa Bildumargi describen ejemplares (signatura,
código de barras, título, préstamo sí/no), no lectores: no contienen datos
personales. Aun así, solo se guardan si la red activa el historial, se
conservan las últimas N cargas y cada biblioteca puede borrar las suyas.
"""

import json
import os
import re
import shutil
import threading
import unicodedata
from datetime import datetime

TIPOS = ("topografico", "catalogo", "no_prestados", "mas_prestados")
_R_CARGA = re.compile(r"^\d{8}-\d{6}(-\d+)?$")


def slug(nombre):
    """«Biblioteca de Monteagudo» → «biblioteca-de-monteagudo»."""
    texto = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return texto[:80] or "biblioteca"


def _escribir_json(ruta, datos):
    temporal = f"{ruta}.tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)


def _nombre_seguro(nombre):
    base = os.path.basename(str(nombre or "fichero.txt"))
    base = re.sub(r"[^\w.\- ]+", "_", base).strip() or "fichero.txt"
    return base[:120]


class Almacen:
    def __init__(self, raiz):
        self.raiz = raiz
        self._candado = threading.Lock()
        self.error = None
        try:
            os.makedirs(raiz, exist_ok=True)
        except OSError as exc:
            self.error = f"No se puede crear «{raiz}»: {exc}"
        else:
            if not os.access(raiz, os.W_OK):
                self.error = f"La carpeta «{raiz}» no admite escritura."

    def carpeta(self, biblioteca, crear=True):
        ruta = os.path.join(self.raiz, slug(biblioteca))
        if crear:
            os.makedirs(ruta, exist_ok=True)
            ficha = os.path.join(ruta, "biblioteca.txt")
            if not os.path.exists(ficha):   # para saber de quién es la carpeta a simple vista
                with open(ficha, "w", encoding="utf-8") as f:
                    f.write(str(biblioteca) + "\n")
        return ruta

    # -- preferencias ------------------------------------------------------
    def leer_json(self, biblioteca, nombre):
        try:
            with open(os.path.join(self.carpeta(biblioteca, crear=False), nombre), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def escribir_json(self, biblioteca, nombre, datos):
        if self.error:
            raise OSError(self.error)
        with self._candado:
            _escribir_json(os.path.join(self.carpeta(biblioteca), nombre), datos)

    # -- historial de cargas -----------------------------------------------
    def _carpeta_cargas(self, biblioteca, crear=True):
        ruta = os.path.join(self.carpeta(biblioteca, crear=crear), "cargas")
        if crear:
            os.makedirs(ruta, exist_ok=True)
        return ruta

    def guardar_carga(self, biblioteca, subidos, resumen, max_cargas):
        """subidos: {tipo: [(nombre, bytes), …]}. Devuelve el id de la carga."""
        if self.error:
            raise OSError(self.error)
        with self._candado:
            base = self._carpeta_cargas(biblioteca)
            id_carga = datetime.now().strftime("%Y%m%d-%H%M%S")
            n = 1
            while os.path.exists(os.path.join(base, id_carga)):
                n += 1
                id_carga = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}"
            destino = os.path.join(base, id_carga)
            os.makedirs(destino)
            nombres = {}
            for tipo in TIPOS:
                ficheros = subidos.get(tipo) or []
                if not ficheros:
                    continue
                os.makedirs(os.path.join(destino, tipo))
                nombres[tipo] = []
                for i, (nombre, contenido) in enumerate(ficheros):
                    seguro = _nombre_seguro(nombre)
                    if seguro in nombres[tipo]:
                        seguro = f"{i + 1}_{seguro}"
                    with open(os.path.join(destino, tipo, seguro), "wb") as f:
                        f.write(contenido)
                    nombres[tipo].append(seguro)
            _escribir_json(os.path.join(destino, "resumen.json"),
                           {**resumen, "id": id_carga, "fecha": datetime.now().isoformat(timespec="seconds"),
                            "ficheros": nombres})
            # Conservar solo las últimas `max_cargas`
            todas = sorted(c for c in os.listdir(base) if _R_CARGA.match(c))
            for vieja in todas[:-int(max_cargas)] if len(todas) > int(max_cargas) else []:
                shutil.rmtree(os.path.join(base, vieja), ignore_errors=True)
        return id_carga

    def cargas(self, biblioteca):
        base = self._carpeta_cargas(biblioteca, crear=False)
        if not os.path.isdir(base):
            return []
        salida = []
        for c in sorted((c for c in os.listdir(base) if _R_CARGA.match(c)), reverse=True):
            try:
                with open(os.path.join(base, c, "resumen.json"), encoding="utf-8") as f:
                    salida.append(json.load(f))
            except (OSError, ValueError):
                continue
        return salida

    def leer_carga(self, biblioteca, id_carga):
        if not _R_CARGA.match(str(id_carga)):
            return None
        ruta = os.path.join(self._carpeta_cargas(biblioteca, crear=False), id_carga)
        if not os.path.isdir(ruta):
            return None
        subidos = {}
        for tipo in TIPOS:
            carpeta = os.path.join(ruta, tipo)
            if os.path.isdir(carpeta):
                subidos[tipo] = []
                for nombre in sorted(os.listdir(carpeta)):
                    with open(os.path.join(carpeta, nombre), "rb") as f:
                        subidos[tipo].append((nombre, f.read()))
        return subidos

    def borrar_carga(self, biblioteca, id_carga):
        if not _R_CARGA.match(str(id_carga)):
            return False
        ruta = os.path.join(self._carpeta_cargas(biblioteca, crear=False), id_carga)
        if not os.path.isdir(ruta):
            return False
        with self._candado:
            shutil.rmtree(ruta, ignore_errors=True)
        return True
