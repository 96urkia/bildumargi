#!/bin/bash
# Construye el zip de siempre (Windows y cualquier sistema con Python).
#
#   bash packaging/construir_zip.sh 1.1
set -euo pipefail
VERSION=${1:?Falta la versión, por ejemplo 1.1}
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
cd "$RAIZ"
NOMBRE="bildumargi-$VERSION"
TEMPORAL=$(mktemp -d)
mkdir -p "$TEMPORAL/$NOMBRE/datos" dist
cp -a backend frontend config.py conversor.py crear_demo.py iniciar.py iniciar.bat iniciar.sh \
      requirements.txt README.md VERSION.txt LICENSE AVISO-LICENCIA.md .gitignore "$TEMPORAL/$NOMBRE/"
# Solo los ficheros de partida: nada de datos de uso ni de pruebas
cp datos/bibliotecas.xlsx datos/pautas.json "$TEMPORAL/$NOMBRE/datos/"
[ -f datos/materias_secciones.json ] && cp datos/materias_secciones.json "$TEMPORAL/$NOMBRE/datos/"
# Encabezados THEMA de EDItEUR, si quien construye los ha dejado en datos/
for f in datos/thema.* datos/thema_*.*; do if [ -f "$f" ]; then cp "$f" "$TEMPORAL/$NOMBRE/datos/"; fi; done
find "$TEMPORAL/$NOMBRE" -name "__pycache__" -prune -exec rm -rf {} +
( cd "$TEMPORAL" && zip -qr "$RAIZ/dist/$NOMBRE.zip" "$NOMBRE" )
rm -rf "$TEMPORAL"
ls -la "dist/$NOMBRE.zip"
