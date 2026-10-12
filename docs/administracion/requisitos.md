# Requisitos y modos de uso

Bildumargi 2.0 está pensado para que **cada biblioteca** lo instale y lo use
por su cuenta, con sus datos, su configuración y su cuenta de DILVE.

## Modos de uso

| | **Instalador de Windows** | **Con Python (zip)** | **Servidor Linux (.deb)** |
|---|---|---|---|
| Para | Lo habitual: un ordenador de la biblioteca | Linux, macOS, o Windows con Python | Varios ordenadores de la biblioteca a la vez |
| Instalación | Doble clic, sin permisos de administrador | Python 3.10+ y `pip` | `apt`, como servicio |
| Se abre | En su propia ventana, desde el escritorio | En el navegador | En el navegador, desde la intranet |
| Guía | [Instalar en Windows](instalar-windows.md) | [Instalar con Python](instalar-ordenador.md) | [Instalar en un servidor Linux](instalar-servidor.md) |

Bildumargi **no necesita estar publicado en internet** ni salida a internet
para analizar la colección. Solo se conecta fuera para DILVE, y para las
portadas de los libros.

## Requisitos

- **Windows**: Windows 10 u 11 de 64 bits. El instalador trae todo lo
  necesario; la ventana usa WebView2, el motor de Edge que ya trae Windows.
- **Con Python**: Python 3.10 o superior.
- **Servidor**: Debian 12, Debian 13 o Ubuntu 24.04.
- **Espacio**: unos 100 MB para el programa; los datos ocupan de decenas a
  algunos cientos de MB según el fondo y lo descargado de DILVE.

## Una demo sin instalar nada

Para enseñar Bildumargi en un equipo donde no se puede instalar nada, se
puede preparar una demo que se abre con doble clic, como un PDF. Instrucciones
en el README del proyecto, apartado «Demostración sin instalar nada».
