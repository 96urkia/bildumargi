#!/bin/sh
# Después de instalar o actualizar Bildumargi
set -e

# Usuario del servicio, sin acceso al sistema (se crea una sola vez)
if ! getent passwd bildumargi >/dev/null; then
    adduser --system --group --home /var/lib/bildumargi --no-create-home \
            --shell /usr/sbin/nologin --quiet bildumargi
fi
install -d -o bildumargi -g bildumargi -m 0750 /var/lib/bildumargi

# Claves: el fichero se crea una sola vez, con una clave de administración
# aleatoria, y nunca se sobrescribe en las actualizaciones.
if [ ! -f /etc/bildumargi/secretos.env ]; then
    umask 077
    CLAVE=$(head -c 24 /dev/urandom | base64 | tr -d '/+=')
    cat > /etc/bildumargi/secretos.env <<FIN
# Claves de Bildumargi. Solo las lee el administrador del sistema (permisos 600).
# Tras cambiarlas: sudo systemctl restart bildumargi
BILDUMARGI_CLAVE_ADMIN=$CLAVE
BILDUMARGI_DILVE_USUARIO=
BILDUMARGI_DILVE_CLAVE=
FIN
    chmod 0600 /etc/bildumargi/secretos.env
    echo "Bildumargi: clave de administración creada en /etc/bildumargi/secretos.env"
fi

# Servicio: se activa y se (re)arranca si el sistema usa systemd
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable bildumargi.service >/dev/null 2>&1 || true
    systemctl restart bildumargi.service || true
fi
exit 0
