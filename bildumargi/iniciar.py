# -*- coding: utf-8 -*-
"""
Bildumargi · Arranque
=====================

Ejecuta este fichero para poner la aplicación en marcha:

    python iniciar.py

Se abrirá el navegador en http://127.0.0.1:8000. Para pararla, cierra esta
ventana o pulsa Ctrl+C.

Creado por: Asier Urkia · bildumargi@gmail.com
"""

import os
import socket
import sys
import threading
import webbrowser

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)


def comprobar_dependencias():
    faltan = []
    for modulo, paquete in (("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
                            ("openpyxl", "openpyxl"), ("multipart", "python-multipart")):
        try:
            __import__(modulo)
        except ImportError:
            faltan.append(paquete)
    if faltan:
        print("\nFaltan estas librerías:", ", ".join(faltan))
        print("Instálalas con:\n")
        print(f"    {os.path.basename(sys.executable)} -m pip install -r requirements.txt\n")
        sys.exit(1)


def puerto_ocupado(host, puerto):
    """True si ya hay algo escuchando en ese puerto.

    Importa más de lo que parece: si queda abierta la ventana de una ejecución
    anterior, uvicorn no puede arrancar, pero el navegador se abre igualmente
    contra la dirección de siempre y muestra la aplicación VIEJA que sigue
    respondiendo. Parece que la actualización no ha surtido efecto cuando lo
    que ocurre es que nunca llegó a ejecutarse."""
    prueba = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex((prueba, puerto)) == 0


def main():
    comprobar_dependencias()

    import uvicorn
    import config

    direccion = "127.0.0.1" if config.HOST in ("0.0.0.0", "127.0.0.1") else config.HOST
    url = f"http://{direccion}:{config.PUERTO}"

    print("=" * 62)
    print(f"  Bildumargi {config.VERSION}")
    print("=" * 62)
    print(f"  Carpeta: {RAIZ}")
    print(f"  Abriendo {url}")
    if config.HOST == "0.0.0.0":
        print("  Accesible también desde otros equipos de la red local.")
    if not config.url_base_datos():
        print("  Sin base de datos enlazada: las recomendaciones de compra")
        print("  quedan ocultas. Ver el apartado 1 del README.")
    print("  Para parar la aplicación: Ctrl+C")
    print("=" * 62)

    if puerto_ocupado(config.HOST, config.PUERTO):
        print()
        print("  NO SE HA PODIDO ARRANCAR")
        print(f"  El puerto {config.PUERTO} ya está ocupado, casi siempre porque hay")
        print("  otra ventana de Bildumargi abierta. Ciérrala y vuelve a intentarlo.")
        print()
        print("  Si no la encuentras, cambia PUERTO en config.py (por ejemplo, 8001).")
        print()
        print("  No se abre el navegador a propósito: lo que verías sería la versión")
        print("  que ya estaba en marcha, no esta.")
        print()
        try:
            input("  Pulsa Intro para cerrar. ")
        except EOFError:
            pass
        sys.exit(1)

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("backend.servidor:app", host=config.HOST, port=config.PUERTO,
                log_level="warning")


if __name__ == "__main__":
    main()
