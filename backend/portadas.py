# -*- coding: utf-8 -*-
"""Miniaturas de las portadas de DILVE, guardadas en local.

Las editoriales dan en DILVE la portada original, a tamaño de imprenta: de
media unos 800 KB (algunas, varios MB), servidas por decenas de servidores
distintos. Una página de 48 novedades eran unos 40 MB. Aquí cada portada se
descarga una sola vez, se reduce a una miniatura de unos 15-30 KB y se guarda
en datos/cache/portadas; las siguientes veces sale del disco al momento.

Sin Pillow (zip o .deb instalados sin él) se guarda la imagen tal cual: no
pesa menos, pero tampoco se vuelve a pedir a la editorial.

Solo se piden direcciones http(s) de servidores de internet: nada de la red
local ni del propio equipo, aunque una ficha lo dijera.
"""

import hashlib
import io
import ipaddress
import os
import socket
import threading
import time
from urllib.parse import urlparse

import requests

try:
    from PIL import Image
except ImportError:                     # sin Pillow: se guarda el original
    Image = None

LADO_MAXIMO = (360, 540)        # basta para la ficha ampliada; las tarjetas la ven más pequeña
CALIDAD_JPEG = 82
MAXIMO_BYTES = 15 * 1024 * 1024  # una portada de más de 15 MB no se descarga
ESPERA = 20                      # segundos sin recibir nada antes de abandonar
ESPERA_TOTAL = 30                # tope de toda la descarga: hay servidores que mandan a cuentagotas
DIAS_FALLO = 7                   # una portada que no se pudo bajar se reintenta pasada una semana

_candados = {}
_candado_general = threading.Lock()


def _candado(clave):
    """Un candado por portada: dos peticiones a la vez no la bajan dos veces."""
    with _candado_general:
        return _candados.setdefault(clave, threading.Lock())


def _servidor_publico(url):
    """¿Es una dirección http(s) de un servidor de internet?"""
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        return False
    try:
        direcciones = {info[4][0] for info in socket.getaddrinfo(partes.hostname, None)}
    except OSError:
        return False
    for direccion in direcciones:
        ip = ipaddress.ip_address(direccion.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _reducir(datos):
    """Miniatura JPEG; None si no es una imagen que Pillow sepa leer."""
    try:
        imagen = Image.open(io.BytesIO(datos))
        imagen.draft("RGB", LADO_MAXIMO)          # los JPEG grandes se leen ya reducidos
        imagen = imagen.convert("RGB")
        imagen.thumbnail(LADO_MAXIMO)
        salida = io.BytesIO()
        imagen.save(salida, "JPEG", quality=CALIDAD_JPEG, optimize=True, progressive=True)
        return salida.getvalue()
    except Exception:                            # noqa: BLE001 (imagen rota o formato raro)
        return None


def miniatura(url, carpeta):
    """Ruta de la miniatura en disco (descargándola si hace falta) o None si
    no se puede conseguir."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    clave = hashlib.sha1(url.encode("utf-8")).hexdigest()
    ruta = os.path.join(carpeta, clave[:2], clave + ".jpg")
    fallo = ruta + ".fallo"
    if os.path.exists(ruta):
        return ruta
    with _candado(clave):
        if os.path.exists(ruta):                 # la ha bajado otra petición mientras se esperaba
            return ruta
        if os.path.exists(fallo) and time.time() - os.path.getmtime(fallo) < DIAS_FALLO * 86400:
            return None
        datos = None
        if _servidor_publico(url):
            try:
                with requests.get(url, timeout=ESPERA, stream=True,
                                  headers={"User-Agent": "Bildumargi (portadas de DILVE)"}) as r:
                    if r.ok and "image" in r.headers.get("Content-Type", "image"):
                        trozos, total, inicio = [], 0, time.time()
                        for trozo in r.iter_content(65536):
                            total += len(trozo)
                            if total > MAXIMO_BYTES or time.time() - inicio > ESPERA_TOTAL:
                                trozos = None
                                break
                            trozos.append(trozo)
                        datos = b"".join(trozos) if trozos else None
            except requests.RequestException:
                datos = None
        if datos and Image is not None:
            datos = _reducir(datos)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        if not datos:
            with open(fallo, "w", encoding="utf-8") as f:
                f.write(url)
            return None
        temporal = ruta + ".tmp"
        with open(temporal, "wb") as f:
            f.write(datos)
        os.replace(temporal, ruta)
        if os.path.exists(fallo):
            os.remove(fallo)
        return ruta
