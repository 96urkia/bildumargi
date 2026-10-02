# Catálogo colectivo de la red

Con el catálogo colectivo, Bildumargi activa la pestaña **Sugerencias de
compra**, el filtro de idioma y las valoraciones enlazadas a títulos. Sin él,
analiza igualmente la colección propia.

## 1. Genera la base con `conversor.py`

`conversor.py` convierte la exportación MARC del catálogo en una base SQLite:

```
python conversor.py todopublicas.mrc -o datos/base_red.db
```

En el servidor con paquete `.deb`: `sudo bildumargi conversor todopublicas.mrc`.

Admite MARC21 binario (`.mrc`, lo habitual en AbsysNet) y MARCXML, y también
una carpeta con varias exportaciones. Opciones útiles:

| Opción | Para qué |
|---|---|
| `--anio-minimo-marcxml 2015` | Guardar el MARCXML solo desde ese año (por defecto). |
| `--sin-marc` | No guardar el MARCXML: base mucho más ligera. |
| `--sin-fts` | No crear índices de búsqueda por texto. |
| `--codificacion utf-8` | Si el MARC binario no viene en ISO-8859-1. |

**Tamaño orientativo** con 500.000 registros: unos 2,1 GB con el MARCXML
completo y unos 850 MB sin él.

!!! warning "El campo 952"
    El conversor espera los datos del ejemplar en los subcampos del 952 que usa
    AbsysNet. Si al terminar avisa de que no ha leído ningún ejemplar, el mapeo
    no corresponde: las constantes están al principio de `conversor.py`.

## 2. Indica dónde está la base

En `config.py`, la variable `URL_BASE_DATOS`, o la variable de entorno
`BILDUMARGI_DB_URL`. Admite un fichero local o una descarga directa:

```python
URL_BASE_DATOS = "datos/base_red.db"
URL_BASE_DATOS = "https://www.dropbox.com/scl/fi/xxx/base.db?dl=1"
```

Con Dropbox, el enlace debe terminar en `?dl=1`.

## 3. Actualiza la base periódicamente

Regenera la base cuando quieras reflejar el fondo actual de la red (por
ejemplo, cada meso anualmente). Las valoraciones de las bibliotecas no se pierden: están
en otro fichero (`valoraciones.db`). 

!!! warning "Idiomas"
Además de para generar recomendaciones, la base de datos permite extraer el **idioma**
de los ejemplares, a través del campo 008 de MARC21. Sin vincularla, el **filtro de idioma**
no funciona adecuadamente en el análisis de la colección. 


