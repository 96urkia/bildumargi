#!/bin/bash
# Construye el paquete .deb de Bildumargi para la distribución en la que se ejecuta.
#
#   bash packaging/construir_deb.sh 1.1 ubuntu24.04
#
# Debe ejecutarse como root dentro de la distribución de destino (en GitHub
# Actions, en su contenedor oficial): el entorno de Python queda ligado a la
# versión de Python del sistema, así que hace falta un paquete por distribución.
set -euo pipefail

VERSION=${1:?Falta la versión, por ejemplo 1.1}
DISTRO=${2:?Falta la distribución, por ejemplo ubuntu24.04 o deb13}
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
DESTINO=/usr/lib/bildumargi          # el entorno de Python debe crearse en su ruta final
cd "$RAIZ"

# Salvaguarda: el programa se prepara en /usr/lib/bildumargi, así que no puede
# construirse en un equipo que tenga Bildumargi instalado (lo borraría).
if dpkg-query -W -f='${Status}' bildumargi 2>/dev/null | grep -q "install ok installed"; then
    echo "Bildumargi está instalado en este equipo: construye el paquete en otro"
    echo "equipo o en un contenedor (GitHub Actions lo hace así)." >&2
    exit 1
fi

echo "== Programa"
rm -rf "$DESTINO" build
mkdir -p "$DESTINO/app/datos"
cp -a backend frontend config.py conversor.py crear_demo.py iniciar.py \
      README.md VERSION.txt LICENSE AVISO-LICENCIA.md "$DESTINO/app/"
# Solo los ficheros de partida: nada de datos de uso ni de pruebas
cp datos/bibliotecas.xlsx datos/pautas.json "$DESTINO/app/datos/"
[ -f datos/materias_secciones.json ] && cp datos/materias_secciones.json "$DESTINO/app/datos/"
# Encabezados THEMA de EDItEUR, si quien construye los ha dejado en datos/
for f in datos/thema.* datos/thema_*.*; do if [ -f "$f" ]; then cp "$f" "$DESTINO/app/datos/"; fi; done
find "$DESTINO/app" -name "__pycache__" -prune -exec rm -rf {} +

echo "== Python y librerías"
python3 -m venv "$DESTINO/venv"
"$DESTINO/venv/bin/pip" install --quiet --no-cache-dir --upgrade pip
"$DESTINO/venv/bin/pip" install --quiet --no-cache-dir -r requirements.txt
# Compilado de antemano: el programa no necesita escribir en su carpeta
"$DESTINO/venv/bin/python" -m compileall -q "$DESTINO/app" >/dev/null

echo "== Paquete"
mkdir -p build/usr/lib dist
cp -a "$DESTINO" build/usr/lib/
PYDEP="python$("$DESTINO/venv/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
case "$(dpkg --print-architecture)" in
    amd64) ARCH=amd64 ;;
    arm64) ARCH=arm64 ;;
    *) ARCH=$(dpkg --print-architecture) ;;
esac
export VERSION RELEASE="1~${DISTRO}" ARCH PYDEP
nfpm pkg --packager deb --config packaging/nfpm.yaml --target dist/
ls -la dist/*.deb
