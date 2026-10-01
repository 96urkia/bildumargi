# Bildumargi

**Análisis de la colección de una biblioteca pública a partir de los listados de AbsysNet.**

Bildumargi lee las exportaciones que ya genera tu sistema de gestión y devuelve
el estado real del fondo: qué se presta y qué no se ha movido nunca, cómo se
reparte la colección por materias y lenguas, qué tramos están envejecidos y —si
enlazas el catálogo colectivo— qué títulos tiene el resto de la red y tú no.

Funciona de dos maneras: en un solo ordenador (el análisis se hace en local y
los ficheros no salen de él) o en un servidor de la intranet de la red, al que
entran todas las bibliotecas desde el navegador sin instalar nada. En ningún
caso necesita estar publicado en internet.

**Versión 1.1** · Licencia AGPLv3 · Castellano, euskera, catalán, gallego e inglés.

**Descargas:** zip para Windows y cualquier sistema y paquetes .deb para Debian
y Ubuntu, en [la página de versiones](https://github.com/96urkia/bildumargi/releases).

---

## Puesta en marcha en cinco minutos

### 1. Instalar Python

Hace falta **Python 3.10 o superior**. Comprueba si ya lo tienes abriendo una
terminal (en Windows, «Símbolo del sistema») y escribiendo:

```
python --version
```

Si no lo tienes, descárgalo de [python.org](https://www.python.org/downloads/).
En Windows, marca la casilla **«Add Python to PATH»** durante la instalación.

### 2. Instalar las librerías

Desde la carpeta de Bildumargi:

```
pip install -r requirements.txt
```

### 3. Arrancar

```
python iniciar.py
```

Se abre el navegador en `http://127.0.0.1:8000`. Para parar la aplicación,
pulsa `Ctrl+C` en la terminal o cierra la ventana.

En Windows puedes hacer doble clic en `iniciar.bat`; en Linux y macOS, ejecutar
`./iniciar.sh`.

**Ya funciona.** Todo el análisis de la colección propia está disponible sin
configurar nada más. Los dos apartados siguientes son para sacarle el resto.

---

## Instalación en un servidor Linux (paquete .deb)

Para Debian 12, Debian 13 y Ubuntu 24.04 hay un paquete que instala Bildumargi
como un servicio más del sistema. En la página de cada versión en GitHub
están el zip de siempre y un `.deb` por distribución, con sus huellas en
`SHA256SUMS`.

```
sudo apt update
sudo apt install ./bildumargi_1.1-1~ubuntu24.04_amd64.deb
```

El paquete crea un usuario propio para el servicio, lo deja arrancado en
`127.0.0.1:8765` y genera una clave de administración aleatoria. Después:

1. Ver la clave: `sudo cat /etc/bildumargi/secretos.env`. En ese mismo fichero
   se ponen, si se usa DILVE, el usuario y la contraseña de la cuenta.
2. Sustituir `/var/lib/bildumargi/bibliotecas.xlsx` por el directorio de la red.
3. Publicarlo en la intranet con nginx, a partir del ejemplo de
   `/usr/share/doc/bildumargi/ejemplos/nginx-bildumargi.conf`.
4. Tras cambiar ajustes o claves: `sudo systemctl restart bildumargi`.

| Qué | Dónde |
| --- | --- |
| Programa (no se modifica) | `/usr/lib/bildumargi` |
| Ajustes: dirección, puerto, carpeta de datos | `/etc/bildumargi/bildumargi.env` |
| Claves (solo las lee el administrador) | `/etc/bildumargi/secretos.env` |
| Datos: bases, historial, DILVE | `/var/lib/bildumargi` |
| Mensajes del programa | `journalctl -u bildumargi` |

La orden `bildumargi` sirve para lo demás: `sudo bildumargi conversor
fichero.mrc` genera la base de la red y `bildumargi version` muestra la
versión instalada.

Para **actualizar**, se instala el `.deb` de la versión nueva igual que el
primero: los ajustes, las claves y los datos se conservan. `sudo apt remove
bildumargi` desinstala el programa y conserva ajustes y datos; `sudo apt purge
bildumargi` lo borra **todo**, datos incluidos.

### Cómo se publica una versión (para quien mantiene el proyecto)

La carpeta `packaging/` contiene la receta del paquete y
`.github/workflows/publicar.yml`, el proceso automático. Al subir una etiqueta:

```
git tag -a v1.1 -m "Bildumargi 1.1"
git push origin v1.1
```

GitHub construye el zip y los tres `.deb`, prueba a instalar cada uno en un
sistema limpio y los publica en la página de la versión con sus huellas.

## Lo que hay que configurar

### Dónde guarda Bildumargi sus datos

Por defecto, en la carpeta `datos` junto al programa (y la caché en `cache`).
No hace falta configurar nada: así funciona el zip de Windows.

Para guardar los datos en otra carpeta, se define la variable de entorno
`BILDUMARGI_DATOS` antes de arrancar. Es lo que hace el paquete de Linux, que
instala el programa en una carpeta del sistema y los datos en
`/var/lib/bildumargi`:

```
BILDUMARGI_DATOS=/var/lib/bildumargi python3 iniciar.py
```

La primera vez, Bildumargi crea esa carpeta y copia en ella `bibliotecas.xlsx`,
`pautas.json` y, si existe, `materias_secciones.json`. Nunca los sobrescribe
después, así que los cambios de la red se conservan al actualizar. La caché va
dentro de esa carpeta, salvo que se indique otra con `BILDUMARGI_CACHE`.


### 1. El enlace a la base de datos de la red

**Fichero:** `config.py`
**Línea:** **34**

```python
URL_BASE_DATOS = ""
```

Escribe entre las comillas la dirección de tu base de datos. Admite dos formas:

```python
URL_BASE_DATOS = "datos/base_red.db"                                   # fichero local
URL_BASE_DATOS = "https://www.dropbox.com/scl/fi/xxx/base.db?dl=1"     # descarga directa
```

Si usas un enlace de Dropbox, asegúrate de que termina en `?dl=1` y no en
`?dl=0`: con `dl=0` se descarga la página de vista previa en lugar del fichero,
y Bildumargi avisará de que lo recibido no es una base SQLite.

Ese `.db` lo generas tú con `conversor.py` (apartado 4). Alternativamente,
puedes fijar la variable de entorno `BILDUMARGI_DB_URL` en lugar de editar el
fichero, que es lo cómodo en un despliegue de servidor.

**Si dejas esta línea vacía**, Bildumargi sigue funcionando: analiza la
colección propia con normalidad y **oculta por sí sola la pestaña de
sugerencias de compra**, que es la única parte que necesita el catálogo
colectivo. También se apaga el filtro de idioma, porque la lengua de cada
documento se lee del campo MARC 008 y ese dato vive en la base, no en los
listados de AbsysNet.

### 2. El directorio de bibliotecas

**Fichero:** `datos/bibliotecas.xlsx`

Es lo que permite a Bildumargi reconocer sola qué biblioteca ha subido los
listados y con qué población comparar la colección. Tiene cuatro columnas,
más una opcional para el acceso con clave:

| Columna | ¿Obligatoria? | Qué es |
|---|---|---|
| `Nombre_biblioteca` | Sí | El nombre tal y como aparece en el campo 952 del catálogo (la biblioteca propietaria del ejemplar). |
| `Sucursal` | Sí | El número de la columna «Suc.» de los listados de AbsysNet. |
| `Poblacion` | Sí | Habitantes atendidos. |
| `Metros_cuadrados` | **No** | Superficie útil. Si se deja vacía, el indicador de documentos por m² aparece como «N/D». |
| `Clave` | **No** | Clave con la que la biblioteca vuelve a su último análisis guardado sin subir los ficheros (ver «Acceso con clave»). |

El fichero incluye tres filas de ejemplo: **bórralas** y escribe debajo tus
bibliotecas, una por fila, sin tocar los nombres de la primera fila. Cada
cabecera lleva un comentario explicativo, y la segunda hoja del Excel repite
estas instrucciones.

**Para saber el código de sucursal:** abre cualquier listado topográfico
exportado de AbsysNet. La columna «Suc.» trae ese número en todas las líneas, y
es el mismo para toda la biblioteca.

Si no usas Excel, puedes guardar lo mismo como `datos/bibliotecas.csv` con esas
columnas en la primera fila: Bildumargi lo lee igual.

**Acceso con clave.** Para ver lo que ya estaba analizado no hace falta volver
a subir los listados. A la derecha del asistente de carga aparece «Entrar con
clave»: la biblioteca escribe su nombre en «Biblioteca de:» (basta con la
localidad, «Monteagudo», sin tildes ni mayúsculas) y su clave, y se abre su
**última carga guardada**, igual que si acabara de subirla. Funciona así:

- Las claves las crea y las cambia **el administrador de la red**, en la
  columna `Clave` del Excel de la carpeta de datos. No hay registro de
  usuarios ni «He olvidado mi contraseña»: quien la olvide pide otra al
  administrador. Bildumargi relee el Excel al momento, sin reiniciar.
- Una biblioteca sin clave no puede entrar así (sigue pudiendo subir sus
  ficheros), y el panel solo aparece si alguna biblioteca tiene clave y el
  historial de cargas está activo (Administración de la red), porque lo que
  se abre es la última carga guardada. Si aún no hay ninguna, se avisa.
- Tras cinco intentos fallidos en diez minutos desde el mismo equipo hay que
  esperar. El mensaje de error es el mismo si la biblioteca no existe o la
  clave está mal, para no revelar qué bibliotecas hay.
- Las claves se guardan **tal cual en el Excel**, sin cifrar: es una barrera
  sencilla, no un sistema de seguridad. Usa claves que no sirvan para nada
  más, y **no compartas ni publiques el Excel con las claves puestas** (en
  particular, no lo subas a ningún repositorio: el del proyecto lleva la
  plantilla con la columna vacía).

### 3. La referencia de fondo por habitante

**Fichero:** `datos/pautas.json`

El Diagnóstico compara los documentos por habitante del municipio con una
referencia. Esa referencia **no está escrita en el código**: vive en este
fichero para que cada red ponga la suya, sea un estándar autonómico, el plan
de su red o un criterio propio. La fuente aparece siempre junto al dato en el
panel, así que quien lo lea sabe con qué se compara.

Por defecto trae las **Pautas sobre los servicios de las bibliotecas públicas
(2002)**, que recogen las Directrices IFLA/UNESCO (2001): de **1,5 a 2,5
documentos por habitante** y un fondo mínimo de **2.500 documentos**.

Una red que quiera tramos por población lo escribiría así (el ejemplo es
ilustrativo, no el valor por defecto):

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

- Los tramos se leen en orden: se aplica el primero cuyo `hasta_habitantes`
  sea mayor o igual que la población. `null` significa «sin límite».
- `docs_hab_min` y `docs_hab_max` marcan el tramo de referencia. Si son
  iguales, la referencia es un valor único.
- `fuente_corta` es lo que se ve en la tarjeta; `fuente`, el texto completo
  que aparece al pasar el ratón.
- Si el fichero falta o está mal formado, se usan las Pautas de 2002.

La población sale de `datos/bibliotecas.xlsx`: sin ella no hay dato por
habitante. **En municipios pequeños es normal superar la referencia**, porque
una biblioteca necesita un fondo básico sea cual sea su población. El panel
lo explica en su lectura automática y no lo marca como un problema.

### 4. Generar el `.db` con `conversor.py`

En la carpeta va incluido **`conversor.py`**, que convierte la exportación MARC
del catálogo en el `.db` que necesita el punto 1:

```
python conversor.py todopublicas.mrc -o datos/base_red.db
```

Admite MARC21 binario (`.mrc`, lo habitual en AbsysNet/Baratz) y MARCXML
(`.xml`, `.mods`, `.marcxml`), y también una carpeta entera con varias
exportaciones. Opciones útiles:

```
--anio-minimo-marcxml 2015   guardar el MARCXML solo desde ese año (por defecto)
--sin-marc                   no guardar el MARCXML: base mucho más ligera
--sin-fts                    no crear los índices de búsqueda por texto
--codificacion utf-8         si tu MARC binario no viene en iso-8859-1
```

**Sobre el tamaño.** Medido sobre 500.000 registros: con el MARCXML completo la
base ronda los 2,1 GB y sin él los 850 MB. Los índices FTS5 casi triplican el
fichero. Si necesitas una base más ligera, las palancas por orden son
`--anio-minimo-marcxml`, `--sin-fts-libros` y `--sin-marc`.

**El mapeo del campo 952** está en constantes al principio de `conversor.py`
(`SUB_BIBLIOTECA`, `SUB_SECCION`, `SUB_SIGNATURA`, `SUB_CODIGO_BARRAS`). Los
valores por defecto son los de AbsysNet; si tu catálogo coloca los datos del
ejemplar en otros subcampos, ese es el único punto que hay que tocar. Al
terminar, el conversor avisa si no ha leído ningún ejemplar, que es la señal de
que el mapeo no corresponde.

---

## Qué muestra cada pestaña

- **Diagnóstico.** Radiografía del fondo en una pantalla: volúmenes,
  documentos por habitante frente a la referencia de `datos/pautas.json`,
  circulación, actualidad y el peso y uso relativo de cada sección, con una
  lectura automática en texto.
- **Secciones.** Exploración por signatura: el treemap sirve para elegir una
  sección y el resto del panel muestra su perfil (años, localizaciones,
  ejemplares). El buscador admite comodines y varias signaturas separadas por
  comas: `32*, I 32*` o `*(460*`.
- **Sugerencias de compra** (solo con la base de la red). Cruza la demanda
  del fondo propio con lo que tienen las demás bibliotecas: dónde hace más
  falta comprar y qué títulos, ordenados por su presencia en la red.

**Informe imprimible.** El botón «Informe», junto a «Cambiar ficheros», abre
una vista previa en hojas A4 que se imprime o se guarda como PDF desde el
propio navegador (sin conexión a internet). Describe el fondo completo, sin
filtros:

1. Indicadores con su referencia, la lectura automática y el peso y uso
   relativo de cada sección.
2. La colección sección a sección (volúmenes, peso, préstamo, uso relativo,
   año medio, % de los últimos 5 años) y los años de edición.
3. Con la base de la red: dónde hace más falta comprar y títulos sugeridos
   de las secciones prioritarias.

Cierra con notas de método (qué es el uso relativo, de dónde sale el
préstamo, la fuente de la referencia por habitante). Se imprime siempre en
tema claro; la opción «Para blanco y negro» usa la paleta de un solo tono.
Lo que no cabe en una hoja pasa solo a la siguiente.

**El uso relativo** aparece en las tres pestañas y tiene una ayuda «?» junto
al dato. Compara cuánto se presta una sección con cuánto pesa en el fondo: su
parte de los ejemplares prestados dividida entre su parte de los volúmenes.
Una sección con el 10 % de los volúmenes y el 15 % de los ejemplares
prestados tiene un uso relativo de 1,5. El 1,0 significa que rinde lo que
pesa. Se calcula con el préstamo sí/no de los listados de AbsysNet, no con
el número de préstamos (es el «uso relativo» de Bonn, 1974).

Bildumargi describe el fondo y sugiere compras. **No propone retirar
ejemplares**: esa decisión corresponde al personal bibliotecario.

## Configuración: red y biblioteca

La configuración tiene dos niveles. El botón con la rueda dentada, arriba a la
derecha, abre la de la biblioteca; desde su pie se entra a la de la red.

### Nivel red (administración)

Lo decide la red para **todas** las bibliotecas:

- **Pestañas que existen.** Las que se desactivan desaparecen para todos; por
  ejemplo, quitar «Red» si la red no quiere comentarios entre bibliotecas.
- **Idiomas que se ofrecen** y el idioma, tema y paleta **de partida**.
- **Historial de cargas**: si se guardan los listados de cada carga y
  cuántas cargas se conservan por biblioteca (12 por defecto).

Se entra con una clave. Se fija en `config.py`, en `CLAVE_ADMIN`, o con la
variable de entorno `BILDUMARGI_CLAVE_ADMIN`, que es preferible en un
servidor compartido. Sin clave, la administración queda desactivada y todo
está activo.

**No hay recuperación por correo**, y es a propósito: exigiría un servidor de
correo que mantener y direcciones que custodiar. Si alguien la olvida, quien
administre la red abre `config.py`, pone otra y reinicia Bildumargi. La
pantalla de acceso lo explica. Sin clave, la administración queda desactivada y todo está
activo. El acceso dura dos horas y un intento fallido tarda un segundo en
responder, para frenar los intentos a ciegas. Se guarda en
`datos/configuracion_red.json`.

La administración tiene además su propia **tabla de secciones por
signatura**, igual que la de cada biblioteca: la usan las bibliotecas que no
tengan una propia. Si una biblioteca cambia la suya, manda la de la
biblioteca; con «Volver a la tabla de la red» recupera la común.

### Nivel biblioteca

Cada biblioteca ajusta lo suyo dentro de lo que permite la red:

- **Idioma de la interfaz** (castellano, euskera, catalán, gallego o inglés) entre los que ofrece la red. Se traducen también
  los nombres de sección, de lengua y el informe; las signaturas no se tocan.
- **Tema**: oscuro (para pantalla) o claro (más luz; también para imprimir).
- **Colores de los gráficos**: azul y naranja (Okabe-Ito, la recomendada),
  Viridis o Azules (un solo tono, para imprimir en blanco y negro). Todas se
  leen con las formas más comunes de daltonismo.
- **Pestañas**: ocultar las que no usa y elegir con cuál se abre. Las que la
  red ha desactivado aparecen marcadas y no se pueden activar.
- **Secciones por signatura**: una tabla de dos columnas, «Empieza por» y
  «Sección», que dice a qué sección del análisis va cada signatura según su
  comienzo: `N` → Ficción / Narrativa, `I 1` → I 1 - Filosofía, `EUS` →
  Euskera, `VIA` → Viajes… Basta con el principio, porque detrás cada
  signatura lleva sus letras (`N GRE cie`), y gana el comienzo más largo
  (`I 1` antes que `I`). Un prefijo con letras no se corta a mitad de
  palabra (`C` no se lleva `CUA 12`); uno solo numérico sigue la CDU (`8`
  incluye `821`). Una sección cuenta como infantil si empieza por `I` o `JN`
  o su nombre dice «infantil» o «juvenil» (también en euskera, gallego o
  inglés). Por defecto la tabla es la de siempre; la biblioteca puede
  añadir, cambiar o quitar filas, y el fondo se reclasifica al guardar, sin
  volver a subir nada. Solo afecta al análisis (Diagnóstico, Secciones,
  informe): las sugerencias de compra siguen con las secciones comunes de la
  red, que son las que se pueden cruzar con su oferta.

Los cambios de tema y paleta se ven al momento; si se cierra sin guardar, se
deshacen. Se guarda en la carpeta de la biblioteca (abajo), así que es la
misma configuración en cualquier ordenador desde el que entre; además se
recuerda en cada navegador para aplicar el tema desde la primera pantalla.

### Carpeta de cada biblioteca

```
datos/bibliotecas/biblioteca-de-monteagudo/
  biblioteca.txt           El nombre de la biblioteca, para reconocer la carpeta.
  preferencias.json        Su configuración.
  cargas/20260919-093012/  Una carpeta por carga:
    topografico/…            los listados tal como se subieron
    catalogo/…
    no_prestados/…
    mas_prestados/…
    resumen.json             sus indicadores, para el seguimiento
```

Se crea sola. Si existía el `datos/preferencias.json` de versiones anteriores,
se usa como respaldo hasta que cada biblioteca guarde su configuración.

### Sugerencias de compra: tres fuentes

El menú lateral despliega las tres fuentes de «Sugerencias de compra». El
diagnóstico de arriba (indicadores, «¿Dónde hace más falta comprar?» y la
oferta de la red por sección; en Autores y Novedades, las barras muestran en su
lugar la demanda y la actualidad de cada sección, los mismos datos de la
matriz) **es el mismo en las tres** y sirve de filtro:
al pulsar una sección, la lista de abajo se acota a ella en cualquiera de las
tres fuentes (en Autores y Novedades, el desplegable de sección se pone solo
en la sección pulsada, y al revés). Lo único que cambia
es la lista y sus filtros.

- **Presencia en bibliotecas.** Lo de siempre: títulos que tienen muchas
  bibliotecas de la red y esta no, con su presencia y sus valoraciones.
- **Autores más prestados.** De cada sección se toma el núcleo de préstamo:
  los títulos que suman la mitad de los préstamos de esa sección (criterio de
  Bradford). Se piden sus fichas a DILVE por ISBN y se recogen las demás obras
  de esos autores que la biblioteca no tiene. Se descartan las películas, las
  autorías corporativas (una editorial que figura como autora arrastra cientos
  de títulos), lo que no está a la venta, los estuches y los libros de texto,
  y se limita el número de títulos por autor. Cada propuesta dice de dónde
  sale: «Del mismo autor que "X" (94 préstamos)». Tiene sus propios filtros de
  idioma, sección y edad, con el número de títulos de cada opción. El
  cálculo se prepara en segundo plano nada más cargar los listados, y su
  resultado se guarda en la carpeta de la biblioteca: al reabrir Bildumargi no
  se vuelve a calcular ni se pide nada a DILVE mientras el núcleo de préstamo
  no cambie; para rehacerlo está el botón «Recalcular».
- **Panel superior de "Sugerencias de compra".** Es un híbrido: los cuatro
  indicadores generales del fondo (Volúmenes, Documentos por habitante,
  Índice de circulación, Editado en los últimos 5 años, siempre sobre la
  colección completa, sin los filtros de esta pestaña) más las Secciones
  prioritarias propias de este panel. Es el mismo en las tres fuentes.
- **Novedades.** Las altas de DILVE de los últimos meses, en rejilla de
  portadas, con filtros por sección (la signatura que le daría la biblioteca),
  idioma declarado, editorial, formato, «solo publicados a día de hoy» y
  «disponibles en los próximos 3 meses» (las dos activadas por defecto: se ve
  lo ya publicado más lo que sale en los próximos tres meses, ni un día más,
  y quedan fuera las preventas lejanas), por páginas de 48 libros, y
  texto (título, autor, colección, editorial, resumen y
  palabras clave, con varias palabras en cualquier orden). El formato es la
  forma física
  del libro según ONIX, con su nombre: rústica, tapa dura, libro de cartón,
  audiolibro… La casilla «Afines a lo que más se presta» las ordena por el
  préstamo que se espera de cada una en esta biblioteca (ver abajo).

**Orden por afinidad: el modelo de préstamo.** Para cada rasgo de un libro
—autor, serie, editorial o colección, cada nivel de su materia THEMA (F, FR,
FRD…), calificadores, palabras clave, tener premio— Bildumargi calcula su
tasa de préstamo en la biblioteca: préstamos entre ejemplares × años en la
estantería (el año de edición hace de fecha de alta). Es el uso relativo de
Bonn llevado al nivel de rasgo, con los nunca prestados contando como ceros y
con contracción empírico-bayesiana: un rasgo con pocos datos se acerca a lo
esperado (en THEMA, a lo de su código padre), para que dos títulos muy
prestados no conviertan a un autor en estrella. La previsión de una novedad
es la tasa de su sección corregida por sus rasgos, con más peso para el
autor y la serie que para la materia, que es lo que indica la investigación
sobre qué predice la demanda de un libro nuevo (Wang et al. 2019; Suominen
2023). La lista se reparte por secciones según el
préstamo propio (calibración de Steck, 2018) y no admite más de dos libros de
la misma serie ni tres del mismo autor en cada bloque de 50.

El autor se aprende de todo el catálogo propio; el resto de rasgos, de los
títulos propios que tienen ficha DILVE descargada. Por eso el cálculo de
«Autores más prestados» aprovecha lo que le sobra de su tope de llamadas para
descargar fichas de títulos propios de todo tipo, también nunca prestados:
cada cálculo mejora el modelo. El modelo no llama a DILVE.

El «?» junto a la casilla lo resume en dos párrafos, con los pesos que se
están usando (si la red los cambia, la explicación lo refleja).

Junto a la casilla, el enlace **«Comparar con el histórico»** hace una prueba
retrospectiva que, con lo editado antes de un año de corte, predice el
préstamo de lo editado después y compara el modelo con el perfil por materias
de la versión 1.0 (que ya no se usa para ordenar), con el orden solo por sección y
con el azar (Spearman, nDCG, AUC y proporción de nunca prestados en los
primeros puestos, con intervalos de confianza). Los pesos por defecto son
razonables pero no están validados en bibliotecas españolas: cada red puede
ajustarlos en `datos/afinidad.json` y comprobar el efecto con esa prueba.
Por ejemplo, `{"beta": {"thema": 0.9}, "ventana_anios": 4}`. El interés local
es un término de política, desactivado por defecto:
`{"local": {"prefijos": ["1DSE-ES-NA"], "peso": 0.2}}` (compruébese el código
THEMA del territorio en el buscador oficial).

Al pulsar un título se abre su ficha a la derecha. Se puede ampliar con el
botón de arriba (portada y datos lado a lado, resumen a lo ancho) o darle el
ancho que se quiera arrastrando su borde izquierdo; el ancho se recuerda. La
ficha muestra portada, autoría,
editorial, fecha, colección, sección con el motivo, idioma, resumen, palabras
clave y materias THEMA. **Bildumargi no maneja precios ni presupuestos**: de
ONIX solo se recoge lo que describe el libro.

Algunas editoriales usan el código de «mismo autor» de ONIX para anunciar su
catálogo. Bildumargi comprueba que la autoría coincide de verdad y, si no,
marca el título como «sugerido por la editorial». La red decide en
Administración si quiere verlos o no.

**Las secciones salen de las materias** (CDU si viene; si no, THEMA; si no,
IBIC) con tablas propias, una para THEMA y otra para IBIC (el mismo código
no significa lo mismo en los dos esquemas), revisadas con THEMA v1.6. Cada
red puede ajustarlas en `datos/materias_secciones.json` con las claves
`secciones` (THEMA), `ibic` e `infantil`, por ejemplo
`{"secciones": {"MKM": "6", "WH": "N"}}`. En la tabla van marcados como
«criterio» los códigos en que las bibliotecas no coinciden (psicología social,
psicoterapia, humor, urbanismo, estudios sobre cómic…): conviene que los fije
la comisión técnica de la red.

**Psicología (159.9) es una sección propia**, separada de filosofía (1): en
las signaturas, todo lo que empieza por 159.9 va a psicología y el resto de
la clase 1 a filosofía. En las materias van a psicología JM (psicología),
VS (autoayuda y desarrollo personal), VFJ y VFV (problemas personales,
relaciones y familia) y MKM (psicología clínica); la psiquiatría (MKL) sigue
en 6 y la filosofía de la mente (QDTM) en 1. Todo VX (mente, cuerpo,
espíritu, incluido lo esotérico) va a psicología, salvo las terapias
complementarias (VXH), que van a 6: ninguna materia V acaba en filosofía. Los
tramos infantiles se **calibran con la propia estantería**: se compara la
edad que declara la editorial con el tramo en el que la biblioteca coloca esos
libros. Con el fondo de Monteagudo, el acierto de los tramos pasó del 30 % al
79 %, y el de la tabla completa, del 61 % al 75 %. Lo que no se puede deducir
queda como «Infantil/juvenil sin edad» o «Sin clasificar»: nunca se inventa.

**Un libro puede estar en varias secciones.** Las editoriales suelen dar
varias materias THEMA a un mismo título: la novela gráfica de *Orgullo y
prejuicio* trae novela romántica (la principal) y novela gráfica. La sección
principal sale de la primera; las demás materias se clasifican una a una y,
si llevan a otra sección, el libro aparece también allí: en el filtro de
sección, en los recuentos y como distintivo en su tarjeta. La ficha lo indica
como «También en».

**Materias THEMA en la ficha y en el buscador.** La ficha de cada libro
muestra todas sus materias THEMA, cada una con enlace a su definición en el
[buscador oficial de EDItEUR](https://ns.editeur.org/thema/es), que incluye
la traducción al castellano de la FGEE y es el que recomienda
[DILVE](https://web.dilve.es/thema-2/thema/). En Novedades hay un filtro
«Materia (Thema)» con las materias presentes en lo descargado, en orden
alfabético y con su recuento (el «?» junto al rótulo abre el buscador oficial),
y el buscador admite códigos: `XQ` encuentra XQG, XQM y el resto de géneros
de cómic. Un código escrito en mayúsculas se busca solo entre las materias
(así `FR` no encuentra «Francia»); en minúsculas, en todo el texto.

Para ver el **encabezado** junto al código («Novela gráfica · XAM») hace falta
la lista de EDItEUR, que es gratuita y de uso libre pero no viene con
Bildumargi. Se descarga de [editeur.org](https://www.editeur.org/151/thema/)
(«categories and codes in Spanish», formato JSON o XML) y se deja en la
carpeta de datos como `thema_es.json` (o `.xml`). Sirven también un JSON
sencillo `{"FRD": "Novela romántica"}` o un CSV `código;encabezado`, y otros
idiomas con su código (`thema_en.json`); si falta el de la interfaz se usa el
castellano. Se lee al arrancar: tras copiar el fichero hay que reiniciar
Bildumargi. Con la lista cargada, el buscador encuentra también por
encabezado («novela gráfica»).

Si se deja la lista en `datos/` antes de construir el zip o el .deb, entra en
el paquete. En ese caso debe ser el **fichero oficial sin modificar**, con sus
avisos de copyright: la licencia de EDItEUR permite redistribuirlo tal cual,
pero no extractos ni versiones modificadas sin su permiso (y el de la FGEE
para la traducción). Los formatos sencillos (JSON propio o CSV) sirven solo
para uso interno de la red.

### Uso prudente de DILVE

DILVE es un servicio gratuito para bibliotecas, y conviene tratarlo con
cuidado: un volumen alto de llamadas en poco tiempo puede hacer que bloquee
la cuenta (error 1120, «Access denied. Contact DILVE's Support»). Bildumargi
lo limita así:

- **Nada se pide dos veces.** Antes de llamar a DILVE se mira en todo lo ya
  descargado: la caché de fichas (`datos/dilve/fichas.db`) y el espejo de
  novedades (`datos/dilve/novedades.db`). Los ISBN que DILVE no tiene se
  anotan y no se vuelven a pedir en 60 días.
- **Cuota diaria y pausa.** Por defecto, 300 llamadas al día como máximo y
  6 segundos entre dos llamadas, que es lo que recomienda DILVE y el mínimo
  que admite Bildumargi. Se ajustan en Administración de la red. Al llegar al
  máximo, lo que falte se pide al día siguiente.
- **Contraseña incorrecta.** Si DILVE rechaza el usuario o la contraseña, se
  deja de llamar en el acto (insistir puede hacer que bloquee la cuenta) y
  el panel de administración lo avisa. En cuanto se cambia la contraseña en
  `config.py`, en las variables de entorno o en el propio panel, y se
  reinicia Bildumargi, vuelve a funcionar solo.
- **Autores más prestados** pide como mucho 640 fichas nuevas por cálculo
  (cinco llamadas), empezando por las obras de los títulos más prestados;
  el resto se completa en cálculos posteriores.
- **Si DILVE deniega el acceso**, Bildumargi deja de llamarle y el panel de
  administración lo avisa. Hay que escribir a asistencia@dilve.es; cuando lo
  restablezcan, se pulsa «Desbloquear».

### Año de edición: un intervalo

En «Secciones» hay dos campos, «De» y «A», para acotar por año de edición.
Puestos los dos son un intervalo cerrado; con uno solo, «desde ese año en
adelante» o «hasta ese año». Los ejemplares sin año se cuentan aparte y no
entran mientras el filtro esté activo.

### Gráficos ampliables

Todos los gráficos analíticos (el peso y uso por sección, los años de edición,
el mapa de secciones, las localizaciones, la matriz de «¿Dónde hace más falta
comprar?», la oferta por sección y la evolución de Seguimiento) tienen un
cuadradito discreto arriba a la derecha, visible al pasar el ratón, que abre el
mismo gráfico en una ventana más grande. Se sigue pudiendo pulsar sobre él
igual que en el tamaño normal.

### Novedades del libro español (DILVE)

DILVE es la base de datos del libro en venta en España, que alimentan las
propias editoriales. Bildumargi la usa para saber qué se publica y poder
proponer compras. **El uso para bibliotecas es gratuito, pero hay que
solicitarlo a la Federación de Gremios de Editores de España (FGEE)**, que
asigna un usuario y una contraseña a la red.

Se configura en Administración de la red, apartado «Novedades del libro
español»:

- **Credenciales.** Lo más seguro es ponerlas en el servidor, en las variables
  de entorno `BILDUMARGI_DILVE_USUARIO` y `BILDUMARGI_DILVE_CLAVE`. Si no,
  se pueden escribir en el panel: se comprueban contra DILVE antes de
  guardarlas en `datos/dilve/credenciales.json`, que queda con permisos de
  solo lectura para quien ejecuta el servidor.
- **Qué se guarda.** Solo las **altas** (novedades), no las modificaciones de
  fichas antiguas, y **sin filtrar por idioma**: hay editoriales que no lo
  declaran, así que se descarga todo y filtra después cada biblioteca en su
  panel. Opcionalmente, solo libro en papel.
- **Cuándo.** La primera vez se descargan los meses de la ventana (3 por
  defecto). Después se actualiza sola cada 7 días, añadiendo las altas nuevas
  y retirando las que salen de la ventana; también hay botones para hacerlo a
  mano.

La base vive **siempre en `datos/dilve/novedades.db`**, con ese nombre, así que
se puede copiar de una versión de Bildumargi a la siguiente sin volver a
descargarla. Si el fichero ya está ahí al arrancar, la aplicación no lo
vuelve a descargar: solo lo actualiza cuando toca.

De cada novedad se guardan ISBN, título, autoría (con ISNI si lo trae),
editorial, colección, idioma, formato, páginas, materias THEMA, edad
recomendada, fecha, precio, disponibilidad, resumen y la dirección de la
cubierta. Con unos 1.000 títulos, la base ocupa medio megabyte.

Las condiciones de uso de DILVE son suyas: antes de mostrar cubiertas o
resúmenes fuera del personal de la biblioteca, conviene confirmarlo por
escrito con la FGEE.

### Pestaña «Seguimiento»

Con el historial activado, cada carga se guarda y la pestaña «Seguimiento»
muestra la evolución de volúmenes, circulación, fondo de los últimos 5 años y
año medio de edición, carga a carga, con el cambio respecto a la anterior.
Desde ahí se puede **reabrir una carga anterior** sin volver a subir los
ficheros, o borrarla. Las cargas sin listado de no prestados no tienen dato de
circulación y no se dibujan en esa serie.

Los listados que usa Bildumargi describen ejemplares (signatura, código de
barras, título, préstamo sí/no), **no lectores**: no contienen datos
personales. Aun así, solo se guardan si la red activa el historial, se
conservan las últimas N cargas y cada biblioteca puede borrar las suyas.

## Demostración sin instalar nada (equipos bloqueados)

Para enseñar Bildumargi en un equipo donde no se puede instalar ni ejecutar
ningún programa, se puede crear una **demo**: una carpeta que se abre con
doble clic en «Abrir Bildumargi.html», en Edge o Chrome, igual que un PDF.
No arranca ningún servidor ni ejecuta nada: los resultados van ya calculados
dentro de la carpeta.

Se prepara en un ordenador donde Bildumargi sí funcione:

1. Arranca Bildumargi y abre `http://127.0.0.1:8765/?grabar_demo=1`. Abajo a
   la izquierda aparece el panel «Grabando la demo».
2. Carga y analiza los listados de la biblioteca **con la grabación ya
   activa**.
3. Pulsa «Recorrido automático» y espera (unos minutos): recorre todas las
   pestañas, secciones, fuentes de sugerencias —también las de DILVE, con lo
   que ya tengas descargado— y sus filtros, y graba las fichas de lo que
   aparece. Puedes pulsar además, a mano, cualquier cosa que quieras enseñar.
4. Abre «Administración de la red» con tu clave, para grabarla también.
5. Pulsa «Descargar grabación» (`bildumargi-grabacion.json`).
6. Desde la carpeta de Bildumargi, ejecuta
   `python crear_demo.py "ruta\a\bildumargi-grabacion.json"`. En un segundo
   crea la carpeta `Bildumargi-demo` y el zip, con su huella SHA-256, junto a
   la grabación (o donde indique `--salida`). La demo va **sin portadas**:
   en su lugar se ve el marcador con la inicial, y así no intenta conectarse
   a internet. Con `--con-portadas` se descargan e incluyen, aunque puede
   tardar mucho. Si la demo anterior está abierta y no se puede borrar, se
   crea otra al lado con la fecha en el nombre.

En la demo, el asistente de carga funciona igual, pero al pulsar «Analizar»
muestra los resultados ya calculados; la administración admite cualquier
clave; lo que no se grabó muestra un aviso en lugar de fallar. La lista
completa de ejemplares para CSV no se incluye, para que la demo pese poco.

## Traducciones

Todos los textos de la interfaz están en `frontend/js/i18n.js`, un bloque por
idioma (`es`, `eu`, `ca`, `gl`, `en`) con las mismas claves. Los marcadores entre
llaves (`{n}`, `{s}`…) se sustituyen por datos y deben conservarse tal cual.
Al final del mismo fichero están los nombres de sección y de lengua de cada
idioma. Cualquier corrección terminológica se hace en ese fichero, sin tocar
nada más. El inglés usa ortografía británica y escribe
los números a la inglesa (10,112 · 32.9%); los otros cuatro, con punto de
miles y coma decimal. Para añadir un idioma, se copia el bloque `es`
con un código nuevo, se traduce y se añade a `IDIOMAS_INTERFAZ`.

## Los cuatro listados de AbsysNet

Se cargan con un asistente, un fichero por pantalla: **Siguiente** avanza y,
en los opcionales, **Omitir** los salta. Cada paso explica qué aporta el
fichero, qué se pierde si se omite y enlaza un vídeo que enseña a obtenerlo.
Al final, un resumen muestra lo cargado y lo omitido antes de analizar; desde
ahí se puede volver a cualquier paso.

| Listado | ¿Obligatorio? | Qué aporta | Si se omite |
|---|---|---|---|
| Topográfico de ejemplares | Sí | La colección: signatura, código de barras, localización. | No se puede analizar. |
| Catálogo | No, muy recomendable | Año de edición, autor, ISBN y materias. | Análisis en «modo reducido». |
| No prestados | No, muy recomendable | Marca lo que no ha salido en préstamo en el periodo. | Todo cuenta como prestado: la circulación y el uso relativo **no son reales**. El panel lo avisa. |
| Más prestados | No | Marca los títulos de alta demanda. | No se distingue la alta demanda del préstamo normal. |

Expórtalos **en `.txt`** y súbelos tal cual: no los abras ni los guardes con
Excel, porque se pierde el formato de columnas.

Si tienes un fondo grande y AbsysNet no te deja exportar el catálogo completo de
una vez, puedes subir **varios ficheros a la vez** en el hueco del catálogo: se
concatenan solos y el orden da igual.

No importa si te equivocas de paso al subirlos: Bildumargi identifica cada
fichero por su contenido, lo recoloca y avisa de lo que ha hecho.

---

## Valoraciones y conversación entre bibliotecas

Cada biblioteca puede puntuar del 1 al 5 y comentar cualquier título de la
red, y **responder a los comentarios de las demás** en hilos cortos («¿lo
tenéis en JN o en adultos?»). Se hace desde la ficha del título, que se abre:

- en **Sugerencias de compra**, al pulsar un título que te falta;
- en **Secciones**, al pulsar un ejemplar de tu propio fondo (si está
  enlazado con el catálogo de la red), así que también se valora lo que ya
  tienes;
- en la pestaña **Red**, que reúne la actividad reciente de todas las
  bibliotecas (con filtros para ver solo las respuestas a tus comentarios o
  solo lo que ha escrito tu biblioteca), los títulos mejor valorados (con al
  menos dos puntuaciones) y los más comentados.

Todo se firma con el nombre de la biblioteca, que Bildumargi ya deduce del
código de sucursal de los listados: no hay registro, ni contraseñas, ni se
guarda ningún dato personal. Cada biblioteca tiene una valoración por título,
que puede reeditar o borrar, y puede borrar sus propias respuestas. Si borra
su valoración, se borran también las respuestas que colgaban de ella.

**Normas de uso**, visibles junto a cada formulario: se comentan libros, no
personas; no se escriben nombres de lectores ni datos personales. Como la
firma se deduce de los listados cargados, el sistema está pensado para una
intranet de confianza, no para publicarse en internet.

**Esto solo tiene sentido en un despliegue central.** Si cada biblioteca
ejecuta su copia en su ordenador, las valoraciones se quedan en esa máquina y
no las ve nadie más. Para que la función sirva, una biblioteca —normalmente la
central— debe ejecutar Bildumargi en un servidor al que entren las demás por la
intranet (ver el apartado siguiente). Si no es tu caso, pon
`VALORACIONES_ACTIVAS = False` en `config.py` y la sección desaparece.

Se guardan en `datos/valoraciones.db`, **deliberadamente separado del `.db` del
catálogo**: ese se regenera con `conversor.py` cada vez que se actualiza el
fondo, y si las valoraciones vivieran ahí se borrarían en cada actualización.
Es el único fichero del paquete con información que no se puede reconstruir:
**inclúyelo en la copia de seguridad del servidor.**

La carpeta `datos/` debe tener permiso de escritura para el usuario que ejecuta
el servidor. Si no lo tiene, la aplicación arranca igual y avisa de que las
valoraciones no están disponibles, sin romper nada más.

## Ponerlo en un servidor o una intranet

Para que otras bibliotecas lo usen desde sus equipos sin instalar nada:

1. Copia la carpeta al servidor.
2. En `config.py`, cambia `HOST = "127.0.0.1"` por `HOST = "0.0.0.0"`, y el
   `PUERTO` si el 8000 está ocupado.
3. Arranca con `python iniciar.py`, o directamente con uvicorn si quieres
   controlar los procesos:

```
python -m uvicorn backend.servidor:app --host 0.0.0.0 --port 8000
```

Las demás bibliotecas entran en `http://IP-DEL-SERVIDOR:8000`. Cada una sube
sus propios listados y ve solo su análisis; las sesiones viven en memoria y
caducan a las tres horas (`MINUTOS_SESION` en `config.py`).

La aplicación **no necesita salida a internet**: los gráficos están dibujados a
mano en SVG y no se carga ninguna librería externa. Lo único que intenta
descargarse de fuera son las tipografías de Google Fonts, y si no hay conexión
el respaldo del sistema mantiene el mismo aspecto. Si la base de datos la pones
como fichero local en vez de como URL, funciona completamente aislada.

---

## Qué hay en cada carpeta

```
config.py            Configuración. La línea 34 es el enlace a la base de datos.
iniciar.py           Arranque. Doble clic en iniciar.bat (Windows) o ./iniciar.sh.
conversor.py         MARC -> .db. Necesario solo para las sugerencias de compra.
requirements.txt     Librerías necesarias.

backend/             Lógica en Python.
  absysnet.py          Lectura de los cuatro listados.
  clasificacion.py     Motor de tejuelo. Todas las reglas de signatura viven aquí.
  analisis.py          Métricas, agregados y búsqueda sobre la colección.
  recomendaciones.py   Sugerencias de compra contra el catálogo colectivo.
  basedatos.py         Acceso a la base SQLite de la red.
  bibliotecas.py       Lectura del Excel de bibliotecas.
  idiomas.py           Idioma del documento desde el MARC 008.
  servidor.py          API y arranque del servidor web.

frontend/            Interfaz web en JavaScript.
  js/i18n.js           Todos los textos, en castellano y euskera.
  fuentes/             Tipografías alojadas en local (no depende de internet).

datos/
  bibliotecas.xlsx     El directorio que tienes que rellenar.
  pautas.json          Referencia de fondo por habitante (configurable por red).
  configuracion_red.json   Lo que decide la red (se crea al guardar en Administración).
  dilve/novedades.db   Novedades descargadas de DILVE (se crea sola; se puede copiar).
  dilve/fichas.db      Fichas de DILVE por ISBN, compartidas por toda la red.
                       Guarda también qué ISBN no reconoce DILVE, para no
                       volver a pedirlos en cada consulta.
  materias_secciones.json  Tabla propia materias -> signatura (opcional).
  thema_es.json        Encabezados THEMA de EDItEUR (opcional; ver «Sugerencias de compra»).
  afinidad.json        Parámetros del orden por afinidad (opcional).
  bibliotecas/         Una carpeta por biblioteca: preferencias e historial de cargas.
```

---

## Si algo no va

**«No se reconoce el fichero»** — Es una exportación distinta de las cuatro
esperadas, o se ha guardado con Excel. Vuelve a exportarlo en `.txt` desde
AbsysNet sin abrirlo por el camino.

**«El código de sucursal detectado no figura en el directorio»** — El número de
la columna «Suc.» de tus listados no está en `datos/bibliotecas.xlsx`. Añádelo.

**«El topográfico y el catálogo no comparten ningún registro»** — Los dos
ficheros son de bibliotecas o fechas distintas. Vuelve a exportarlos juntos.

**Las recomendaciones proponen títulos que ya tienes** — El nombre de tu
biblioteca en el Excel no coincide exactamente con el del campo 952 del
catálogo. La propia aplicación avisa de esto y sugiere los nombres parecidos que
ha encontrado en la base.

**El puerto 8000 está ocupado** — Cambia `PUERTO` en `config.py`.

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
