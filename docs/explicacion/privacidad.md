# Datos y privacidad

## Qué datos usa Bildumargi

Los listados de AbsysNet que usa Bildumargi describen **ejemplares**:
signatura, código de barras, título, autor, año y si ha salido en préstamo o
no. **No contienen datos de lectores.**

## Dónde se guardan

Todo se queda en el ordenador (o en el servidor) donde está instalado
Bildumargi. Solo se conecta fuera para:

- **DILVE**, si se activa: se envían ISBN para recibir sus fichas.
- **Las portadas** de los libros, que se piden a las direcciones que da DILVE.
- **Los enlaces** que tú pulsas (Todos tus libros, el buscador de Thema), que
  se abren en el navegador.

## Qué se conserva

- **Historial de cargas**: si está activado, se conservan las últimas N
  cargas, que se pueden borrar desde [Seguimiento](../uso/seguimiento.md).
- **Cuenta de DILVE**: si se escribe en Configuración o en el instalador, se
  guarda en `dilve/credenciales.json`, en la carpeta de datos. Trata las
  copias de esa carpeta como algo privado.

## Seguridad

- En una instalación compartida (un servidor), Bildumargi está pensado para
  una **intranet de confianza**, no para publicarse en internet. Conviene
  poner una [clave de configuración](../administracion/ajustes-avanzados.md#clave-de-configuracion).
