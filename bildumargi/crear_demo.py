# -*- coding: utf-8 -*-
"""Crea una DEMO de Bildumargi que funciona sin servidor ni instalación.

Pensado para equipos donde no se puede instalar ni ejecutar ningún programa:
la demo es una carpeta que se abre con doble clic en «Abrir Bildumargi.html»,
en Edge o Chrome, igual que un PDF.

Cómo se usa
-----------
1. Arranca Bildumargi normalmente y abre en el navegador:
       http://127.0.0.1:8765/?grabar_demo=1
   Aparece abajo a la izquierda el panel «Grabando la demo».
2. Carga y analiza los listados de la biblioteca (por ejemplo, Monteagudo).
3. Pulsa «Recorrido automático» y espera a que termine: recorre todas las
   pestañas, secciones, fuentes de sugerencias (también las de DILVE) y
   filtros. Puedes pulsar además, a mano, lo que quieras enseñar.
4. Abre «Administración de la red» con tu clave, para que también se grabe.
5. Pulsa «Descargar grabación»: se guarda bildumargi-grabacion.json.
6. Ejecuta este script:
       python crear_demo.py ruta\\a\\bildumargi-grabacion.json
   Crea la carpeta «Bildumargi-demo» y el zip «Bildumargi-demo.zip».

Por defecto la demo va sin portadas: se crea en segundos y en su lugar se ve
el marcador con la inicial del título. Con --con-portadas se descargan y se
guardan dentro de la demo (primero las que aparecen en más pantallas, hasta
1.200; --max-portadas N, 0 = todas), con una caché «portadas-cache» junto a la
grabación para no repetir descargas.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import zipfile
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(RAIZ, "frontend")
NOMBRE_HTML = "Abrir Bildumargi.html"

LEEME = """BILDUMARGI - DEMOSTRACIÓN
=========================

Para abrirla: haga doble clic en «Abrir Bildumargi.html».
Se abrirá en el navegador (Edge o Chrome). No hace falta instalar nada ni
tener conexión: no se ejecuta ningún programa.

Qué incluye: los datos de {biblioteca}, ya analizados. Puede recorrer
Diagnóstico, Secciones, Sugerencias de compra (presencia en la red, autores
más prestados y novedades de DILVE), Red y Seguimiento, pulsar los gráficos,
ampliarlos, cambiar filtros y abrir fichas.

Subir archivos: el asistente de carga funciona igual que en la aplicación
real, pero al pulsar «Analizar» se muestran los resultados ya calculados de
{biblioteca}, sean cuales sean los archivos elegidos.

Administración de la red: se entra con cualquier clave.

Si alguna consulta concreta no se grabó al preparar la demo, aparece un
aviso; en la aplicación real se calcula al momento.

Consejo: si el navegador no deja abrirla desde el USB, copie la carpeta
entera al Escritorio y ábrala desde allí.

Bildumargi es software libre (AGPLv3). Grabación del {fecha}.
"""


def _extension(url, tipo):
    tipo = (tipo or "").lower()
    for clave, ext in (("png", ".png"), ("webp", ".webp"), ("gif", ".gif")):
        if clave in tipo:
            return ext
    if re.search(r"\.(png|webp|gif)(\?|$)", url, re.I):
        return "." + re.search(r"\.(png|webp|gif)", url, re.I).group(1).lower()
    return ".jpg"


def _nombre_portada(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _en_cache(url, cache):
    """Nombre del archivo si esa portada ya se descargó en otra ocasión."""
    base = _nombre_portada(url)
    for ext in (".jpg", ".png", ".webp", ".gif"):
        if os.path.exists(os.path.join(cache, base + ext)):
            return base + ext
    return None


def _descargar(url, cache):
    """Descarga una portada a la caché. Devuelve (url, nombre o None, ¿falló
    la conexión?). Tiempos cortos: una web lenta no puede bloquear la demo."""
    ya = _en_cache(url, cache)
    if ya:
        return url, ya, False
    try:
        import requests
        r = requests.get(url, timeout=(4, 8), headers={"User-Agent": "Bildumargi-demo/1.0"})
        if r.status_code != 200 or not r.content or len(r.content) < 200:
            return url, None, False
        nombre = _nombre_portada(url) + _extension(url, r.headers.get("Content-Type"))
        temporal = os.path.join(cache, nombre + ".parcial")
        with open(temporal, "wb") as f:
            f.write(r.content)
        os.replace(temporal, os.path.join(cache, nombre))     # nunca queda una a medias
        return url, nombre, False
    except Exception:            # noqa: BLE001 — una portada que falla no detiene la demo
        return url, None, True


def _contar_portadas(valor, contador):
    """Cuántas veces aparece cada portada en lo grabado: las más repetidas son
    las que se ven en más pantallas, y se descargan primero."""
    if isinstance(valor, dict):
        for clave, v in valor.items():
            if clave == "cubierta" and isinstance(v, str) and v.startswith("http"):
                contador[v] = contador.get(v, 0) + 1
            else:
                _contar_portadas(v, contador)
    elif isinstance(valor, list):
        for v in valor:
            _contar_portadas(v, contador)


def _quitar_portadas(valor):
    """Sin portadas, se borran las direcciones web de las cubiertas: así la demo
    no intenta conectarse a internet (en un equipo corporativo, cada intento
    podría esperar al proxy) y enseña directamente el marcador con la inicial."""
    if isinstance(valor, dict):
        return {k: (None if k == "cubierta" and isinstance(v, str) and v.startswith("http")
                    else _quitar_portadas(v)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_quitar_portadas(v) for v in valor]
    return valor


def _sustituir_portadas(valor, mapa):
    if isinstance(valor, dict):
        return {k: (mapa.get(v, v) if k == "cubierta" and isinstance(v, str) else _sustituir_portadas(v, mapa))
                for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sustituir_portadas(v, mapa) for v in valor]
    return valor


def _borrar_carpeta(ruta):
    """Borra una carpeta aunque tenga archivos de solo lectura (Windows los
    deja así a veces al extraer un zip). Devuelve False si no se puede, por
    ejemplo porque algún archivo está abierto."""
    def quitar_solo_lectura(funcion, camino, _error):
        try:
            os.chmod(camino, stat.S_IWRITE)
            funcion(camino)
        except OSError:
            raise
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(ruta, onexc=quitar_solo_lectura)
        else:
            shutil.rmtree(ruta, onerror=quitar_solo_lectura)
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(description="Crea una demo de Bildumargi que se abre sin servidor.")
    ap.add_argument("grabacion", help="bildumargi-grabacion.json descargado desde el panel de grabación")
    ap.add_argument("--salida", default=None, help="carpeta de destino (por defecto, Bildumargi-demo junto a la grabación)")
    # Sin portadas por defecto: descargarlas de las webs de las editoriales puede
    # llevar mucho rato (miles de imágenes) y la demo se entiende igual con el
    # marcador que lleva la inicial del título.
    ap.add_argument("--con-portadas", action="store_true",
                    help="descargar las portadas e incluirlas en la demo (tarda)")
    ap.add_argument("--sin-portadas", action="store_true", help=argparse.SUPPRESS)   # compatibilidad
    ap.add_argument("--max-portadas", type=int, default=1200,
                    help="cuántas portadas descargar, empezando por las que más se ven (0 = todas)")
    args = ap.parse_args()

    with open(args.grabacion, encoding="utf-8") as f:
        grabacion = json.load(f)
    if grabacion.get("formato") != "bildumargi-grabacion":
        sys.exit("Ese archivo no es una grabación de Bildumargi.")
    datos = grabacion["datos"]
    biblioteca = grabacion.get("biblioteca") or "la biblioteca"
    fecha = (grabacion.get("fecha") or "")[:10]

    # Comprobaciones: sin estas respuestas la demo quedaría coja
    claves = list(datos)
    avisos = []
    if "POST /api/analizar" not in datos:
        avisos.append("No se grabó el análisis de los listados: activa la grabación ANTES de subirlos.")
    if not any(k.startswith("POST /api/admin/entrar") for k in claves):
        avisos.append("No se grabó la entrada en Administración de la red: el panel de administración no funcionará.")
    if not any(k.startswith("GET /api/sesion/S/sugerencias/autores") for k in claves):
        avisos.append("No hay «Autores más prestados» grabados.")
    if not any(k.startswith("GET /api/sesion/S/sugerencias/novedades") for k in claves):
        avisos.append("No hay «Novedades» grabadas.")

    # La lista completa de ejemplares de cada búsqueda («todas») solo sirve
    # para el botón «Descargar CSV» y ocupa casi todo el peso: en la demo se
    # retira (el botón no aparece) y los datos pasan de decenas de MB a unos 2.
    for clave, valor in datos.items():
        if clave.startswith("GET /api/sesion/S/buscar") and isinstance(valor, dict):
            valor["todas"] = None

    salida = args.salida or os.path.join(os.path.dirname(os.path.abspath(args.grabacion)), "Bildumargi-demo")
    if os.path.exists(salida) and not _borrar_carpeta(salida):
        # Windows no deja borrar la demo anterior (abierta en el navegador, en el
        # Explorador o sincronizándose con OneDrive): se crea otra al lado en
        # vez de pararse.
        anterior = salida
        salida = f"{salida.rstrip(os.sep)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        print(f"No se ha podido borrar la demo anterior ({anterior}):")
        print("  probablemente está abierta en el navegador o en el Explorador.")
        print(f"  Se crea una nueva en: {salida}\n")
    shutil.copytree(FRONTEND, salida)
    os.remove(os.path.join(salida, "index.html"))

    # Portadas dentro de la demo, para verlas sin conexión (solo si se piden)
    if args.con_portadas and not args.sin_portadas:
        veces = {}
        _contar_portadas(datos, veces)
        urls = sorted(veces, key=lambda u: -veces[u])       # las más vistas primero
        if args.max_portadas and len(urls) > args.max_portadas:
            print(f"Hay {len(urls)} portadas; se descargan las {args.max_portadas} que aparecen en más pantallas")
            print("  (para todas: --max-portadas 0; el resto se verá con el marcador).")
            urls = urls[:args.max_portadas]
        if urls:
            # Caché junto a la grabación: lo descargado se conserva aunque se pare
            # con Ctrl+C o se vuelva a crear la demo.
            cache = os.path.join(os.path.dirname(os.path.abspath(args.grabacion)), "portadas-cache")
            os.makedirs(cache, exist_ok=True)
            ya = sum(1 for u in urls if _en_cache(u, cache))
            print(f"Portadas: {len(urls)} ({ya} ya descargadas antes). Se pueden parar con Ctrl+C: "
                  "lo descargado se conserva.")
            mapa, fallos_seguidos, hechas = {}, 0, 0
            sin_conexion = False
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as grupo:
                futuros = [grupo.submit(_descargar, u, cache) for u in urls]
                try:
                    for futuro in concurrent.futures.as_completed(futuros):
                        url, nombre, fallo_red = futuro.result()
                        hechas += 1
                        if nombre:
                            mapa[url] = nombre
                            fallos_seguidos = 0
                        elif fallo_red:
                            fallos_seguidos += 1
                        if hechas % 100 == 0 or hechas == len(urls):
                            print(f"  {hechas} de {len(urls)} · {len(mapa)} guardadas", flush=True)
                        if fallos_seguidos >= 40 and not mapa:
                            sin_conexion = True
                            for otro in futuros:
                                otro.cancel()
                            break
                except KeyboardInterrupt:
                    for otro in futuros:
                        otro.cancel()
                    print("\n  Descarga de portadas interrumpida: se sigue con las que ya hay.")
            if sin_conexion:
                print("  No se puede acceder a las portadas (¿proxy o red sin salida a internet?).")
                print("  Se sigue sin ellas: se verá el marcador con la inicial del título.")
            # Se copian a la demo solo las que se van a usar
            carpeta = os.path.join(salida, "portadas")
            os.makedirs(carpeta, exist_ok=True)
            for url, nombre in list(mapa.items()):
                try:
                    shutil.copy2(os.path.join(cache, nombre), os.path.join(carpeta, nombre))
                    mapa[url] = f"portadas/{nombre}"
                except OSError:
                    del mapa[url]
            datos = _sustituir_portadas(datos, mapa)
            print(f"  {len(mapa)} portadas en la demo; el resto se verá con el marcador.")

    if not args.con_portadas or args.sin_portadas:
        datos = _quitar_portadas(datos)

    # Los datos grabados, como script clásico: desde un archivo local el
    # navegador no deja leer JSON con fetch(), pero sí cargar <script src>.
    with open(os.path.join(salida, "js", "demo-datos.js"), "w", encoding="utf-8") as f:
        f.write("/* Datos de la demostración de Bildumargi, generados por crear_demo.py */\n")
        f.write("window.BILDUMARGI_DEMO_DATOS = ")
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    # Página de entrada: sin «?v=…» (no sirve fuera del servidor) y con los datos
    with open(os.path.join(FRONTEND, "index.html"), encoding="utf-8") as f:
        html = f.read()
    html = re.sub(r'((?:src|href)="[^"?]+)\?v=[^"]*"', r'\1"', html)
    html = html.replace('<script src="js/api.js"></script>',
                        '<script src="js/demo-datos.js"></script>\n<script src="js/api.js"></script>')
    if "demo-datos.js" not in html:
        sys.exit("No se ha podido preparar la página de entrada (¿ha cambiado index.html?).")
    with open(os.path.join(salida, NOMBRE_HTML), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(salida, "LEEME.txt"), "w", encoding="utf-8") as f:
        f.write(LEEME.format(biblioteca=biblioteca, fecha=fecha))

    # Zip listo para el USB, con su huella SHA-256
    destino_zip = salida.rstrip("/\\") + ".zip"
    if os.path.exists(destino_zip):
        try:
            os.remove(destino_zip)
        except OSError:
            destino_zip = f"{salida.rstrip(os.sep)}-{datetime.now().strftime('%H%M%S')}.zip"
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for carpeta, _, ficheros in os.walk(salida):
            for nombre in ficheros:
                ruta = os.path.join(carpeta, nombre)
                z.write(ruta, os.path.relpath(ruta, os.path.dirname(salida)))
    huella = hashlib.sha256(open(destino_zip, "rb").read()).hexdigest()

    tam = os.path.getsize(os.path.join(salida, "js", "demo-datos.js")) / 1_048_576
    print(f"\nDemo creada en: {salida}")
    print(f"  {len(datos)} respuestas grabadas · datos: {tam:.1f} MB")
    print(f"  Zip: {destino_zip}")
    print(f"  SHA-256: {huella}")
    for aviso in avisos:
        print(f"  ATENCIÓN: {aviso}")
    print(f"\nPara probarla: doble clic en «{NOMBRE_HTML}» dentro de la carpeta.")


if __name__ == "__main__":
    main()
