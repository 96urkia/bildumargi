# -*- coding: utf-8 -*-
"""
Bildumargi · Configuración
==========================

Todo tiene valores por defecto que funcionan tal cual. Las claves y lo
propio de cada ordenador van en config_local.py (ver el README).

Creado por: Asier Urkia · bildumargi@gmail.com
Licencia: GNU Affero General Public License v3 (AGPLv3). Ver LICENSE.
"""

import os

RAIZ = os.path.dirname(os.path.abspath(__file__))

# Versión del paquete. Se muestra al arrancar y en la cabecera de la aplicación.
VERSION = "2.1"


# ===========================================================================
# Opciones (no hace falta tocar nada; lo propio de cada ordenador, como las
# claves, va en config_local.py)
# ===========================================================================

# Carpeta de datos: todo lo que Bildumargi guarda (bases de datos, historial
# de cada biblioteca, configuración de la red, DILVE...).
#   · Por defecto, la carpeta «datos» junto al programa, como siempre: así
#     funciona el zip de Windows sin tocar nada.
#   · Con la variable de entorno BILDUMARGI_DATOS puede estar en otro sitio.
#     Es lo que usa el paquete de Linux (/var/lib/bildumargi), que instala el
#     programa en una carpeta del sistema en la que no se escribe.
DATOS_DEL_PROGRAMA = os.path.join(RAIZ, "datos")      # los que trae el programa
RUTA_DATOS = os.environ.get("BILDUMARGI_DATOS") or DATOS_DEL_PROGRAMA

# Configuración de la biblioteca (nombre, población, apariencia, pestañas,
# historial, signaturas, DILVE). Se cambia desde la pantalla Configuración.
RUTA_CONFIGURACION = os.path.join(RUTA_DATOS, "configuracion.json")

# Directorio de bibliotecas de la 1.x: solo se lee, si existe, para importar
# los datos de la biblioteca la primera vez.
RUTA_BIBLIOTECAS = os.path.join(RUTA_DATOS, "bibliotecas.xlsx")

# Dirección y puerto del servidor local.
#   "127.0.0.1" -> solo accesible desde este ordenador.
#   "0.0.0.0"   -> accesible desde otros equipos de la intranet.
HOST = "127.0.0.1"
PUERTO = 8000

# Nombre de la red a la que pertenece la biblioteca, en la cabecera. Vacío =
# ninguno. Se cambia en Configuración → Tu biblioteca; esto es solo el valor
# de partida.
NOMBRE_RED = ""

# Idioma inicial de la interfaz: "es" (castellano) o "eu" (euskera).
IDIOMA_POR_DEFECTO = "es"   # es · eu · ca · gl · en (se puede cambiar en Configuración)

# Año de referencia para los filtros cronológicos: el año en curso.
import datetime as _datetime  # noqa: E402
ANIO_ACTUAL = _datetime.date.today().year

# Minutos que una sesión de análisis permanece en memoria sin usarse.
MINUTOS_SESION = 180

# Pie de página.
AUTORIA = "Created by: Asier Urkia. Contact: bildumargi@gmail.com"

# Enlace al código fuente, que la AGPLv3 exige ofrecer a quien use el programa
# a través de una red (cláusula 13). Si despliegas una versión MODIFICADA en un
# servidor, cambia esta dirección por una donde pueda descargarse tu versión.
URL_CODIGO_FUENTE = "https://github.com/96urkia/bildumargi"

# Texto que acompaña al enlace anterior en el pie.
LICENCIA = "AGPLv3"

# Carpeta de cada biblioteca: sus preferencias y el historial de sus cargas
# (datos/bibliotecas/<biblioteca>/). Se crea sola.
RUTA_BIBLIOTECAS_DATOS = os.path.join(RUTA_DATOS, "bibliotecas")

# Clave para cambiar la configuración. Vacía = sin clave (lo normal en un
# solo ordenador). En un servidor al que entran varias personas, conviene
# ponerla en config_local.py o en la variable de entorno BILDUMARGI_CLAVE_ADMIN.
CLAVE_ADMIN = os.environ.get("BILDUMARGI_CLAVE_ADMIN", "")

# Novedades de DILVE. La base vive SIEMPRE aquí y con este nombre, para poder
# copiarla de una versión de Bildumargi a la siguiente sin volver a descargarla.
RUTA_DILVE = os.path.join(RUTA_DATOS, "dilve", "novedades.db")
RUTA_DILVE_CREDENCIALES = os.path.join(RUTA_DATOS, "dilve", "credenciales.json")
# Fichas de DILVE ya descargadas: lo que ya se tiene no se vuelve a pedir.
RUTA_DILVE_FICHAS = os.path.join(RUTA_DATOS, "dilve", "fichas.db")
# Idioma de los ejemplares extraído del catálogo MARC (.db de conversor.py):
# un fichero pequeño, para no leer cada vez un .db de más de un gigabyte.
RUTA_MARC_IDIOMAS = os.path.join(RUTA_DATOS, "marc_idiomas.db")
# Tabla propia materias -> signatura, si se quiere ajustar.
RUTA_MATERIAS = os.path.join(RUTA_DATOS, "materias_secciones.json")
# Mejor con variables de entorno o en config_local.py que escritas aquí:
DILVE_USUARIO = os.environ.get("BILDUMARGI_DILVE_USUARIO", "")
DILVE_CLAVE = os.environ.get("BILDUMARGI_DILVE_CLAVE", "")
DILVE_BASE = os.environ.get("BILDUMARGI_DILVE_BASE", "https://www.dilve.es/dilve/dilve/")


# Ficheros de partida que trae el programa y que se copian a la carpeta de
# datos la primera vez, si no están (nunca se sobrescriben: se pueden editar).
FICHEROS_INICIALES = ("pautas.json", "materias_secciones.json")


def preparar_carpeta_datos():
    """Crea la carpeta de datos y copia en ella los ficheros de partida que
    falten. Con la instalación de siempre (datos junto al programa) no hace
    nada: los ficheros ya están ahí."""
    import shutil
    os.makedirs(RUTA_DATOS, exist_ok=True)
    if os.path.abspath(RUTA_DATOS) == os.path.abspath(DATOS_DEL_PROGRAMA):
        return
    import glob
    # Encabezados THEMA (thema_es.json…): opcionales, con el nombre que tengan
    thema = [os.path.basename(r) for r in glob.glob(os.path.join(DATOS_DEL_PROGRAMA, "thema*"))]
    for nombre in (*FICHEROS_INICIALES, *thema):
        origen = os.path.join(DATOS_DEL_PROGRAMA, nombre)
        destino = os.path.join(RUTA_DATOS, nombre)
        if os.path.exists(origen) and not os.path.exists(destino):
            shutil.copy2(origen, destino)


# Ajustes propios de este ordenador (rutas, claves): en config_local.py, junto
# a este fichero. No se sube al repositorio ni entra en el zip, así que las
# claves no salen nunca de aquí. Lo que se escriba allí manda sobre lo de arriba.
_CONFIG_LOCAL = os.path.join(RAIZ, "config_local.py")
if os.path.exists(_CONFIG_LOCAL):
    with open(_CONFIG_LOCAL, encoding="utf-8") as _f:
        exec(compile(_f.read(), _CONFIG_LOCAL, "exec"))
