# Población

La pestaña **Población** evita escribir a mano los habitantes: con el código
postal de la biblioteca, Bildumargi descarga del Instituto Nacional de
Estadística (INE) los habitantes y la demografía del municipio.

## Poner el código postal

1. Escribe el código postal y pulsa **Buscar**.
2. Si abarca varios municipios, marca los que atiende la biblioteca: sus datos
   se suman. El código 31522, por ejemplo, incluye Monteagudo y Tulebras.
3. Pulsa **Usar estos municipios**.

Hace falta conexión con `servicios.ine.es` para la primera descarga. Después se
trabaja con una copia guardada, que se renueva cada 30 días o con
**Actualizar ahora**. Si el INE no responde, se usa la última copia y se avisa.

## Qué se ve

Todo en una pantalla, con cuatro gráficos. A la izquierda, la edad; a la derecha, la
procedencia. Arriba, la población; abajo, su cotejo con el fondo.

- **Habitantes** y su evolución en los últimos diez años.
- **Edad media**, menores de 15 años, mayores de 65 y de 80.
- **Pirámide de población** por sexo y tramos de cinco años.
- **Población de origen extranjero**, por país: por nacionalidad y por lugar de
  nacimiento, que son cosas distintas.

Si no caben todos los países, los últimos se suman en una fila «Resto». Están al
pasar el ratón por ella y completos en **Descargar CSV**.

## Por qué hay dos cifras de población

Los **habitantes** son las cifras oficiales del Padrón, y son los que se usan
para los documentos por habitante. La **composición** por edad y procedencia
sale del Censo anual de población, que cuenta de otra manera. Por eso las dos
cifras no coinciden del todo.

## Cotejo con el fondo

- **Por edad**: tres columnas por público (infantil, juvenil y adultos): su peso
  entre los vecinos, en el fondo y en los documentos prestados. El público del
  fondo sale de la signatura, y su edad es una equivalencia aproximada.
- **Por lengua**: el peso de la lengua en el fondo dividido entre su peso en el
  municipio (personas nacidas en países con esa lengua oficial principal). Con
  1,0 pesa lo mismo; a la izquierda, menos; a la derecha, más.

En Navarra se añade una fila de **euskera**, arriba y separada: se mide con las
personas de 3 años o más que lo hablan o lo entienden, no con el país de nacimiento.
Fuente: Nastat, *Estadística de población según conocimiento de euskera*, 2022.

Los tramos de edad son 0-14, 15-17 y 18 o más.

No hay ninguna pauta detrás de estas comparaciones: describen, no valoran. El
INE no pregunta la lengua de nadie, así que la asignación por país es solo
orientativa. Si se conoce el idioma de menos de la mitad del fondo, la pantalla
avisa de que esas cifras aún no sirven para comparar: hacen falta el catálogo
MARC o las fichas de DILVE.

## Limitaciones

Los datos son del **municipio entero**. Si la biblioteca atiende solo a una parte
(un barrio de una ciudad), pulsa **Dejar de usar el INE** en
[Configuración](configuracion.md) y escribe los habitantes a mano. Mientras se use
el INE, los habitantes del análisis son siempre los del Padrón.
