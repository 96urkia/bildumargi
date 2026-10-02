# Instalar en un ordenador

Para Windows, Linux o macOS, con el zip.

## 1. Instala Python

Hace falta **Python 3.10 o superior**. Para comprobar si ya lo tienes, abre
una terminal (en Windows, «Símbolo del sistema») y escribe:

```
python --version
```

Si no lo tienes, descárgalo de [python.org](https://www.python.org/downloads/).
En Windows, marca la casilla **«Add Python to PATH»** durante la instalación.

## 2. Descarga y descomprime Bildumargi

Descarga `bildumargi-1.1.zip` de la
[página de versiones](https://github.com/96urkia/bildumargi/releases) y
descomprímelo en una carpeta, por ejemplo `C:\Bildumargi`.

## 3. Instala las librerías

Desde la carpeta de Bildumargi:

```
pip install -r requirements.txt
```

## 4. Arranca

=== "Windows"

    Doble clic en `iniciar.bat`.

=== "Linux y macOS"

    ```
    ./iniciar.sh
    ```

=== "Cualquier sistema"

    ```
    python iniciar.py
    ```

Se abre el navegador en `http://127.0.0.1:8000`. Para parar Bildumargi, pulsa
++ctrl+c++ en la terminal o ciérrala.

!!! example "Captura pendiente"
    `img/arranque-windows.png`: la ventana de la terminal con la dirección.

## Siguiente paso

Rellena el [directorio de bibliotecas](directorio.md) con, al menos, tu
biblioteca.
