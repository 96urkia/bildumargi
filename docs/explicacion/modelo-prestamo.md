# El modelo de préstamo

La opción **Afines a lo que más se presta** de Novedades ordena los libros por
el préstamo que cabe esperar de cada uno en tu biblioteca. Esta página explica
cómo.

## La idea

Para cada **rasgo** de un libro, Bildumargi mira cuánto se prestan en tu
biblioteca los títulos que lo comparten:

- el **autor** y la **serie**;
- la **editorial** o colección;
- cada nivel de su **materia Thema** (F, FR, FRD…);
- los **calificadores** Thema (lugar, época, edad);
- las **palabras clave**;
- si tiene **premio**.

Cada rasgo recibe una **tasa de préstamo**: préstamos entre ejemplares por
años en la estantería. Es el [uso relativo](uso-relativo.md) llevado del nivel
de sección al nivel de rasgo.

## Prudencia con pocos datos

Un autor con dos títulos muy prestados no debe convertirse en una apuesta
segura. Por eso, un rasgo con pocos datos se acerca a lo esperado: a lo
habitual de su sección o, en Thema, a lo de su materia más general. Es lo que
en estadística se llama **contracción bayesiana empírica**. Los títulos que
nunca se han prestado cuentan como ceros, porque informan tanto como los muy
prestados.

## Por qué el autor pesa más

Los estudios sobre qué predice la demanda de un libro nuevo coinciden en que
**el historial del autor** explica mucho más que el género o el tema: los
lectores siguen a autores y sagas (Wang et al., 2019; Suominen, 2023). Por eso
autor y serie pesan más que la materia.

## El reparto final

La lista se reparte entre secciones de forma parecida a como se reparte tu
préstamo (calibración de Steck, 2018) y no admite más de dos libros de una
misma serie ni tres de un mismo autor por cada 50.

## Límites

- **Favorece lo que ya funciona**: no conoce a los lectores que todavía no
  vienen. Es una ayuda para seleccionar, no una decisión.
- **Necesita fichas**: el autor se aprende de todo tu catálogo, pero el resto
  de rasgos solo de los títulos propios con ficha DILVE descargada.
- **Los pesos son razonables, no validados** en bibliotecas españolas. Cada
  red puede ajustarlos y comprobar el efecto con **Comparar con el histórico**.

## Referencias

- Bonn, G. S. (1974). Evaluation of the collection. *Library Trends*, 22(3), 265–304.
- Steck, H. (2018). Calibrated recommendations. *Proceedings of ACM RecSys*. <https://doi.org/10.1145/3240323.3240372>
- Suominen, S. (2023). Novel genre explaining borrowings from the public libraries. *Informaatiotutkimus*.
- Wang, X. et al. (2019). Success in books: predicting book sales before publication. *EPJ Data Science*, 8, 31.
