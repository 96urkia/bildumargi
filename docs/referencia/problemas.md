# Problemas frecuentes

??? question "Windows dice «Windows protegió su PC» al instalar"
    Es normal en programas libres sin firma digital comercial. Pulsa **Más
    información** y después **Ejecutar de todas formas**.

??? question "La ventana de Bildumargi no se abre, o se abre en el navegador"
    La ventana propia usa WebView2, el motor de Edge que trae Windows. Si
    falta, Bildumargi se abre en el navegador y funciona igual. Los mensajes
    del programa están en `%LOCALAPPDATA%\Bildumargi\datos\registro.txt`.

??? question "«No se reconoce el fichero»"
    Es una exportación distinta de las cuatro esperadas, o se ha guardado con
    Excel. Vuelve a exportarla en `.txt` desde AbsysNet sin abrirla.

??? question "«Estos listados son de la sucursal X, pero Bildumargi tiene apuntada la Y»"
    Has subido listados de otra biblioteca. Se analizan, pero no se guardan
    en el historial. Si has cambiado de biblioteca de verdad, pulsa **Olvidar
    la sucursal** en [Configuración](../uso/configuracion.md) y vuelve a
    cargarlos.

??? question "«El topográfico y el catálogo no comparten ningún registro»"
    Los dos ficheros son de bibliotecas o fechas distintas. Vuelve a
    exportarlos juntos.

??? question "La circulación sale al 100 %"
    Falta el listado de no prestados: sin él, todo cuenta como prestado. El
    panel lo avisa.

??? question "No hay documentos por habitante"
    Falta la población. Escríbela en [Configuración](../uso/configuracion.md),
    apartado **Tu biblioteca**.

??? question "No aparece la pestaña Sugerencias de compra"
    Falta la cuenta de DILVE. Ver [DILVE](../administracion/dilve.md).

??? question "Muchos ejemplares salen con idioma «Sin determinar»"
    Descarga las [fichas de DILVE de todo el catálogo](../administracion/dilve.md#fichas-de-todo-el-catalogo)
    y, si puedes, conecta el [catálogo MARC](../administracion/catalogo-marc.md):
    DILVE no tiene muchos libros antiguos.

??? question "En Series salen tomos como «Falta» que sí tengo"
    Ese libro no tiene ISBN, o su ficha de DILVE aún no se ha descargado, así
    que no se le puede poner número. Mira si aparece como «Posiblemente de
    esta serie» y descarga las fichas del catálogo.

??? question "Una colección de editorial sale como serie"
    En su detalle, pulsa **No es una serie: ocultarla**.

??? question "Las altas y bajas no cuadran con los volúmenes"
    Ver [Seguimiento](../uso/seguimiento.md#altas-y-bajas): los volúmenes
    dependen del catálogo exportado; las altas y bajas, del topográfico.

??? question "Con el zip, el puerto 8000 está ocupado"
    Pon otro `PUERTO` en `config_local.py`.
