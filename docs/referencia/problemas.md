# Problemas frecuentes

??? question "«No se reconoce el fichero»"
    Es una exportación distinta de las cuatro esperadas, o se ha guardado con
    Excel. Vuelve a exportarla en `.txt` desde AbsysNet sin abrirla.

??? question "«El código de sucursal detectado no figura en el directorio»"
    El número de la columna «Suc.» de tus listados no está en
    `bibliotecas.xlsx`. La administración de la red debe añadirlo.

??? question "«El topográfico y el catálogo no comparten ningún registro»"
    Los dos ficheros son de bibliotecas o fechas distintas. Vuelve a
    exportarlos juntos.

??? question "La circulación sale al 100 %"
    Falta el listado de no prestados: sin él, todo cuenta como prestado. El
    panel lo avisa.

??? question "No aparece la pestaña Sugerencias de compra"
    La red no ha conectado el catálogo colectivo. Ver
    [Catálogo colectivo de la red](../administracion/catalogo-red.md).

??? question "No veo el panel «Entrar con clave»"
    La red no ha puesto claves en el directorio o no tiene activado el
    historial de cargas.

??? question "Las valoraciones no las ven otras bibliotecas"
    Bildumargi está instalado en un ordenador, no en un servidor común. Las
    valoraciones solo se comparten en una instalación central.

??? question "El puerto 8000 está ocupado"
    Cambia `PUERTO` en `config.py`.

!!! note "Pendiente de completar"
    Añade los problemas que vayan apareciendo en las bibliotecas piloto.
