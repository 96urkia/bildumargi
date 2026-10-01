# -*- coding: utf-8 -*-
"""Propuestas de compra a partir de DILVE.

Dos fuentes, además de la que ya existía (títulos que tiene la red y esta
biblioteca no):

  Autores más prestados
      Del listado «Más prestados» se toma el núcleo de cada sección: los
      títulos que suman la mitad de los préstamos de esa sección (criterio de
      Bradford, el mismo que se usa en bibliometría para el núcleo de
      revistas). Se piden sus fichas a DILVE por ISBN y se leen sus productos
      relacionados «del mismo autor» (ONIX, lista 51, código 22). Se comprueba
      que el autor coincide de verdad, porque algunas editoriales usan ese
      código para anunciar su catálogo: lo que no coincide se marca como
      «sugerido por la editorial» y cada red decide si quiere verlo.

  Novedades
      Las altas recientes de DILVE, filtrables por sección, idioma declarado,
      editorial y formato, con la opción de ordenarlas por parecido con lo que
      más se presta en la biblioteca.

Las fichas se guardan en una caché común a toda la red: los superventas se
repiten de una biblioteca a otra, así que casi siempre están ya descargadas.

Aquí no hay precios ni presupuestos: Bildumargi describe la colección y
sugiere compras, pero no gestiona el gasto.
"""

import collections
import time
import math
import re
import unicodedata

from backend import materias as mod_materias

RELACIONADOS_POR_TITULO = 20        # tope por título: hay autorías con cientos
# Fichas NUEVAS que se piden a DILVE en cada cálculo (el resto ya está guardado).
# Cinco llamadas como mucho: lo que no quepa se pide en cálculos posteriores,
# empezando siempre por las obras de los títulos más prestados.
MAX_FICHAS_NUEVAS = 640
MINIMO_POR_SECCION = 3              # para que ninguna sección se quede fuera
PALABRAS_VACIAS = {"de", "la", "el", "los", "las", "y", "en", "del", "un", "una", "para", "con",
                   "por", "al", "su", "sus", "lo", "que", "o", "a", "eta", "the", "of", "sobre"}
_ESPECIAL = re.compile(r"estuche|\bpack\b|edici[oó]n (limitada|especial|coleccionista|de lujo)|"
                       r"\blote\b|caja regalo|box set", re.I)
_CORPORATIVO = re.compile(r"^(dk|vv\s*aa|aa\s*vv|varios|na|anonimo|editorial|equipo|mcgraw|"
                          r"disney|planeta|oxford|santillana|sm|anaya|larousse|susaeta)\b")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def normaliza(texto):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def apellido(nombre):
    n = normaliza(nombre)
    return n.split(" ")[0] if n else ""


def isbn13(valor):
    """Normaliza a ISBN-13; convierte los de 10 dígitos."""
    d = re.sub(r"[^0-9Xx]", "", str(valor or "")).upper()
    if len(d) == 10:
        base = "978" + d[:9]
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))
        return base + str((10 - total % 10) % 10)
    return d if len(d) == 13 else None


def autor_de(ficha):
    for c in ficha.get("contribuidores") or []:
        if c.get("rol") in ("A01", None):
            return c.get("invertido") or c.get("nombre") or ""
    return ""


def es_autor_corporativo(nombre):
    """Editoriales y colectivos que figuran como autoría: sus «mismo autor»
    son el catálogo entero de la casa, no la obra de una persona."""
    return (not nombre) or ("," not in nombre) or bool(_CORPORATIVO.match(normaliza(nombre)))


def _claves(ficha):
    return [m["texto"] for m in ficha.get("materias") or []
            if m.get("esquema") == "20" and m.get("texto")][:8]


def _thema(ficha):
    """Todos los códigos THEMA de materia, la principal primero y sin repetir.
    Antes se cortaba en seis y se perdían géneros (cómic, novela gráfica…)."""
    materias = [m for m in ficha.get("materias") or [] if m.get("esquema") == "93" and m.get("codigo")]
    materias.sort(key=lambda m: 0 if m.get("principal") else 1)
    return list(dict.fromkeys(m["codigo"].strip().upper() for m in materias))


def _texto_thema(ficha, encabezados=None):
    """Códigos y encabezados THEMA, para que el buscador los encuentre."""
    partes = []
    for codigo in _thema(ficha):
        partes.append(codigo)
        if encabezados:
            partes.extend(encabezados.nombres(codigo))
    return " ".join(partes)


def _coincide_palabra(palabra, fondo, codigos, encabezados=None):
    """Una palabra de búsqueda escrita EN MAYÚSCULAS que es un código THEMA
    conocido se busca solo entre los códigos del libro, por prefijo («XQ»
    encuentra XQG y XQM) y sin confundirse con «Francia» al buscar «FR».
    El resto, como siempre: en cualquier parte del texto."""
    if encabezados and palabra.isupper() and encabezados.es_codigo(palabra):
        return any(c.startswith(palabra) for c in codigos)
    return normaliza(palabra) in fondo


def secciones_de(propuesta):
    """Sección principal más las que salen de las otras materias THEMA."""
    return [propuesta.get("seccion")] + [s for s, _ in propuesta.get("otras_secciones") or []]


def _idioma(ficha):
    """Solo el idioma que declara la editorial. Cuando falta, DILVE presupone
    castellano; aquí no se presupone nada."""
    return ficha.get("idioma") if ficha.get("idioma_declarado") else None


def ficha_a_propuesta(ficha, opciones, extra=None):
    extra = extra or {}
    if "seccion" in extra:                  # ya calculado por quien llama
        seccion, motivo = extra["seccion"], extra.get("motivo_seccion")
    else:
        seccion, motivo = mod_materias.clasificar(ficha, opciones.get("calibracion"), opciones.get("tablas"))
    otras = extra["otras_secciones"] if "otras_secciones" in extra else mod_materias.otras_secciones(
        ficha, seccion, opciones.get("calibracion"), opciones.get("tablas"))
    edad, _ = mod_materias.edad_declarada(ficha)
    propuesta = {
        "isbn": ficha.get("isbn"), "titulo": ficha.get("titulo"), "subtitulo": ficha.get("subtitulo"),
        "autor": autor_de(ficha) or ficha.get("autor_principal"),
        "editorial": ficha.get("editorial") or ficha.get("sello"),
        "fecha": ficha.get("fecha_publicacion"), "coleccion": ficha.get("coleccion"),
        "paginas": ficha.get("paginas"), "forma": ficha.get("forma"),
        "idioma": _idioma(ficha), "edad": edad,
        "seccion": seccion, "motivo_seccion": motivo, "otras_secciones": otras,
        "cubierta": ficha.get("cubierta"), "resumen": ficha.get("resumen"),
        "claves": _claves(ficha), "thema": _thema(ficha),
        "premios": [p["nombre"] for p in ficha.get("premios") or [] if p.get("nombre")],
    }
    propuesta.update(extra)
    return propuesta


def _descartar(ficha, opciones, propios_isbn, propios_clave, descartes):
    """Filtros comunes a las dos fuentes. Devuelve el motivo del descarte o None."""
    isbn = ficha.get("isbn")
    if isbn in propios_isbn:
        return "ya en el fondo"
    clave = (apellido(autor_de(ficha)), normaliza(ficha.get("titulo"))[:40])
    if clave in propios_clave:
        return "ya en el fondo (autor y título)"
    if opciones.get("solo_papel", True) and not (ficha.get("forma") or "").upper().startswith("B"):
        return "no es libro en papel"
    if opciones.get("solo_en_venta", True) and ficha.get("estado") not in (None, "", "02", "04"):
        return "no está a la venta"
    if opciones.get("excluir_especiales", True) and (
            (ficha.get("composicion") or "00") != "00" or _ESPECIAL.search(ficha.get("titulo") or "")):
        return "estuche o edición especial"
    idioma = _idioma(ficha)
    idiomas = opciones.get("idiomas") or []
    if idioma and idiomas and idioma not in idiomas:
        return f"idioma {idioma}"
    if not idioma and not opciones.get("incluir_sin_idioma", True):
        return "idioma sin indicar"
    return None


# ---------------------------------------------------------------------------
# Núcleo de préstamo (Bradford)
# ---------------------------------------------------------------------------
def nucleo_prestamo(registros, fraccion=0.5, minimo_por_seccion=MINIMO_POR_SECCION):
    """Por sección, los títulos que suman `fraccion` de los préstamos.

    Si el listado de más prestados no trae el número de préstamos, cada
    ejemplar de alta demanda cuenta como uno. En las secciones pequeñas entran
    todos los empates: así ninguna se queda sin representación."""
    por_titulo = {}
    for r in registros:
        veces = r.get("n_prestamos") or (1 if r.get("prestamos") == 2 else 0)
        if veces <= 0:
            continue
        if r.get("es_audiovisual") or "DVD" in str(r.get("categoria_estandar") or r.get("categoria") or ""):
            continue                                   # las películas no se cruzan con DILVE
        isbn = isbn13(r.get("isbn"))
        clave = isbn or f"{normaliza(r.get('autor'))[:20]}|{normaliza(r.get('titulo'))[:40]}"
        t = por_titulo.setdefault(clave, {"isbn": isbn, "titulo": r.get("titulo"),
                                          "autor": r.get("autor"), "seccion": r.get("categoria_estandar") or r.get("categoria"),
                                          "prestamos": 0, "ejemplares": 0})
        t["prestamos"] += veces
        t["ejemplares"] += 1

    por_seccion = collections.defaultdict(list)
    for t in por_titulo.values():
        por_seccion[t["seccion"]].append(t)
    nucleo = []
    for titulos in por_seccion.values():
        titulos.sort(key=lambda t: (-t["prestamos"], t["titulo"] or ""))
        objetivo = sum(t["prestamos"] for t in titulos) * fraccion
        acumulado, corte = 0, 0
        for i, t in enumerate(titulos):
            acumulado += t["prestamos"]
            corte = i
            if acumulado >= objetivo:
                break
        umbral = titulos[corte]["prestamos"]
        dentro = [t for t in titulos if t["prestamos"] >= umbral]
        if len(dentro) < minimo_por_seccion:
            dentro = titulos[:minimo_por_seccion]
        nucleo.extend(dentro)
    nucleo.sort(key=lambda t: -t["prestamos"])
    return nucleo


# ---------------------------------------------------------------------------
# Perfil de la biblioteca (para ordenar las novedades por parecido)
# ---------------------------------------------------------------------------
def perfil(fichas_nucleo, nucleo):
    """Qué materias, palabras clave, editoriales y colecciones funcionan aquí.

    Cada rasgo pesa según los préstamos de los títulos en que aparece, así que
    un autor con un solo ejemplar muy prestado no arrastra el perfil."""
    prestamos_de = {t["isbn"]: t["prestamos"] for t in nucleo if t.get("isbn")}
    pesos = collections.Counter()
    for isbn, ficha in (fichas_nucleo or {}).items():
        peso = math.log1p(prestamos_de.get(isbn, 1))
        for m in ficha.get("materias") or []:
            if m.get("esquema") in ("93", "12") and m.get("codigo"):
                pesos["thema:" + m["codigo"][:3]] += peso
            elif m.get("esquema") == "20" and m.get("texto"):
                for palabra in normaliza(m["texto"]).split():
                    if len(palabra) > 3 and palabra not in PALABRAS_VACIAS:
                        pesos["clave:" + palabra] += peso * 0.5
        if ficha.get("editorial"):
            pesos["editorial:" + normaliza(ficha["editorial"])] += peso * 0.4
        if ficha.get("coleccion"):
            pesos["coleccion:" + normaliza(ficha["coleccion"])] += peso
    total = sum(pesos.values()) or 1
    return {k: round(v / total, 6) for k, v in pesos.items() if v > 0}


def parecido(ficha, perfil_biblioteca):
    """(puntuación, rasgos que coinciden) de una novedad con el perfil."""
    if not perfil_biblioteca:
        return 0.0, []
    puntos, rasgos = 0.0, []
    for m in ficha.get("materias") or []:
        if m.get("esquema") in ("93", "12") and m.get("codigo"):
            clave = "thema:" + m["codigo"][:3]
            if clave in perfil_biblioteca:
                puntos += perfil_biblioteca[clave]
                rasgos.append(m["codigo"])
        elif m.get("esquema") == "20" and m.get("texto"):
            for palabra in normaliza(m["texto"]).split():
                if "clave:" + palabra in perfil_biblioteca:
                    puntos += perfil_biblioteca["clave:" + palabra] * 0.5
                    rasgos.append(palabra)
    for campo, factor in (("editorial", 0.4), ("coleccion", 1.0)):
        clave = f"{campo}:{normaliza(ficha.get(campo))}"
        if ficha.get(campo) and clave in perfil_biblioteca:
            puntos += perfil_biblioteca[clave] * factor
            rasgos.append(ficha[campo])
    return round(math.sqrt(puntos) * 100, 1), rasgos[:6]


def muestra_estratificada(registros):
    """ISBN propios en orden de descarga para el modelo de afinidad: se van
    alternando nunca prestados, prestados y muy prestados, de lo más reciente
    a lo más antiguo, para que la muestra no quede sesgada hacia el éxito."""
    grupos = {0: [], 1: [], 2: []}
    vistos = set()
    for r in sorted(registros, key=lambda r: -(r.get("year") or 0)):
        isbn = isbn13(r.get("isbn"))
        if not isbn or isbn in vistos or r.get("es_audiovisual"):
            continue
        vistos.add(isbn)
        grupos[min(max(int(r.get("prestamos") or 0), 0), 2)].append(isbn)
    orden = []
    for trio in zip(*(g + [None] * (max(map(len, grupos.values())) - len(g)) for g in grupos.values())):
        orden += [i for i in trio if i]
    return orden


# ---------------------------------------------------------------------------
# Fuente: autores más prestados
# ---------------------------------------------------------------------------
def autores_mas_prestados(cache, cliente, registros, opciones, progreso=None):
    """Obras del mismo autor que los títulos más prestados y que no están aquí."""
    nucleo = nucleo_prestamo(registros, opciones.get("fraccion_nucleo", 0.5))
    propios_isbn = {isbn13(r.get("isbn")) for r in registros if isbn13(r.get("isbn"))}
    propios_clave = {(apellido(r.get("autor")), normaliza(r.get("titulo"))[:40])
                     for r in registros if r.get("titulo")}
    prestamos_de = {t["isbn"]: t["prestamos"] for t in nucleo if t.get("isbn")}

    maximo = opciones.get("max_fichas_nuevas", MAX_FICHAS_NUEVAS)
    pedidas = 0

    def pedir_con_tope(isbns):
        """Primero todo lo ya descargado (fichas y novedades); a DILVE solo las
        que falten, por orden de prioridad y sin pasar del tope del cálculo."""
        nonlocal pedidas
        guardadas = cache.leer_fichas(isbns)
        sin_ficha = cache.sin_ficha() if hasattr(cache, "sin_ficha") else set()
        faltan = [i for i in isbns if i not in guardadas and i not in sin_ficha]
        admitidas = faltan[:max(0, maximo - pedidas)]
        if admitidas and cliente is not None:
            nuevas = cache.fichas(admitidas, cliente, progreso)
            guardadas.update(nuevas)
            pedidas += len(admitidas)
        return guardadas, len(faltan) - len(admitidas)

    # Núcleo ordenado por préstamos: si hay que cortar, se corta por lo menos prestado
    isbns_nucleo = [t["isbn"] for t in nucleo if t.get("isbn")]
    en_cache = len(cache.leer_fichas(isbns_nucleo))
    fichas_nucleo, pendientes_nucleo = pedir_con_tope(isbns_nucleo)

    origen, corporativos = collections.defaultdict(list), 0
    for isbn, ficha in fichas_nucleo.items():
        if es_autor_corporativo(autor_de(ficha)):
            corporativos += 1
            continue
        mismos = [r["isbn"] for r in ficha.get("relacionados") or [] if r.get("codigo") == "22"]
        for rel in mismos[:RELACIONADOS_POR_TITULO]:
            rel = isbn13(rel)
            if rel and rel not in propios_isbn:
                origen[rel].append(isbn)

    # Relacionados por orden de interés: los que salen de los títulos más prestados
    orden_rel = sorted(origen, key=lambda i: -sum(prestamos_de.get(o, 0) for o in origen[i]))
    en_cache += len(cache.leer_fichas(orden_rel))
    fichas_rel, pendientes_rel = pedir_con_tope(orden_rel)
    anio_corte = opciones.get("anio_actual", 2026) - opciones.get("anios_recientes", 5) + 1
    candidatos, descartes = [], collections.Counter()

    for isbn, ficha in fichas_rel.items():
        motivo = _descartar(ficha, opciones, propios_isbn, propios_clave, descartes)
        if motivo:
            descartes[motivo] += 1
            continue
        if opciones.get("excluir_texto", True) and mod_materias.clasificar(
                ficha, opciones.get("calibracion"), opciones.get("tablas"))[0] == mod_materias.LIBRO_TEXTO:
            descartes["libro de texto"] += 1
            continue
        autor = autor_de(ficha)
        # ¿Es de verdad del mismo autor? Hay editoriales que usan el código 22
        # para anunciar su catálogo.
        coinciden = [o for o in origen[isbn] if apellido(autor_de(fichas_nucleo[o])) == apellido(autor)]
        del_autor = bool(coinciden)
        if not del_autor and not opciones.get("sugeridos_editorial", False):
            descartes["sugerido por la editorial"] += 1
            continue
        fuentes = coinciden or origen[isbn]
        referencia = fichas_nucleo[fuentes[0]]
        prestamos = sum(prestamos_de.get(o, 0) for o in fuentes)
        anio = int((ficha.get("fecha_publicacion") or "0")[:4] or 0)
        candidatos.append(ficha_a_propuesta(ficha, opciones, {
            "del_autor": del_autor, "reciente": anio >= anio_corte, "anio": anio,
            "origen_titulo": referencia.get("titulo"), "origen_isbn": referencia.get("isbn"),
            "prestamos_origen": prestamos,
            "puntos": prestamos + (20 if anio >= anio_corte else 0) + (10 if del_autor else 0),
        }))

    # Con lo que quede del tope, fichas de títulos PROPIOS de todo tipo
    # (también nunca prestados): el modelo de afinidad aprende de ellas qué
    # materias, series y sellos funcionan aquí y cuáles no.
    muestra_propia = 0
    if cliente is not None and pedidas < maximo:
        orden_propio = muestra_estratificada(registros)
        antes = pedidas
        pedir_con_tope(orden_propio)
        muestra_propia = pedidas - antes

    candidatos.sort(key=lambda p: (-p["puntos"], -(p["anio"] or 0)))
    tope, por_autor, propuestas, anteriores = opciones.get("max_por_autor", 3), collections.Counter(), [], []
    for p in candidatos:
        if not p["reciente"]:
            anteriores.append(p)
            continue
        clave = apellido(p["autor"])
        if tope and por_autor[clave] >= tope:
            descartes["tope por autor"] += 1
            continue
        por_autor[clave] += 1
        propuestas.append(p)
    return {"propuestas": propuestas, "anteriores": anteriores, "nucleo": len(nucleo),
            "con_ficha": len(fichas_nucleo), "corporativos": corporativos,
            "candidatos": len(origen), "descartes": dict(descartes.most_common()),
            "desde_cache": en_cache, "pedidas_dilve": pedidas, "muestra_propia": muestra_propia,
            # Fichas que faltan por pedir: se completarán en próximos cálculos
            "pendientes": pendientes_nucleo + pendientes_rel,
            "interrupcion": str(cliente.interrupcion) if cliente is not None and cliente.interrupcion else None}


# ---------------------------------------------------------------------------
# Fuente: novedades
# ---------------------------------------------------------------------------
def publicado_a_dia_de_hoy(fecha):
    """¿Ya se ha publicado? Compara la fecha de publicación de DILVE con el día
    de hoy según el reloj del ordenador (librería `time`). Las editoriales dan
    de alta muchos libros meses antes de que salgan.

    DILVE da la fecha como AAAAMMDD, AAAAMM o AAAA: se compara con la misma
    precisión (un libro de «202610» cuenta como publicado desde octubre de
    2026). Sin fecha no se puede saber y no se descarta."""
    cifras = "".join(c for c in str(fecha or "") if c.isdigit())
    if len(cifras) < 4:
        return True
    hoy = time.strftime("%Y%m%d")
    largo = 8 if len(cifras) >= 8 else 6 if len(cifras) >= 6 else 4
    return cifras[:largo] <= hoy[:largo]


def _fecha_como_dia(fecha):
    """AAAAMMDD de una fecha de DILVE (AAAAMMDD, AAAAMM o AAAA). Si falta el
    día o el mes se toma el primero: un libro de «202612» puede salir el
    día 1 de diciembre, así que no se deja fuera de un plazo que lo alcance."""
    cifras = "".join(c for c in str(fecha or "") if c.isdigit())
    if len(cifras) < 4:
        return None
    if len(cifras) >= 8:
        return cifras[:8]
    if len(cifras) >= 6:
        return cifras[:6] + "01"
    return cifras[:4] + "0101"


def limite_meses(meses, hoy=None):
    """AAAAMMDD de hoy más `meses` meses naturales (el 30 de noviembre más
    tres meses es el 28 o 29 de febrero, no el 2 de marzo)."""
    import calendar
    hoy = hoy or time.strftime("%Y%m%d")
    anio, mes, dia = int(hoy[:4]), int(hoy[4:6]), int(hoy[6:8])
    mes += meses
    anio += (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    dia = min(dia, calendar.monthrange(anio, mes)[1])
    return f"{anio:04d}{mes:02d}{dia:02d}"


def en_plazo(fecha, publicados=True, proximos_meses=None, hoy=None):
    """¿Entra la fecha de publicación en los plazos marcados?

    - `publicados`: ya ha salido (hasta hoy, incluido).
    - `proximos_meses`: sale entre mañana y hoy + N meses, ni un día más.
    Con los dos marcados, vale cualquiera de las dos cosas. Sin ninguno, todo.
    Los libros sin fecha solo entran si se admite lo publicado (no se puede
    saber si ya han salido, pero seguro que no son una preventa lejana)."""
    if not publicados and not proximos_meses:
        return True
    hoy = hoy or time.strftime("%Y%m%d")
    dia = _fecha_como_dia(fecha)
    if dia is None:
        return bool(publicados)
    if publicados and publicado_a_dia_de_hoy(fecha):
        return True
    if proximos_meses and hoy < dia <= limite_meses(proximos_meses, hoy):
        return True
    return False


def novedades(base, registros, opciones):
    """Novedades de DILVE de la ventana guardada, con filtros y facetas.

    El filtrado se hace aquí y no al descargar: la base guarda todas las altas,
    así que cambiar de criterio no obliga a volver a pedirlas."""
    filtros = opciones.get("filtros") or {}
    limite = opciones.get("limite", 300)
    fichas = base.leer_fichas()
    if not fichas:
        return {"propuestas": [], "total": 0, "sin_filtrar": 0, "facetas": {}}

    propios_isbn = {isbn13(r.get("isbn")) for r in registros if isbn13(r.get("isbn"))}
    propios_clave = {(apellido(r.get("autor")), normaliza(r.get("titulo"))[:40])
                     for r in registros if r.get("titulo")}
    perfil_biblioteca = opciones.get("perfil") or {}
    modelo = opciones.get("modelo_afinidad")
    # «Afines»: orden por el modelo de préstamo (el perfil por materias de la
    # 1.0 queda solo como referencia en la evaluación retrospectiva)
    por_modelo = bool(filtros.get("personalizadas") and modelo)
    if por_modelo:
        from backend import afinidad as mod_afinidad     # aquí: afinidad importa este módulo
    encabezados = opciones.get("encabezados_thema")
    facetas = {"seccion": collections.Counter(), "idioma": collections.Counter(),
               "editorial": collections.Counter(), "forma": collections.Counter(),
               "thema": collections.Counter()}
    propuestas, sin_filtrar = [], len(fichas)

    solo_publicados = filtros.get("solo_publicados", True)
    proximos = 3 if filtros.get("proximos_3_meses", True) else None
    hoy = time.strftime("%Y%m%d")
    for ficha in fichas.values():
        if not en_plazo(ficha.get("fecha_publicacion"), solo_publicados, proximos, hoy):
            continue
        seccion, motivo = mod_materias.clasificar(ficha, opciones.get("calibracion"), opciones.get("tablas"))
        if opciones.get("excluir_texto", True) and seccion == mod_materias.LIBRO_TEXTO:
            continue
        if opciones.get("solo_papel", True) and not (ficha.get("forma") or "").upper().startswith("B"):
            continue
        ya_en_fondo = (ficha.get("isbn") in propios_isbn
                       or (apellido(autor_de(ficha)), normaliza(ficha.get("titulo"))[:40]) in propios_clave)
        if ya_en_fondo and filtros.get("ocultar_propios", True):
            continue
        idioma = _idioma(ficha)
        otras = mod_materias.otras_secciones(ficha, seccion, opciones.get("calibracion"), opciones.get("tablas"))
        secciones = [seccion] + [s for s, _ in otras]
        codigos = _thema(ficha)
        # Las facetas se cuentan antes de aplicar los filtros del usuario, para
        # que los recuentos enseñen lo que hay disponible. Un libro cuenta en
        # cada sección y cada materia que le corresponde.
        for s in secciones:
            facetas["seccion"][s] += 1
        # Materias a tres caracteres (FRD, XAM…): bastante finas para elegir
        # un género y bastante gruesas para que la lista quepa.
        for prefijo in dict.fromkeys(c[:3] for c in codigos):
            facetas["thema"][prefijo] += 1
        facetas["idioma"][idioma or "__SIN__"] += 1
        if ficha.get("editorial"):
            facetas["editorial"][ficha["editorial"]] += 1
        if ficha.get("forma"):
            facetas["forma"][ficha["forma"]] += 1

        if filtros.get("seccion") and filtros["seccion"] not in secciones:
            continue
        if filtros.get("thema") and not any(c.startswith(filtros["thema"].upper()) for c in codigos):
            continue
        if filtros.get("idioma"):
            if filtros["idioma"] == "__SIN__" and idioma:
                continue
            if filtros["idioma"] != "__SIN__" and idioma != filtros["idioma"]:
                continue
        if filtros.get("editorial") and ficha.get("editorial") != filtros["editorial"]:
            continue
        if filtros.get("forma") and ficha.get("forma") != filtros["forma"]:
            continue
        # Varias palabras, en cualquier orden, buscadas en título, autor,
        # colección, editorial, resumen y palabras clave: lo mismo que el
        # resto de buscadores de Bildumargi, para que el hábito no cambie.
        palabras = (filtros.get("texto") or "").strip().split()
        if palabras:
            fondo = normaliza(" ".join([
                ficha.get("titulo") or "", ficha.get("subtitulo") or "", autor_de(ficha),
                ficha.get("coleccion") or "", ficha.get("editorial") or "", ficha.get("sello") or "",
                ficha.get("resumen") or "", *_claves(ficha), _texto_thema(ficha, encabezados),
            ]))
            if not all(_coincide_palabra(p, fondo, codigos, encabezados) for p in palabras):
                continue

        extra = {"seccion": seccion, "motivo_seccion": motivo, "otras_secciones": otras, "ya_en_fondo": ya_en_fondo}
        if por_modelo:
            try:
                prevision, explicacion, relativa = mod_afinidad.prever(ficha, modelo, seccion)
                rasgos_x = mod_afinidad.rasgos_ficha(ficha)
            except Exception:             # una ficha rara no puede tumbar la lista entera
                prevision = modelo["mu_seccion"].get(seccion, modelo["mu"])
                explicacion, relativa, rasgos_x = [], 1.0, {"serie": None, "autores": []}
            # La explicación por libro no se envía: el «?» explica el método
            extra.update({"prevision": round(prevision, 4), "prevision_relativa": round(relativa, 2),
                          "_serie": rasgos_x["serie"], "_autores": rasgos_x["autores"]})
        elif filtros.get("personalizadas"):
            puntos, rasgos = parecido(ficha, perfil_biblioteca)
            if perfil_biblioteca and puntos <= 0:
                continue
            extra.update({"afinidad": puntos, "parecido": rasgos})
        propuestas.append(ficha_a_propuesta(ficha, dict(opciones, seccion=seccion), extra))

    if por_modelo:
        propuestas.sort(key=lambda p: (-p["prevision"], p.get("fecha") or ""))
        # Con una sección elegida no hay reparto que calibrar: solo topes
        propuestas = mod_afinidad.reordenar(propuestas, modelo if not filtros.get("seccion") else
                                            dict(modelo, parametros=dict(modelo["parametros"], calibracion=0)))
        for p in propuestas:
            p.pop("_serie", None)
            p.pop("_autores", None)
    elif filtros.get("personalizadas") and perfil_biblioteca:
        propuestas.sort(key=lambda p: (-(p.get("afinidad") or 0), p.get("fecha") or ""))
    else:
        propuestas.sort(key=lambda p: (p.get("fecha") or "", p.get("titulo") or ""), reverse=True)
    # Por páginas: con miles de novedades, una sola lista no cabe en pantalla
    por_pagina = max(1, int(opciones.get("por_pagina") or limite))
    paginas = max(1, -(-len(propuestas) // por_pagina))
    pagina = min(max(1, int(opciones.get("pagina") or 1)), paginas)
    inicio = (pagina - 1) * por_pagina
    return {"propuestas": propuestas[inicio:inicio + por_pagina], "total": len(propuestas),
            "sin_filtrar": sin_filtrar, "pagina": pagina, "paginas": paginas, "por_pagina": por_pagina,
            "limite_proximos": limite_meses(3, hoy) if proximos else None,
            "facetas": {k: dict(v.most_common(250 if k == "thema" else 40)) for k, v in facetas.items()}}
