# Licencia de Bildumargi

Bildumargi © 2026 Asier Urkia · bildumargi@gmail.com

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los
términos de la **Licencia Pública General Affero de GNU (AGPL), versión 3**,
publicada por la Free Software Foundation. El texto completo y vinculante está
en el fichero `LICENSE`; lo que sigue es solo un resumen orientativo.

Se distribuye con la esperanza de que sea útil, pero **SIN NINGUNA GARANTÍA**,
ni siquiera la garantía implícita de comerciabilidad o idoneidad para un
propósito particular. Ver la licencia para más detalles.

## Qué puedes hacer

- Usarlo para cualquier fin, también en una biblioteca o una administración
  pública, sin pagar nada y sin pedir permiso.
- Estudiar cómo funciona y adaptarlo a tu red, a tu sistema de gestión o a tus
  esquemas de signaturas.
- Redistribuirlo, con o sin cambios.

## Con qué condiciones

- **Mismo licencia.** Si distribuyes el programa, con o sin modificaciones,
  debes hacerlo bajo la AGPLv3, no bajo otra distinta ni con restricciones
  añadidas.
- **Código fuente.** Quien reciba el programa tiene derecho a recibir también
  su código fuente, incluidas tus modificaciones.
- **Atribución y constancia de los cambios.** Debes conservar los avisos de
  copyright y dejar constancia de que has modificado el programa y de cuándo.
- **Uso en red (cláusula 13, la propia de la AGPL).** Si modificas Bildumargi y
  lo pones a disposición de otras personas a través de una red —una intranet,
  un servidor de la red de bibliotecas, un despliegue público— debes ofrecer a
  quienes lo usen la posibilidad de descargar el código fuente de tu versión
  modificada. Esta es la diferencia con la GPL corriente: sin ella, alguien
  podría mejorar el programa, servirlo por web a cientos de bibliotecas y no
  devolver nada.

Para cumplir la cláusula 13, la aplicación muestra en el pie de página un
enlace **«Código fuente»**. Si despliegas una versión modificada, apunta
`URL_CODIGO_FUENTE` en `config.py` a un sitio donde pueda descargarse tu
versión. Si lo usas sin modificar, el enlace por defecto ya sirve.

## Por qué AGPL y no una licencia Creative Commons

Las licencias Creative Commons no están pensadas para software, y la propia
Creative Commons desaconseja usarlas con este fin: no distinguen entre código
fuente y binario ni regulan el uso en red. La AGPLv3 garantiza lo mismo que
buscaba una BY-SA —atribución y que las copias mantengan la licencia— con
términos escritos específicamente para programas, y añade la garantía de que
las mejoras hechas sobre un servicio web vuelvan a la comunidad.

Ten en cuenta que la AGPL **no prohíbe el uso comercial**: una empresa puede
cobrar por instalarlo o darle soporte. Lo que no puede es quedarse el código
para sí ni relicenciarlo.

## Cómo citarlo

> Bildumargi, de Asier Urkia (bildumargi@gmail.com), bajo licencia AGPLv3.

## Componentes de terceros

| Librería | Licencia |
|---|---|
| FastAPI | MIT |
| Uvicorn | BSD 3-Clause |
| Starlette | BSD 3-Clause |
| python-multipart | Apache 2.0 |
| openpyxl | MIT |
| pymarc (solo `conversor.py`) | BSD 2-Clause |

Todas son compatibles con la AGPLv3 y permiten su distribución conjunta.

Las tipografías Public Sans e IBM Plex Mono se cargan desde Google Fonts y
están bajo SIL Open Font License 1.1. La aplicación funciona sin ellas si no
hay conexión a internet.

El listado de la CDU incluido en `datos/` procede de la traducción al
castellano de la Clasificación Decimal Universal de uso común en las
bibliotecas públicas españolas, recogido aquí para dar nombre a los códigos
numéricos.
