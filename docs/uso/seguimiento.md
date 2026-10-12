# Seguimiento

La pestaña **Seguimiento** muestra cómo evoluciona tu fondo análisis a
análisis. Aparece si el historial de cargas está activado (lo está por
defecto; se cambia en [Configuración](configuracion.md)).

## Evolución

- La evolución de **volúmenes**, **circulación**, **fondo de los últimos 5
  años** y **año medio de edición**, carga a carga.
- El cambio respecto a la carga anterior.

Las cargas sin listado de no prestados no tienen dato de circulación y no se
dibujan en esa serie.

## Altas y bajas

Bildumargi compara el topográfico de cada carga con el de la anterior, por
código de barras:

- **Alta**: un ejemplar que está ahora y no estaba antes.
- **Baja**: un ejemplar que estaba antes y ya no está: expurgo, pérdida o
  traslado.

El panel **Altas y bajas** enseña las secciones con más movimiento y la lista
de ejemplares (signatura, título, sección y localización), con un botón para
descargarla en CSV. La tabla de cargas guardadas lleva además dos columnas,
**Altas** y **Bajas**.

!!! warning "Exporta siempre igual"
    Si los dos topográficos se exportaron con criterios distintos (otras
    localizaciones, por ejemplo), saldrán diferencias que no son altas ni
    bajas.

!!! info "Volúmenes y altas no siempre cuadran"
    «Volúmenes» cuenta los ejemplares que tienen ficha en el **catálogo**
    exportado; las altas y bajas comparan los **topográficos**. Si un día el
    catálogo sale incompleto, los volúmenes bajan aunque no haya bajas.

## Reabrir o borrar una carga

Desde la lista puedes **reabrir** una carga anterior sin subir los ficheros, o
**borrarla**. Se conservan las últimas 12 (se cambia en
[Configuración](configuracion.md)).

!!! tip "Para que la serie sea comparable"
    Exporta siempre los mismos listados, con el mismo periodo de préstamo, y
    repite el análisis con una frecuencia fija (por ejemplo, cada trimestre).
