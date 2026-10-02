# Administración de la red

La administración decide lo que vale para **todas las bibliotecas**. Se entra
desde el pie de la configuración (la rueda dentada), con la clave de
administración.

!!! example "Captura pendiente"
    `img/administracion-red.png`

## La clave de administración

Se fija en `config.py` (`CLAVE_ADMIN`) o en la variable de entorno
`BILDUMARGI_CLAVE_ADMIN`. El paquete `.deb` la genera sola en
`/etc/bildumargi/secretos.env`. Sin clave, la administración queda desactivada
y todo está activo.

No hay recuperación por correo: si se olvida, se pone otra en ese fichero y se
reinicia Bildumargi. El acceso dura dos horas.

## Qué se decide aquí

- **Pestañas que existen** para todas las bibliotecas. Por ejemplo, quitar
  «Red» si la red no quiere comentarios entre bibliotecas.
- **Idiomas que se ofrecen** y el idioma, tema y paleta de partida.
- **Historial de cargas**: si se guardan los listados de cada carga y cuántas
  se conservan por biblioteca (12 por defecto). Es necesario para
  Seguimiento y para el acceso con clave.
- **Tabla de secciones por signatura de la red**: la usan las bibliotecas
  que no tengan una propia. Funciona igual que la de cada biblioteca (ver
  [Configuración de la biblioteca](../uso/configuracion.md#secciones-por-signatura)).
- **Novedades del libro español (DILVE)**: credenciales, ventana de meses,
  cuota diaria y pausas (ver [DILVE](dilve.md)).
- Si se muestran los títulos **sugeridos por la editorial**.
