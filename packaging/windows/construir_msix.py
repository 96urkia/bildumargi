# -*- coding: utf-8 -*-
"""Crea el paquete MSIX de Microsoft Store a partir de la carpeta de PyInstaller.

    python packaging/windows/construir_msix.py

Hace falta haber construido antes build/windows/dist/Bildumargi y tener el SDK
de Windows (makeappx.exe). El paquete sale sin firmar: lo firma Microsoft al
certificarlo en la Store. Sin firma no se puede instalar con doble clic.

Con --sin-empaquetar prepara la carpeta y no llama a makeappx.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
SALIDA = os.path.join(RAIZ, "build", "windows")

# Nombre del fichero: (ancho, alto). Sin sufijos de escala, que requieren resources.pri.
LOGOS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
}


def version():
    """La de config.py, con los cuatro números de MSIX y el último a 0 (lo pide la Store)."""
    with open(os.path.join(RAIZ, "config.py"), encoding="utf-8") as f:
        texto = re.search(r'^VERSION = "(.+)"', f.read(), re.M).group(1)
    return texto, ".".join((texto.split(".") + ["0"] * 3)[:3] + ["0"])


def crear_logos(destino):
    os.makedirs(destino, exist_ok=True)
    with Image.open(os.path.join(AQUI, "bildumargi.png")) as original:
        original = original.convert("RGBA")
        for nombre, (ancho, alto) in LOGOS.items():
            lado = min(ancho, alto)
            icono = original.resize((lado, lado), Image.LANCZOS)
            lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
            lienzo.paste(icono, ((ancho - lado) // 2, (alto - lado) // 2), icono)
            lienzo.save(os.path.join(destino, nombre))


def buscar_makeappx():
    kits = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidatos = glob.glob(os.path.join(kits, "Windows Kits", "10", "bin", "10.*", "x64", "makeappx.exe"))
    if not candidatos:
        sys.exit("No se encuentra makeappx.exe: instala el SDK de Windows.")
    return sorted(candidatos)[-1]


def main():
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--sin-empaquetar", action="store_true")
    args = opciones.parse_args()

    texto, numeros = version()
    programa = os.path.join(SALIDA, "dist", "Bildumargi")
    if not os.path.isfile(os.path.join(programa, "Bildumargi.exe")):
        sys.exit("Falta build/windows/dist/Bildumargi: ejecuta antes PyInstaller.")

    carpeta = os.path.join(SALIDA, "msix")
    shutil.rmtree(carpeta, ignore_errors=True)
    shutil.copytree(programa, carpeta)
    crear_logos(os.path.join(carpeta, "Assets"))
    with open(os.path.join(AQUI, "msix", "AppxManifest.xml"), encoding="utf-8") as f:
        manifiesto = f.read().replace("@VERSION@", numeros)
    with open(os.path.join(carpeta, "AppxManifest.xml"), "w", encoding="utf-8") as f:
        f.write(manifiesto)

    if args.sin_empaquetar:
        print(f"Carpeta lista: {carpeta} (versión {numeros})")
        return
    paquete = os.path.join(SALIDA, f"Bildumargi-{texto}.msix")
    subprocess.run([buscar_makeappx(), "pack", "/d", carpeta, "/p", paquete, "/o"], check=True)
    print(f"Listo: {paquete}")


if __name__ == "__main__":
    main()
