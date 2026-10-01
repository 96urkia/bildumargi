# -*- coding: utf-8 -*-
"""
Bildumargi · Configuración
==========================

Este es el ÚNICO fichero que hay que tocar para poner Bildumargi en marcha.
Todo lo que viene después de la sección 1 tiene valores por defecto que
funcionan tal cual.

Creado por: Asier Urkia · bildumargi@gmail.com
Licencia: GNU Affero General Public License v3 (AGPLv3). Ver LICENSE.
"""

import os

RAIZ = os.path.dirname(os.path.abspath(__file__))

# Versión del paquete. Se muestra al arrancar y en la cabecera de la aplicación.
VERSION = "1.1"


# ===========================================================================
# 1. ENLACE A LA BASE DE DATOS DE LA RED
# ===========================================================================
# Escribe aquí, entre las comillas, la dirección de descarga directa del
# fichero .db de tu red de bibliotecas, o la ruta a un .db guardado en este
# mismo ordenador o servidor. Ese .db se genera con `conversor.py` a partir
# de los ficheros MARC (.mods) de tu catálogo.
#
#   Ejemplo con Dropbox : "https://www.dropbox.com/scl/fi/xxxx/base.db?rlkey=yyyy&dl=1"
#   Ejemplo con ruta local: "datos/base_red.db"
#
# Si se deja vacío (""), Bildumargi funciona igualmente: analiza la colección
# propia a partir de los listados de AbsysNet y oculta automáticamente la
# sección de recomendaciones de compra, que necesita el catálogo de la red.

URL_BASE_DATOS = ""

# ===========================================================================
# 2. RESTO DE OPCIONES (no hace falta tocar nada)
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

# Fichero con las bibliotecas de la red, sus códigos de sucursal, población
# y superficie. Ver el README: es la otra pieza que conviene personalizar.
RUTA_BIBLIOTECAS = os.path.join(RUTA_DATOS, "bibliotecas.xlsx")

# Carpeta donde se guarda la copia descargada de la base de datos. Por
# defecto, «cache» junto al programa; si los datos van a otra carpeta, dentro
# de ella; y con BILDUMARGI_CACHE, donde se indique.
RUTA_CACHE = (os.environ.get("BILDUMARGI_CACHE")
              or (os.path.join(RUTA_DATOS, "cache") if os.environ.get("BILDUMARGI_DATOS")
                  else os.path.join(RAIZ, "cache")))

# Dirección y puerto del servidor local.
#   "127.0.0.1" -> solo accesible desde este ordenador.
#   "0.0.0.0"   -> accesible desde otros equipos de la intranet.
HOST = "127.0.0.1"
PUERTO = 8000

# Nombre de la red, que aparece en la cabecera de la aplicación.
NOMBRE_RED = "Red de Bibliotecas"

# Idioma inicial de la interfaz: "es" (castellano) o "eu" (euskera).
IDIOMA_POR_DEFECTO = "es"   # es · eu · ca · gl · en (cada biblioteca puede cambiarlo en Configuración)

# Año de referencia para los filtros cronológicos.
ANIO_ACTUAL = 2026

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

# ---------------------------------------------------------------------------
# Valoraciones entre bibliotecas
# ---------------------------------------------------------------------------
# Permite que cada biblioteca puntúe y comente los títulos del catálogo de la
# red. Tiene sentido en un despliegue CENTRAL (una sola instalación en el
# servidor de la red, a la que entran las demás por la intranet): ahí todo el
# mundo escribe y lee en el mismo sitio. En una instalación local de una sola
# biblioteca, las valoraciones no las ve nadie más; ponlo en False si no las
# quieres.
VALORACIONES_ACTIVAS = True

# Fichero donde se guardan. Es independiente del .db del catálogo A PROPÓSITO:
# ese se regenera con conversor.py cada vez que se actualiza el fondo, y las
# valoraciones se perderían con él. Haz copia de seguridad de este fichero.
RUTA_VALORACIONES = os.path.join(RUTA_DATOS, "valoraciones.db")

# Carpeta de cada biblioteca: sus preferencias y el historial de sus cargas
# (datos/bibliotecas/<biblioteca>/). Se crea sola.
RUTA_BIBLIOTECAS_DATOS = os.path.join(RUTA_DATOS, "bibliotecas")

# Preferencias de versiones anteriores, todas en un fichero: si existe, se
# lee como respaldo hasta que cada biblioteca guarde las suyas.
RUTA_PREFERENCIAS = os.path.join(RUTA_DATOS, "preferencias.json")

# Configuración de la red (pestañas, idiomas, apariencia por defecto e
# historial para todas las bibliotecas). Solo se cambia desde Configuración →
# Administración de la red, con esta clave. Vacía = administración desactivada.
# Mejor fijarla con la variable de entorno BILDUMARGI_CLAVE_ADMIN que escribirla aquí.
CLAVE_ADMIN = os.environ.get("BILDUMARGI_CLAVE_ADMIN", "")

RUTA_CONFIG_RED = os.path.join(RUTA_DATOS, "configuracion_red.json")

# Novedades de DILVE. La base vive SIEMPRE aquí y con este nombre, para poder
# copiarla de una versión de Bildumargi a la siguiente sin volver a descargarla.
RUTA_DILVE = os.path.join(RUTA_DATOS, "dilve", "novedades.db")
RUTA_DILVE_CREDENCIALES = os.path.join(RUTA_DATOS, "dilve", "credenciales.json")
# Fichas de DILVE ya descargadas, compartidas por toda la red: los títulos más
# prestados se repiten de una biblioteca a otra y así no se piden dos veces.
RUTA_DILVE_FICHAS = os.path.join(RUTA_DATOS, "dilve", "fichas.db")
# Tabla propia materias -> signatura, si la red quiere ajustarla.
RUTA_MATERIAS = os.path.join(RUTA_DATOS, "materias_secciones.json")
# Mejor con variables de entorno que escritas en disco:
DILVE_USUARIO = os.environ.get("BILDUMARGI_DILVE_USUARIO", "")
DILVE_CLAVE = os.environ.get("BILDUMARGI_DILVE_CLAVE", "")
DILVE_BASE = os.environ.get("BILDUMARGI_DILVE_BASE", "https://www.dilve.es/dilve/dilve/")


# Ficheros de partida que trae el programa y que se copian a la carpeta de
# datos la primera vez, si no están (nunca se sobrescriben: la red los edita).
FICHEROS_INICIALES = ("bibliotecas.xlsx", "pautas.json", "materias_secciones.json")


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


def url_base_datos() -> str:
    """Permite sobreescribir la URL con la variable de entorno
    BILDUMARGI_DB_URL, útil en despliegues de servidor donde no se quiere
    editar el fichero."""
    return (os.environ.get("BILDUMARGI_DB_URL") or URL_BASE_DATOS or "").strip()
