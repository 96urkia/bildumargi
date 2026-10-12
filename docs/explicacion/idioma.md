# El idioma de cada ejemplar

Los listados de AbsysNet no traen el idioma. Bildumargi lo toma, para cada
ejemplar, de la primera de estas fuentes que lo diga:

1. **El catálogo MARC** (campo 008, posiciones 35-37), si se ha extraído
   (ver [Catálogo MARC](../administracion/catalogo-marc.md)) y el código es
   válido. Describe el ejemplar concreto y cubre casi todo el fondo, también
   lo antiguo.
2. **La ficha de DILVE** del libro, por ISBN, de lo ya descargado. Cubre las
   novedades que aún no están catalogadas y corrige los errores de
   catalogación (códigos inexistentes como «esp» en vez de «spa»).
3. **La signatura**, solo cuando lo dice sin duda: su **primera palabra** es
   una marca de lengua (`EUS N ATX`, `ENG I1 ALO`). En otra posición no
   cuenta: en `342.7 EUS`, «EUS» es el autor o el tema.

Si ninguna lo dice, el ejemplar queda como **Sin determinar**: nunca se
inventa.

## Por qué combinar

DILVE describe bien lo que está a la venta, pero no tiene muchos libros
antiguos o descatalogados. El MARC describe casi todo, con algún error de
catalogación. Cuando los dos dan dato, coinciden en casi todos los casos; los
desacuerdos suelen ser códigos mal puestos en el catálogo o libros bilingües.

| Con el fondo de una biblioteca pequeña | Idioma conocido |
|---|---|
| Solo DILVE | 45 % |
| DILVE y catálogo MARC | 99 % |

La ficha de cada ejemplar dice de dónde sale su idioma.
