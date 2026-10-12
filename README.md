# Bildumargi

**Análisis de la colección de una biblioteca pública a partir de los listados de AbsysNet.**

Bildumargi lee las exportaciones que ya genera tu sistema de gestión y devuelve
el estado real del fondo: qué se presta y qué no se ha movido nunca, cómo se
reparte la colección por materias y lenguas, qué tramos están envejecidos, qué
series están incompletas y qué conviene comprar.

La versión 2.0 está pensada para que **cada biblioteca** lo instale en su
ordenador, con sus datos y su cuenta de DILVE. Los listados no salen del
equipo y no hace falta publicarlo en internet.

**Versión 2.0** · Licencia AGPLv3 · Castellano, euskera, catalán, gallego e inglés.

**Manual de uso:** <https://96urkia.github.io/bildumargi/>

**Descargas:** instalador para Windows, zip para cualquier sistema y paquetes
.deb para Debian y Ubuntu, en [la página de versiones](https://github.com/96urkia/bildumargi/releases).

---

## Instalar en Windows (lo habitual)

1. Descarga `Bildumargi-2.0-instalador.exe` de la página de versiones.
2. Ábrelo con doble clic. No pide permisos de administrador. Si Windows avisa
   de que «protegió su PC», pulsa **Más información → Ejecutar de todas formas**
   (es un programa libre sin firma comercial).
3. El instalador pregunta, y todo se puede dejar en blanco y rellenar después
   en **Configuración**:
   - **Tu biblioteca**: nombre, red a la que pertenece, población y superficie.
   - **Cuenta de DILVE**: usuario y contraseña.
   - **Catálogo MARC**: la ruta al `.db` del catálogo, si lo tienes.
4. Al terminar queda un acceso directo en el escritorio. Bildumargi se abre en
   su propia ventana.

Los datos se guardan en `%LOCALAPPDATA%\Bildumargi\datos`. Desinstalar el
programa no los borra.

## Con Python (Windows, Linux o macOS)

Hace falta **Python 3.10 o superior** (en Windows, marca **«Add Python to
PATH»** al instalarlo). Descomprime el zip y, desde su carpeta:

```
pip install -r requirements.txt
python iniciar.py
```

Se abre el navegador en `http://127.0.0.1:8000`. También vale doble clic en
`iniciar.bat` (Windows) o `./iniciar.sh` (Linux y macOS). Para pararlo,
`Ctrl+C` o cerrar la ventana.

## En un servidor Linux (paquete .deb)

Para que varios ordenadores de la biblioteca usen el mismo Bildumargi desde
el navegador. Hay un `.deb` para Debian 12, Debian 13 y Ubuntu 24.04:

```
sudo apt install ./bildumargi_2.0-1~ubuntu24.04_amd64.deb
```

Queda como servicio en `127.0.0.1:8765`, con una clave de configuración
aleatoria en `/etc/bildumargi/secretos.env` (ahí van también el usuario y la
contraseña de DILVE). Se publica en la intranet con nginx, a partir de
`/usr/share/doc/bildumargi/ejemplos/nginx-bildumargi.conf`.

| Qué | Dónde |
| --- | --- |
| Programa (no se modifica) | `/usr/lib/bildumargi` |
| Ajustes: dirección, puerto, carpeta de datos | `/etc/bildumargi/bildumargi.env` |
| Claves (solo las lee el administrador) | `/etc/bildumargi/secretos.env` |
| Datos: configuración, historial, DILVE | `/var/lib/bildumargi` |
| Mensajes del programa | `journalctl -u bildumargi` |

Tras cambiar ajustes o claves: `sudo systemctl restart bildumargi`. Para
actualizar, se instala el `.deb` nuevo igual que el primero; `apt remove`
conserva los datos y `apt purge` lo borra **todo**. Guía paso a paso en el
[manual](https://96urkia.github.io/bildumargi/administracion/instalar-servidor/).

---

## Configuración

Todo se ajusta dentro de la aplicación, en **Configuración**, con un menú
lateral:

- **Tu biblioteca**: nombre, red (editable, para que lo use cualquier red),
  población y superficie. Con la población salen los documentos por habitante.
- **Apariencia e idioma**, **Pestañas** visibles y pestaña de inicio.
- **Historial de cargas**: cuántas se guardan para el seguimiento.
- **Secciones por signatura**: qué prefijo corresponde a cada sección.
- **Novedades del libro español (DILVE)** y **Fichas de DILVE de todo el
  catálogo**.
- **Catálogo MARC (idioma)**: de dónde sacar el idioma de cada ejemplar.
- **Series ocultas**: las que se han marcado como «no es una serie».

Si se pone una clave (`CLAVE_ADMIN`), la configuración solo la cambia quien
la sepa. Es lo recomendable en una instalación compartida.

### DILVE

Con una cuenta de [DILVE](https://www.dilve.es) se activan las sugerencias de
compra, las novedades, las portadas y la detección de series. Bildumargi pide
las fichas por ISBN (128 por llamada, con pausas) y las guarda en
`dilve/fichas.db` para no repetir.

La opción **Descargar las fichas de todo el catálogo** pide primero una
confirmación bien visible: en una biblioteca pequeña son unos 10 000 libros;
en una grande, muchas más llamadas. Se puede parar y retomar.

### El idioma: catálogo MARC y DILVE

Los listados de AbsysNet no traen el idioma. Bildumargi lo toma, por este
orden, del **catálogo MARC** (campo 008), de la **ficha de DILVE** y, solo si
no hay duda, de la **signatura** (`EUS N ATX`). DILVE va bien con las
novedades y falla con lo antiguo; el MARC, al revés: juntos, en una
biblioteca pequeña, se pasa del 45 % al 99 % de ejemplares con idioma.

El `.db` del catálogo se genera una vez con `conversor.py` a partir de una
exportación MARC21 (`python conversor.py fichero.mrc`; en Linux,
`sudo bildumargi conversor fichero.mrc`). Bildumargi extrae de él solo los
idiomas de tus ejemplares y deja de necesitarlo.

### Ajustes propios: `config_local.py`

Lo que no está en pantalla (puerto, clave, rutas) se pone en un
`config_local.py` junto a `config.py`, que tiene prioridad sobre él y no se
sube al repositorio ni entra en el zip:

```python
PUERTO = 8002
CLAVE_ADMIN = "una clave larga"
```

La carpeta de datos se puede mover con la variable de entorno
`BILDUMARGI_DATOS`.

---

## Qué muestra cada pestaña

- **Diagnóstico**: volumen, circulación, uso relativo, antigüedad y fondo por
  habitante, con el núcleo de Bradford y lo que no se ha prestado nunca.
- **Secciones**: cada sección por materias, lenguas y años, con búsqueda y
  exportación a CSV.
- **Series**: las series y colecciones del fondo, detectadas con DILVE, con la
  portada del primer tomo. Al abrir una, sus libros con número, año y
  préstamos, y los tomos que **faltan**, también los posteriores y las
  novedades.
- **Sugerencias de compra** (con DILVE): **Autores más prestados**, que mira
  todos los libros de cada autor y sus préstamos en conjunto, y **Novedades**
  afines a lo que más se presta.
- **Seguimiento**: la evolución entre cargas y, en cada subida, las **altas y
  bajas** de ejemplares (lo añadido y lo expurgado).
- **Informe imprimible** con lo principal, para guardar en PDF.

Explicación detallada de cada indicador en el
[manual](https://96urkia.github.io/bildumargi/referencia/indicadores/).

## Los cuatro listados de AbsysNet

Se cargan con un asistente, un fichero por pantalla: **Siguiente** avanza y,
en los opcionales, **Omitir** los salta. Al final, un resumen muestra lo
cargado antes de analizar. El último análisis se puede volver a abrir sin
cargar nada.

| Listado | ¿Obligatorio? | Qué aporta | Si se omite |
|---|---|---|---|
| Topográfico de ejemplares | Sí | La colección: signatura, código de barras, localización. | No se puede analizar. |
| Catálogo | No, muy recomendable | Año de edición, autor, ISBN y materias. | Análisis en «modo reducido». |
| No prestados | No, muy recomendable | Marca lo que no ha salido en préstamo en el periodo. | Todo cuenta como prestado: la circulación y el uso relativo **no son reales**. El panel lo avisa. |
| Más prestados | No | Marca los títulos de alta demanda. | No se distingue la alta demanda del préstamo normal. |

Expórtalos **en `.txt`** y súbelos tal cual: no los abras ni los guardes con
Excel. Si AbsysNet no deja exportar el catálogo de una vez, se pueden subir
**varios ficheros** en su hueco. Si te equivocas de paso, Bildumargi
identifica cada fichero por su contenido y lo recoloca.

---

## Demostración sin instalar nada (equipos bloqueados)

Para enseñar Bildumargi en un equipo donde no se puede instalar ni ejecutar
ningún programa, se puede crear una **demo**: una carpeta que se abre con
doble clic en «Abrir Bildumargi.html», en Edge o Chrome, igual que un PDF.
No arranca ningún servidor: los resultados van ya calculados dentro.

Se prepara en un ordenador donde Bildumargi sí funcione:

1. Arranca Bildumargi y abre su dirección añadiendo `?grabar_demo=1` (por
   ejemplo `http://127.0.0.1:8000/?grabar_demo=1`). Abajo a la izquierda
   aparece el panel «Grabando la demo».
2. Carga y analiza los listados **con la grabación ya activa**.
3. Pulsa «Recorrido automático» y espera unos minutos: recorre pestañas,
   secciones y sugerencias y graba lo que aparece. Puedes pulsar además, a
   mano, lo que quieras enseñar.
4. Pulsa «Descargar grabación» (`bildumargi-grabacion.json`).
5. Desde la carpeta de Bildumargi:
   `python crear_demo.py "ruta\a\bildumargi-grabacion.json"`. Crea la carpeta
   `Bildumargi-demo` y el zip, con su huella SHA-256. Va **sin portadas**, para
   no conectarse a internet; con `--con-portadas` se incluyen.

En la demo, al pulsar «Analizar» se ven los resultados ya calculados; la
configuración admite cualquier clave; lo que no se grabó muestra un aviso en
lugar de fallar. No incluye el usuario de DILVE.

## Datos y privacidad

Los listados describen **ejemplares**, no lectores. Todo se queda en el
ordenador o servidor donde está instalado. Solo se sale fuera para DILVE
(se envían ISBN), para las portadas y para los enlaces que pulses. La cuenta
de DILVE se guarda en `dilve/credenciales.json`, en la carpeta de datos:
trata sus copias como algo privado.

## Qué hay en cada carpeta

```
config.py            Configuración general (no se toca).
config_local.py      Tus ajustes y claves (lo creas tú; no se sube ni entra en el zip).
iniciar.py           Arranque con Python. Doble clic en iniciar.bat o ./iniciar.sh.
escritorio.py        Arranque de la aplicación de Windows (ventana propia).
conversor.py         MARC21 -> .db, para el idioma de los ejemplares.
crear_demo.py        Demo sin instalar nada.

backend/             Lógica en Python.
  absysnet.py          Lectura de los cuatro listados.
  clasificacion.py     Motor de tejuelo: las reglas de signatura.
  analisis.py          Métricas, agregados y búsqueda.
  cambios.py           Altas y bajas entre cargas.
  configuracion.py     La configuración de la biblioteca.
  dilve.py             Cliente de DILVE y caché de fichas.
  idiomas.py, marc.py  Idioma de cada ejemplar (MARC, DILVE, signatura).
  series.py            Detección de series y tomos que faltan.
  sugerencias.py       Sugerencias de compra.
  servidor.py          API y servidor web.

frontend/            Interfaz web en JavaScript.
  js/i18n.js           Todos los textos, en los cinco idiomas.
  fuentes/             Tipografías en local (no depende de internet).

packaging/           Receta del .deb, del zip y, en windows/, del instalador.
docs/                El manual (MkDocs).

datos/               (se crea sola; en Windows, %LOCALAPPDATA%\Bildumargi\datos)
  configuracion.json   La configuración de la biblioteca.
  pautas.json          Referencia de fondo por habitante.
  marc_idiomas.db      Idiomas extraídos del catálogo MARC.
  dilve/               Fichas y novedades de DILVE, y la cuenta.
  bibliotecas/         Historial de cargas.
```

## Traducciones

Todos los textos de la interfaz están en `frontend/js/i18n.js`, un bloque por
idioma (`es`, `eu`, `ca`, `gl`, `en`) con las mismas claves. Los marcadores
entre llaves (`{n}`, `{s}`…) deben conservarse tal cual. El inglés usa
ortografía británica y números a la inglesa (10,112 · 32.9%); los otros
cuatro, punto de miles y coma decimal. Para añadir un idioma, se copia el
bloque `es` con un código nuevo, se traduce y se añade a `IDIOMAS_INTERFAZ`.

## Cómo se publica una versión (para quien mantiene el proyecto)

Al subir una etiqueta:

```
git tag -a v2.0 -m "Bildumargi 2.0"
git push origin v2.0
```

GitHub (`.github/workflows/publicar.yml`) construye el zip, los tres `.deb`
y el instalador de Windows, prueba los `.deb` en un sistema limpio y lo
publica todo en la página de la versión con sus huellas SHA-256. El
instalador también se puede construir a mano en Windows con
`packaging\windows\construir.ps1` (necesita Inno Setup 6).

El manual se publica solo (`.github/workflows/manual.yml`) al cambiar `docs/`.

---

## Esquemas de clasificación de terceros

Bildumargi usa códigos del esquema de clasificación temática **Thema**,
© EDItEUR Limited (https://www.editeur.org), conforme a la *Licence to use
EDItEUR Standards* (https://doi.org/10.4400/nwgj). Traducción española de
Thema © FGEE – Federación de Gremios de Editores de España, difundida a
través de DILVE (https://web.dilve.es). Códigos heredados BIC/IBIC © BIC y
Nielsen Book Services Ltd (https://bic.org.uk), usados conforme a la
licencia de estándares de BIC. Los números de la **Clasificación Decimal
Universal (CDU/UDC)** se usan solo como identificadores de sección de
estantería; la CDU es © UDC Consortium (https://udcc.org).

Las tablas de correspondencia THEMA/IBIC → sección son obra original de este
proyecto y se distribuyen bajo AGPLv3; usan los códigos como identificadores,
sin reproducir los encabezados oficiales. La lista de encabezados de EDItEUR,
si se incluye en un paquete, conserva su propia licencia y **no** está bajo
AGPLv3. Bildumargi no está afiliado a EDItEUR, la FGEE, DILVE, BIC ni la UDC
Consortium, ni cuenta con su respaldo. ONIX y Thema son estándares de
EDItEUR.

## Licencia

Bildumargi es software libre bajo la **Licencia Pública General Affero de GNU,
versión 3 (AGPLv3)**. Puedes usarlo, estudiarlo, adaptarlo y redistribuirlo;
a cambio, las copias y las versiones modificadas deben mantener esta misma
licencia y ofrecer su código fuente.

La AGPL añade una condición propia respecto a la GPL corriente: si despliegas
una versión **modificada** en un servidor y otras personas la usan a través de
la red, debes ofrecerles la descarga del código de esa versión. Para eso está
`URL_CODIGO_FUENTE` en `config.py`, que alimenta el enlace «Código fuente» del
pie de página; si lo usas sin modificar, no tienes que tocar nada.

Texto completo en `LICENSE`; explicación en castellano en `AVISO-LICENCIA.md`.

Las tipografías Public Sans e IBM Plex Mono de `frontend/fuentes/` se
distribuyen bajo la SIL Open Font License 1.1 (textos en esa misma carpeta).

Created by: Asier Urkia. Contact: bildumargi@gmail.com
