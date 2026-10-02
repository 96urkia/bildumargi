# DILVE

DILVE es la base de datos del libro en venta en España, que alimentan las
editoriales. Bildumargi la usa para las **Novedades** y para **Autores más
prestados**.

## Solicitar el acceso

El uso para bibliotecas es **gratuito**, pero hay que solicitarlo a la
Federación de Gremios de Editores de España (FGEE), que asigna un usuario y
una contraseña a la red.

## Configurar

En [Administración de la red](panel-red.md), apartado «Novedades del libro
español»:

- **Credenciales.** Lo más seguro es ponerlas en el servidor, en
  `BILDUMARGI_DILVE_USUARIO` y `BILDUMARGI_DILVE_CLAVE` (en el `.deb`, en
  `/etc/bildumargi/secretos.env`). También se pueden escribir en el panel: se
  comprueban antes de guardarlas.
- **Ventana**: cuántos meses de novedades se guardan (3 por defecto). Se
  actualiza sola cada 7 días.
- **Solo papel**: opcional.

## Uso prudente

Un volumen alto de llamadas puede hacer que DILVE bloquee la cuenta.
Bildumargi lo limita:

- **Nada se pide dos veces**: todo lo descargado se guarda.
- **Cuota diaria y pausa**: 300 llamadas al día y 6 segundos entre llamadas
  por defecto.
- **Contraseña incorrecta**: deja de llamar en el acto y lo avisa.
- **Acceso denegado** (error 1120): deja de llamar. Escribe a
  `asistencia@dilve.es` y, cuando lo restablezcan, pulsa **Desbloquear**.

!!! warning "Cubiertas y resúmenes"
    Las condiciones de uso de DILVE son suyas. Antes de mostrar cubiertas o
    resúmenes fuera del personal de la biblioteca, confírmalo por escrito con
    la FGEE.
