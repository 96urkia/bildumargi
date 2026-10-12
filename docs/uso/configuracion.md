# Configuración

El botón de la **rueda dentada**, arriba a la derecha, abre la configuración.
Es una sola, la de tu biblioteca, ordenada en apartados con un **menú a la
izquierda**. Los cambios se guardan con **Guardar**; si cierras sin guardar,
se deshacen.

!!! note "Captura pendiente"
    `img/configuracion.png` — Configuración: el menú lateral a la izquierda y
    el apartado «Tu biblioteca» abierto.

## Tu biblioteca

- **Nombre** de la biblioteca.
- **Red a la que pertenece** (opcional): aparece en la cabecera.
- **Habitantes atendidos**: para los documentos por habitante.
- **Superficie útil (m²)**: para los documentos por m².
- **Sucursal de los listados**: la apunta Bildumargi en la primera carga y
  avisa si llegan listados de otra. **Olvidar la sucursal** sirve si cambias
  de biblioteca.

## Apariencia e idioma

- **Idioma**: castellano, euskera, catalán, gallego o inglés. Se traducen
  también los nombres de sección y el informe.
- **Tema**: oscuro o claro.
- **Colores de los gráficos**: tres paletas, todas legibles con las formas más
  comunes de daltonismo. «Azules» sirve para imprimir en blanco y negro.

Los cambios de tema y colores se ven al momento.

## Pestañas

Ocultar las que no uses y elegir con cuál se abre Bildumargi.

## Historial de cargas

Si se guardan los listados de cada carga (necesario para
[Seguimiento](seguimiento.md), las altas y bajas y **Abrir el último
análisis**) y cuántas cargas se conservan.

## Secciones por signatura

Esta tabla dice a qué sección del análisis va cada signatura según **cómo
empieza**. Tiene dos columnas, **Empieza por** y **Sección**:

| Empieza por | Sección |
|---|---|
| `N` | Ficción / Narrativa |
| `I 1` | I 1 - Filosofía |
| `EUS` | Euskera |
| `VIA` | Viajes |

Por defecto trae la clasificación habitual. Puedes **añadir**, **cambiar** o
**quitar** filas:

- Basta con el principio: `N` abarca `N GRE cie`, `N ARA pat`…
- Gana el comienzo **más largo**: `I EUS` antes que `I`.
- Un prefijo con letras no se corta a mitad de palabra: `C` no se lleva
  `CUA 12`.
- Un prefijo numérico sigue la CDU: `8` incluye `821`.
- Una sección cuenta como **infantil** si empieza por `I` o `JN`, o si su
  nombre dice «infantil» o «juvenil».

Al guardar, el fondo se reclasifica al momento, sin volver a subir los
ficheros. **Volver a la tabla estándar** recupera la de partida.

!!! info "Solo afecta al análisis"
    La tabla cambia Diagnóstico, Secciones, Seguimiento e Informe. Las
    sugerencias de compra siguen usando las secciones estándar, que son las que
    se pueden cruzar con las materias de DILVE.

## Novedades del libro español (DILVE)

La cuenta de DILVE, la descarga de novedades y el freno de llamadas. Ver
[DILVE](../administracion/dilve.md).

## Fichas de DILVE de todo el catálogo

La descarga de las fichas de tu catálogo, con el aviso de cuántas llamadas
supone. Ver [DILVE](../administracion/dilve.md#fichas-de-todo-el-catalogo).

## Catálogo MARC (idioma)

La ruta del `.db` del catálogo del que se toma el idioma de los ejemplares.
Ver [Catálogo MARC](../administracion/catalogo-marc.md).

## Series ocultas

Las colecciones que se marcaron como «no es una serie», con **Volver a
mostrar** (ver [Series](series.md)).

!!! tip "Clave de configuración"
    En una instalación compartida (un servidor), se puede poner una clave para
    que solo quien la sepa cambie la configuración. Ver
    [Ajustes avanzados](../administracion/ajustes-avanzados.md).
