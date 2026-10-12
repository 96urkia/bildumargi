# Catálogo MARC (idioma)

Los listados de AbsysNet no traen el **idioma** de los ejemplares. Bildumargi
lo combina de tres fuentes (ver [El idioma de cada ejemplar](../explicacion/idioma.md)):
DILVE describe bien las novedades, pero no tiene muchos libros antiguos o
descatalogados; el **catálogo MARC** los describe casi todos. Combinados, se
conoce el idioma de casi todo el fondo.

!!! example "Con el fondo de una biblioteca pequeña"
    Solo con DILVE, idioma conocido en el **45 %** de los ejemplares. Con DILVE
    y el catálogo MARC, en el **99 %**.

## 1. Consigue el `.db` del catálogo

Bildumargi lee el catálogo en un fichero `.db` generado con `conversor.py`,
que viene con Bildumargi. Puede ser:

- **el de tu red**, si la red ya lo genera para sus bibliotecas;
- **el de tu propio catálogo**: en AbsysNet, exporta tus registros en MARC21
  (`.mrc`) y conviértelos:

```
python conversor.py exportacion.mrc --sin-marc --sin-fts
```

Con `--sin-marc --sin-fts` la base es ligera: solo hace falta para el idioma.
En un servidor con el paquete `.deb`: `sudo bildumargi conversor exportacion.mrc`.

??? info "Más opciones de conversor.py"
    Admite MARC21 binario (`.mrc`, lo habitual en AbsysNet) y MARCXML, y
    también una carpeta con varias exportaciones.

    | Opción | Para qué |
    |---|---|
    | `-o ruta.db` | Dónde guardar la base. |
    | `--sin-marc` | No guardar el MARCXML: base mucho más ligera. |
    | `--sin-fts` | No crear índices de búsqueda por texto. |
    | `--codificacion utf-8` | Si el MARC binario no viene en ISO-8859-1. |

    El conversor espera los datos del ejemplar en los subcampos del **952**
    que usa AbsysNet. Si al terminar avisa de que no ha leído ningún ejemplar,
    el mapeo no corresponde: las constantes están al principio de
    `conversor.py`.

## 2. Extrae los idiomas

En [Configuración](../uso/configuracion.md), apartado **Catálogo MARC
(idioma)**, escribe la ruta del `.db` y pulsa **Extraer los idiomas** (hace
falta tener un análisis abierto).

Bildumargi reconoce tu biblioteca en el `.db` por los códigos de barras y
copia **solo el idioma de tus ejemplares** a un fichero pequeño
(`marc_idiomas.db`, unos cientos de KB). Si el `.db` es el de la red, guarda
además los libros de la red de tus autores, que sirven para
[completar las series](../uso/series.md#completar-las-series).

Después, el `.db` grande ya no hace falta. Si lo indicaste al instalar, la
extracción se hace sola en el primer análisis.

## 3. Actualízalo de vez en cuando

Si el `.db` se actualiza (por ejemplo, cada mes o cada año), el apartado lo
avisa: pulsa otra vez **Extraer los idiomas**. **Dejar de usar el MARC**
borra solo el fichero pequeño extraído.
