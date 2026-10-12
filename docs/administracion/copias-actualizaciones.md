# Copias y actualizaciones

## Dónde están los datos

| Instalación | Carpeta de datos |
|---|---|
| Windows (instalador) | `%LOCALAPPDATA%\Bildumargi\datos` |
| Con Python (zip) | `datos/`, junto al programa |
| Servidor (`.deb`) | `/var/lib/bildumargi` |

## Qué copiar

| Fichero | Por qué |
|---|---|
| `configuracion.json` | Toda la configuración: datos de la biblioteca, apariencia, secciones, DILVE… |
| `bibliotecas/` | El historial de cargas, con los listados de cada una. |
| `dilve/` | Novedades y fichas descargadas. Se pueden volver a descargar, pero lleva llamadas y tiempo. |
| `marc_idiomas.db` | El idioma extraído del catálogo MARC. Se puede volver a extraer si se tiene el `.db`. |

Lo más sencillo es copiar **la carpeta de datos entera**. La cuenta de DILVE
va en `dilve/credenciales.json`: trata la copia como algo privado.

## Actualizar Bildumargi

=== "Windows (instalador)"

    Descarga el instalador de la versión nueva y ejecútalo. Se instala encima
    y conserva los datos.

=== "Servidor (.deb)"

    Descarga el `.deb` de la versión nueva para tu sistema e instálalo igual
    que el primero (ver [Instalar en un servidor Linux](instalar-servidor.md)).
    Ajustes, claves y datos se conservan.

    ```
    cd /tmp
    sudo apt install ./bildumargi*deb13*.deb
    ```

=== "Con Python (zip)"

    Descomprime la versión nueva en otra carpeta y copia en ella la carpeta
    `datos/` de la anterior.

## Pasar de la 1.x a la 2.0

La 2.0 lee los datos de la 1.x y los convierte sola: la primera vez toma del
antiguo `bibliotecas.xlsx` el nombre, la población y la superficie de tu
biblioteca, y conserva su historial de cargas, su configuración y lo
descargado de DILVE. Basta con copiar la carpeta de datos de la 1.x en la de
la 2.0 antes de abrirla.

## Desinstalar

- **Windows**: desde «Agregar o quitar programas». Pregunta si se borran
  también los datos.
- **Servidor**: `sudo apt remove bildumargi` quita el programa y conserva
  ajustes y datos; `sudo apt purge bildumargi` lo borra **todo**, datos
  incluidos.
