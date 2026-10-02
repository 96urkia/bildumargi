# Indicadores

Definiciones de los datos que muestra Bildumargi.

| Indicador | Definición | Fuente |
|---|---|---|
| **Volúmenes** | Número de ejemplares. | Topográfico |
| **Documentos por habitante** | Volúmenes / población atendida. Se compara con la referencia de `pautas.json`. | Topográfico y directorio |
| **Documentos por m²** | Volúmenes / superficie útil. «N/D» si no hay superficie. | Topográfico y directorio |
| **Índice de circulación** | Ejemplares prestados al menos una vez en el periodo / volúmenes. | Topográfico y no prestados |
| **Editado en los últimos 5 años** | Porcentaje de volúmenes con año de edición en los cinco últimos años. | Catálogo |
| **Año medio de edición** | Media de los años de edición conocidos. | Catálogo |
| **Peso de una sección** | Volúmenes de la sección / volúmenes totales. | Topográfico |
| **Uso relativo** | Parte de los ejemplares prestados que corresponde a la sección / parte de los volúmenes. 1,0 = rinde lo que pesa. | Topográfico y no prestados |
| **Alta demanda** | Títulos que figuran en el listado de más prestados. | Más prestados |

!!! info "Antigüedad"
    La antigüedad se calcula con el **año de edición**, no con la fecha de
    adquisición, que no viene en los listados.

!!! info "Préstamo"
    El préstamo procede de los listados de AbsysNet (prestado o no, y alta
    demanda) en el periodo con que se exportaron. El uso relativo usa
    **prestado sí/no**, no el número de préstamos.
