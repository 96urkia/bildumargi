# Copias y actualizaciones

## Qué copiar

La carpeta de datos contiene todo lo que no se puede regenerar. Lo esencial:

| Fichero | Por qué |
|---|---|
| `valoraciones.db` | Valoraciones y comentarios de toda la red. **No se puede reconstruir.** |
| `bibliotecas.xlsx` | El directorio, con las claves. |
| `configuracion_red.json` | La configuración de la red. |
| `bibliotecas/` | Preferencias e historial de cargas de cada biblioteca. |
| `dilve/` | Novedades y fichas descargadas (se pueden volver a descargar, pero lleva tiempo). |

La base del catálogo (`base_red.db`) se regenera con `conversor.py`.

## Actualizar Bildumargi

=== "Servidor (.deb)"

    Descarga el `.deb` de la versión nueva para tu sistema e instálalo igual
    que el primero (ver [Instalar en un servidor Linux](instalar-servidor.md)).
    Ajustes, claves y datos se conservan.

    ```
    cd /tmp
    sudo apt install ./bildumargi*deb13*.deb
    ```

=== "Ordenador (zip)"

    Descomprime la versión nueva en otra carpeta y copia en ella la carpeta
    `datos/` de la anterior.

## Desinstalar

- `sudo apt remove bildumargi`: quita el programa y conserva ajustes y datos.
- `sudo apt purge bildumargi`: lo borra **todo**, datos incluidos.
