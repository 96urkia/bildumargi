# Ajustes avanzados

Ficheros opcionales en la carpeta de datos para adaptar Bildumargi a la red.

## Referencia de fondo por habitante: `pautas.json`

El Diagnóstico compara los documentos por habitante con una referencia. Por
defecto, las **Pautas sobre los servicios de las bibliotecas públicas
(2002)**: de 1,5 a 2,5 documentos por habitante y un fondo mínimo de 2.500.

Una red puede poner la suya, por tramos de población:

```json
{
  "fuente": "Estándar de la red (nombre completo y año)",
  "fuente_corta": "Estándar de la red",
  "tramos": [
    {"hasta_habitantes": 3000,  "docs_hab_min": 3.0, "docs_hab_max": 3.0},
    {"hasta_habitantes": 10000, "docs_hab_min": 2.5, "docs_hab_max": 2.5},
    {"hasta_habitantes": null,  "docs_hab_min": 1.5, "docs_hab_max": 2.5, "fondo_minimo": 2500}
  ]
}
```

Se aplica el primer tramo cuyo `hasta_habitantes` sea mayor o igual que la
población; `null` significa «sin límite».

## Materias y secciones: `materias_secciones.json`

Ajusta cómo se asignan secciones a las novedades a partir de sus materias
Thema:

```json
{"secciones": {"MKM": "6", "WH": "N"}}
```

## Modelo de préstamo: `afinidad.json`

Ajusta los pesos del orden «Afines a lo que más se presta». Compruébalo
después con **Comparar con el histórico**:

```json
{"beta": {"thema": 0.9}, "ventana_anios": 4}
```

## Encabezados Thema: `thema_es.json`

Para ver el nombre de cada materia junto a su código («Novela gráfica · XAM»),
descarga de editeur.org la lista oficial en castellano (JSON o XML), guárdala
como `thema_es.json` y reinicia Bildumargi.

!!! info "Licencia de la lista Thema"
    Si se redistribuye, debe ser el fichero oficial sin modificar.
