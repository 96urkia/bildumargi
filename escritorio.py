# -*- coding: utf-8 -*-
"""Bildumargi como aplicación de escritorio.

Es lo que abre el acceso directo del instalador de Windows (ver
packaging/windows). Arranca el servidor de Bildumargi por dentro, en un
puerto libre y solo para este ordenador, y lo enseña en su propia ventana
(WebView2, el motor de Edge que trae Windows). Al cerrar la ventana se cierra
todo. Si la ventana propia no se puede abrir, se usa el navegador.

Los datos van en la carpeta del usuario de Windows,
%LOCALAPPDATA%\\Bildumargi\\datos, para que una versión nueva no los toque.

Creado por: Asier Urkia · bildumargi@gmail.com
Licencia: AGPLv3 (ver LICENSE)
"""

import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


def carpeta_datos():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Bildumargi", "datos")


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def responde(url):
    try:
        with urllib.request.urlopen(url + "/api/config", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def abrir_ventana(url, datos):
    """La ventana propia. Devuelve False si no se ha podido abrir."""
    try:
        import webview
    except ImportError:
        return False
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True                 # CSV, grabación de la demo
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # EDItEUR, Todos tus libros…
        webview.create_window("Bildumargi", url, width=1440, height=900, min_size=(960, 640))
        # Carpeta propia del navegador interno: guarda el tema y lo demás
        # que la aplicación recuerda en el navegador entre una vez y otra.
        webview.start(private_mode=False, storage_path=os.path.join(datos, "ventana"))
        return True
    except Exception as exc:                                    # noqa: BLE001
        print(f"No se ha podido abrir la ventana propia: {exc}")
        return False


def main():
    datos = os.environ.setdefault("BILDUMARGI_DATOS", carpeta_datos())
    os.makedirs(datos, exist_ok=True)
    # Sin consola (aplicación de ventana), los mensajes van a un fichero
    if sys.stdout is None or sys.stderr is None or getattr(sys, "frozen", False):
        registro = open(os.path.join(datos, "registro.txt"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = registro
        print(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # ¿Ya está abierto? Se abre otra ventana sobre el mismo servidor
    fichero = os.path.join(datos, "en_marcha.json")
    try:
        with open(fichero, encoding="utf-8") as f:
            previo = json.load(f).get("url")
    except (OSError, ValueError):
        previo = None
    if previo and responde(previo):
        if not abrir_ventana(previo, datos):
            webbrowser.open(previo)
        return

    import uvicorn

    import config
    from backend import servidor

    puerto = puerto_libre()
    url = f"http://127.0.0.1:{puerto}"
    servidor_web = uvicorn.Server(uvicorn.Config(servidor.app, host="127.0.0.1", port=puerto,
                                                 log_config=None, access_log=False))
    hilo = threading.Thread(target=servidor_web.run, daemon=True, name="servidor")
    hilo.start()
    for _ in range(200):                                       # hasta 20 segundos
        if servidor_web.started:
            break
        time.sleep(0.1)
    print(f"Bildumargi {config.VERSION} en {url} · datos en {datos}")
    with open(fichero, "w", encoding="utf-8") as f:
        json.dump({"url": url, "pid": os.getpid()}, f)

    try:
        if not abrir_ventana(url, datos):
            # Sin ventana propia: el navegador, y el servidor sigue en marcha
            webbrowser.open(url)
            hilo.join()
    finally:
        servidor_web.should_exit = True
        try:
            os.remove(fichero)
        except OSError:
            pass


if __name__ == "__main__":
    main()
