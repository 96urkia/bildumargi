#!/bin/sh
# Antes de desinstalar: parar el servicio solo si se elimina, no al actualizar
set -e
if [ "$1" = "remove" ] && [ -d /run/systemd/system ]; then
    systemctl stop bildumargi.service >/dev/null 2>&1 || true
    systemctl disable bildumargi.service >/dev/null 2>&1 || true
fi
exit 0
