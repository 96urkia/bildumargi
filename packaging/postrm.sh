#!/bin/sh
# Después de desinstalar. «apt remove» conserva configuración y datos;
# «apt purge» lo borra todo, datos incluidos.
set -e
if [ "$1" = "purge" ]; then
    rm -f /etc/bildumargi/secretos.env
    rm -rf /var/lib/bildumargi
    if getent passwd bildumargi >/dev/null; then
        deluser --system --quiet bildumargi >/dev/null 2>&1 || true
    fi
fi
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
fi
exit 0
