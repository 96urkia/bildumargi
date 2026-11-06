# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller: Bildumargi como aplicación de Windows, con Python y
# todas las librerías dentro (no hace falta instalar nada más).
#
#   python -m PyInstaller packaging/windows/bildumargi.spec --noconfirm \
#          --distpath build/windows/dist --workpath build/windows/trabajo
#
# Lo usa packaging/windows/construir.ps1, que después crea el instalador.
# config_local.py NO entra: las claves de cada ordenador no se reparten.
import os
import re

from PyInstaller.utils.hooks import collect_submodules

RAIZ = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

datos = [
    (os.path.join(RAIZ, "frontend"), "frontend"),
    (os.path.join(RAIZ, "datos", "pautas.json"), "datos"),
    (os.path.join(RAIZ, "datos", "codigos_postales.csv"), "datos"),
    (os.path.join(RAIZ, "datos", "euskera_navarra.csv"), "datos"),
    (os.path.join(RAIZ, "LICENSE"), "."),
    (os.path.join(RAIZ, "AVISO-LICENCIA.md"), "."),
    (os.path.join(RAIZ, "VERSION.txt"), "."),
]
if os.path.exists(os.path.join(RAIZ, "datos", "materias_secciones.json")):
    datos.append((os.path.join(RAIZ, "datos", "materias_secciones.json"), "datos"))

analisis = Analysis(
    [os.path.join(RAIZ, "escritorio.py")],
    pathex=[RAIZ],
    datas=datos,
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("backend") + ["config"],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "pytest", "IPython"],
    noarchive=False,
)
# Los datos de versión del .exe salen de config.py, para que nunca se queden atrás.
with open(os.path.join(RAIZ, "config.py"), encoding="utf-8") as f:
    VERSION = re.search(r'^VERSION = "(.+)"', f.read(), re.M).group(1)
numeros = (VERSION.split(".") + ["0"] * 4)[:4]
with open(os.path.join(SPECPATH, "version.txt"), encoding="utf-8") as f:
    datos_version = f.read().replace("@NUMEROS@", ", ".join(numeros)).replace("@VERSION@", VERSION)
os.makedirs(workpath, exist_ok=True)
fichero_version = os.path.join(workpath, "version-exe.txt")
with open(fichero_version, "w", encoding="utf-8") as f:
    f.write(datos_version)

pyz = PYZ(analisis.pure)
exe = EXE(
    pyz,
    analisis.scripts,
    [],
    exclude_binaries=True,
    name="Bildumargi",
    icon=os.path.join(SPECPATH, "bildumargi.ico"),
    console=False,          # aplicación de ventana, sin consola negra
    version=fichero_version,
)
coleccion = COLLECT(exe, analisis.binaries, analisis.datas, name="Bildumargi")
