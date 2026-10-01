#!/bin/sh
# /usr/bin/bildumargi — orden única para usar Bildumargi instalado con el paquete .deb
#
#   bildumargi servir               arranca el servidor (lo usa el servicio systemd)
#   bildumargi conversor FICHERO    convierte el MARC21 de la red en la base de datos
#   bildumargi demo GRABACION       crea una demostración sin servidor
#   bildumargi version              muestra la versión instalada
set -e
APP=/usr/lib/bildumargi/app
PY=/usr/lib/bildumargi/venv/bin/python

# Configuración: ajustes generales y, si se puede leer, los secretos
if [ -r /etc/bildumargi/bildumargi.env ]; then set -a; . /etc/bildumargi/bildumargi.env; set +a; fi
if [ -r /etc/bildumargi/secretos.env ]; then set -a; . /etc/bildumargi/secretos.env; set +a; fi
# El programa está en una carpeta del sistema en la que no se escribe
export PYTHONDONTWRITEBYTECODE=1

# Si lo lanza root, se ejecuta como el usuario del servicio: así los ficheros
# que cree en /var/lib/bildumargi siguen perteneciendo a ese usuario.
if [ "$(id -u)" = "0" ] && id bildumargi >/dev/null 2>&1; then
    exec setpriv --reuid=bildumargi --regid=bildumargi --init-groups --reset-env \
        env BILDUMARGI_DATOS="$BILDUMARGI_DATOS" BILDUMARGI_HOST="$BILDUMARGI_HOST" \
            BILDUMARGI_PUERTO="$BILDUMARGI_PUERTO" BILDUMARGI_CLAVE_ADMIN="$BILDUMARGI_CLAVE_ADMIN" \
            BILDUMARGI_DILVE_USUARIO="$BILDUMARGI_DILVE_USUARIO" BILDUMARGI_DILVE_CLAVE="$BILDUMARGI_DILVE_CLAVE" \
            PYTHONDONTWRITEBYTECODE=1 PATH=/usr/bin:/bin \
        "$0" "$@"
fi

orden=${1:-ayuda}
[ $# -gt 0 ] && shift
case "$orden" in
    servir|serve)
        cd "$APP"
        # UN solo proceso: las sesiones viven en memoria y DILVE se actualiza desde él
        exec "$PY" -m uvicorn backend.servidor:app \
            --host "${BILDUMARGI_HOST:-127.0.0.1}" --port "${BILDUMARGI_PUERTO:-8765}" \
            --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 "$@" ;;
    conversor)
        exec "$PY" "$APP/conversor.py" "$@" ;;
    demo)
        exec "$PY" "$APP/crear_demo.py" "$@" ;;
    version|--version)
        cd "$APP"
        exec "$PY" -c "import config; print('Bildumargi', config.VERSION)" ;;
    *)
        echo "Uso: bildumargi {servir|conversor FICHERO|demo GRABACION|version}"
        exit 1 ;;
esac
