# -*- coding: utf-8 -*-
"""Series de la biblioteca, a partir de las fichas de DILVE.

En DILVE (ONIX), «colección» mezcla dos cosas: series de verdad («Los
Futbolísimos») y colecciones de editorial («Andanzas», «Serie Negra»), y el
tipo de colección no las distingue; muchas colecciones de editorial también
numeran sus libros. Aquí es serie una colección con al menos dos tomos
propios numerados (hasta el 60), cuyos tomos son casi todos del mismo autor
o llevan el nombre de la serie en el título (ver es_serie). La biblioteca
puede ocultar a mano las que se cuelen.

El número de tomo sale de la ficha (PartNumber) o, si no viene, del título
cuando empieza por el nombre de la serie («Los Futbolísimos 8: El misterio…»).

Qué tomos faltan: con DILVE no se puede pedir una serie entera, así que se
ven dos cosas:
    hueco      números que faltan entre el 1 y el último tomo propio
    posterior  tomos con número mayor que el último propio que aparecen en
               las fichas o las novedades de DILVE ya descargadas
Un tomo posterior que DILVE no haya dado nunca no se puede ver.
"""

import collections
import functools
import re
import unicodedata

from backend import clasificacion

MAX_NUMERO_SERIE = 60      # por encima, numeración de colección de editorial


def _clave(nombre):
    texto = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode()
    return " ".join(texto.lower().split())


@functools.lru_cache(maxsize=65536)     # los mismos nombres se repiten miles de veces
def clave_serie(nombre):
    """Clave para agrupar nombres de serie: sin lo que va entre corchetes
    («Harry Potter [edición con la portada ilustrada…]») ni puntuación
    («Ilargia - Narrativa» = «Ilargia Narrativa»)."""
    texto = re.sub(r"\[[^\]]*\]", " ", _clave(nombre))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texto).split())


def nombre_visible(nombre):
    """Bruño pone su árbol de catálogo en el nombre («Castellano - A PARTIR
    DE 12 AÑOS - NARRATIVA - Mis padres y yo»): se enseña solo el último tramo."""
    tramos = [t.strip() for t in str(nombre or "").split(" - ")]
    return tramos[-1] if len(tramos) >= 3 and tramos[-1] else nombre


def _distancia(a, b, tope=2):
    """Distancia de edición entre dos cadenas, cortada en tope + 1."""
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        previa, fila[0] = fila[0], i
        for j, cb in enumerate(b, 1):
            previa, fila[j] = fila[j], min(fila[j] + 1, fila[j - 1] + 1, previa + (ca != cb))
    return fila[-1]


MIN_LETRAS_PARECIDAS = 8   # nombres más cortos no se unen por parecido


def _unir_parecidas(grupos):
    """Une grupos cuyos nombres difieren en una o dos letras («Pequeña &
    Grande» y «Pequeño & Grande»), solo si son del mismo autor y ningún
    número de tomo propio se repite entre ellos."""
    def autor(g):
        cuenta = collections.Counter(autor_normalizado(r.get("autor")) for r, _ in g["ejemplares"] if r.get("autor"))
        return cuenta.most_common(1)[0][0] if cuenta else None

    def numeros(g):
        return {numero_de(f, f.get("coleccion")) for _, f in g["ejemplares"]} - {None}

    # Solo se comparan grupos del mismo autor (es condición para unirlos):
    # comparar todos con todos eran cientos de miles de distancias
    por_autor = collections.defaultdict(list)
    for clave, g in grupos.items():
        a = autor(g) if len(clave) >= MIN_LETRAS_PARECIDAS else None
        if a:
            por_autor[a].append(clave)
    for claves in por_autor.values():
        if len(claves) < 2:
            continue
        claves.sort(key=lambda c: -len(grupos[c]["ejemplares"]))
        for i, mayor in enumerate(claves):
            if mayor not in grupos:
                continue
            for menor in claves[i + 1:]:
                if menor not in grupos:
                    continue
                a, b = grupos[mayor], grupos[menor]
                if _distancia(mayor, menor) <= 2 and not (numeros(a) & numeros(b)):
                    a["nombres"].update(b["nombres"])
                    a["ejemplares"].extend(b["ejemplares"])
                    a["claves"] |= b["claves"]
                    del grupos[menor]
    return grupos


def numero_de(ficha, coleccion):
    """Número de tomo: el de la ficha o, si no, el del título."""
    bruto = str(ficha.get("num_coleccion") or "").strip()
    m = re.match(r"^\D{0,4}(\d{1,4})", bruto)
    if m:
        return int(m.group(1))
    titulo = str(ficha.get("titulo") or "")
    if coleccion and _clave(titulo).startswith(_clave(coleccion)):
        resto = titulo[len(coleccion):]
        m = re.match(r"^\s*(?:n\.?\s*[ºo°]?\s*|vol\.?\s*|tomo\s*|#\s*)?(\d{1,3})\b", resto, re.I)
        if m:
            return int(m.group(1))
    return None


def _preferencia(ficha, serie, numero):
    titulo = _clave(ficha.get("titulo"))
    con_numero = bool(re.match(rf"^{re.escape(_clave(serie))}\W*(n\W*o?\W*)?{numero}\b", titulo))
    return (con_numero, str(ficha.get("fecha_publicacion") or ""))


def _cubierta(ficha):
    url = str((ficha or {}).get("cubierta") or "")
    return url if url.startswith(("http://", "https://")) else None


def _anio(registro, ficha):
    if registro and registro.get("year"):
        return int(registro["year"])
    fecha = str((ficha or {}).get("fecha_publicacion") or "")
    return int(fecha[:4]) if fecha[:4].isdigit() else None


def _titulo_propio(texto):
    """La parte distintiva de un título de serie: lo que va tras «:» o «.»
    («Los Futbolísimos 3: El misterio del portero fantasma» → «el misterio
    del portero fantasma»), para buscarlo entre los títulos del catálogo."""
    texto = re.split(r"[:.]\s+", str(texto or ""), maxsplit=1)
    return _clave(texto[-1]).strip(" /") if texto else ""


MIN_MISMO_AUTOR = 0.8       # parte de los tomos propios del mismo autor
MIN_TITULO_CON_NOMBRE = 0.5  # parte de los tomos con el nombre de la serie en el título


def _apellido(autor):
    return _clave(str(autor or "").split(",")[0])


def autor_normalizado(autor):
    """«SANTIAGO, Roberto (1968-)» y «Santiago, Roberto ( 1968-)» → «santiago,
    roberto»: el mismo autor escrito por catálogos distintos."""
    texto = re.sub(r"\(.*?\)", "", str(autor or ""))
    return _clave(texto).replace(" ,", ",").strip(" ,.")


def es_serie(nombre, ejemplares):
    """Una colección numerada es serie si sus tomos son del mismo autor
    («Harry Potter», «Geronimo Stilton») o llevan el nombre de la serie en
    el título («Minecraft…», de varios autores). Las colecciones de editorial
    («Andanzas», «Éxitos») mezclan muchos autores y no lo llevan."""
    if not ejemplares:
        return False
    clave = _clave(nombre)
    con_nombre = sum(1 for r, f in ejemplares if clave and clave in _clave(f.get("titulo") or r.get("titulo")))
    if con_nombre / len(ejemplares) >= MIN_TITULO_CON_NOMBRE:
        return True
    autores = collections.Counter(_apellido(r.get("autor")) for r, _ in ejemplares if r.get("autor"))
    if sum(autores.values()) < 2:
        return False
    return autores.most_common(1)[0][1] / sum(autores.values()) >= MIN_MISMO_AUTOR


def detectar(registros, fichas_propias, conocidas, ocultas=()):
    """Series de la biblioteca.

    registros       ejemplares del análisis (isbn, título, año, préstamos…)
    fichas_propias  {isbn: {coleccion, num_coleccion, titulo, fecha_publicacion}}
                    de los libros propios
    conocidas       {colección: [fichas]} de todo lo descargado de esas
                    colecciones (propias, de otras búsquedas y novedades)
    ocultas         nombres de colección que la biblioteca ha descartado
    """
    ocultas = {clave_serie(x) for x in ocultas or ()}
    # Títulos de todo el fondo, también de lo que no tiene ficha de DILVE
    titulos_fondo = {}
    for r in registros:
        clave_titulo = _clave(r.get("titulo")).strip(" /")
        if clave_titulo:
            titulos_fondo.setdefault(clave_titulo, r)
    # Ejemplares propios por colección y número
    grupos = {}
    for r in registros:
        ficha = fichas_propias.get(r.get("isbn") or "")
        if not ficha or not ficha.get("coleccion"):
            continue
        clave = clave_serie(ficha["coleccion"])
        g = grupos.setdefault(clave, {"nombres": collections.Counter(), "ejemplares": [], "claves": {clave}})
        g["nombres"][ficha["coleccion"]] += 1
        g["ejemplares"].append((r, ficha))
    _unir_parecidas(grupos)
    # Para «posiblemente de la serie»: firma (autor, signatura) y comienzo del
    # título de cada ejemplar sin ficha de colección, calculados una sola vez
    # (antes se recalculaban para cada serie con todo el fondo)
    inicio = lambda texto: " ".join(_clave(texto).split()[:2])
    sin_coleccion_por_firma = collections.defaultdict(list)
    for r in registros:
        if r.get("isbn") and fichas_propias.get(r["isbn"], {}).get("coleccion"):
            continue
        sin_coleccion_por_firma[(_clave(r.get("autor")), _clave(r.get("signatura_real")))].append(
            (r, inicio(r.get("titulo"))))
    # Lo conocido de cada serie, por clave (se calcula una vez, no por grupo)
    conocidas_por_clave = collections.defaultdict(list)
    for nombre_conocido, lista in conocidas.items():
        conocidas_por_clave[clave_serie(nombre_conocido)].append((nombre_conocido, lista))

    series = []
    for clave, g in grupos.items():
        # El nombre sin corchetes de edición y, entre esos, el más repetido
        nombre = max(g["nombres"], key=lambda n: ("[" not in n, g["nombres"][n]))
        tomos = collections.defaultdict(list)          # número -> ejemplares propios
        sin_numero = []
        for r, ficha in g["ejemplares"]:
            n = numero_de(ficha, ficha.get("coleccion") or nombre)
            (tomos[n].append((r, ficha)) if n is not None else sin_numero.append((r, ficha)))
        numeros = sorted(tomos)
        # Serie: al menos dos tomos propios numerados, con numeración de serie
        if len(numeros) < 2 or numeros[-1] > MAX_NUMERO_SERIE:
            continue
        if not es_serie(nombre, g["ejemplares"]):
            continue
        visible = nombre_visible(nombre)
        if g["claves"] & ocultas or clave_serie(visible) in ocultas:
            continue
        ultimo = numeros[-1]

        # Lo que DILVE sabe de esta colección (otros tomos, con su título)
        otros = {}
        for nombre_conocido, lista in (par for c in g["claves"] for par in conocidas_por_clave.get(c, ())):
            for f in lista:
                n = numero_de(f, nombre_conocido)
                if n is not None and n not in tomos and n <= MAX_NUMERO_SERIE:
                    previa = otros.get(n)
                    # Con el mismo número puede haber reediciones o una subserie
                    # («Anna Kadabra. Aventuras legendarias 1»): gana el título
                    # «serie + número» y, a igualdad, la edición más reciente.
                    if previa is None or _preferencia(f, nombre, n) > _preferencia(previa, nombre, n):
                        otros[n] = f

        # Si la serie numera sus títulos («Anna Kadabra 7. …»), lo que no sigue
        # ese patrón con su número (una subserie, un álbum aparte) no ocupa
        # el sitio de un tomo: el hueco queda sin título, que es lo cierto.
        conocidos = [(f, n) for n in numeros for _, f in tomos[n]] + [(f, n) for n, f in otros.items()]
        con_patron = sum(1 for f, n in conocidos if _preferencia(f, nombre, n)[0])
        if conocidos and con_patron / len(conocidos) >= 0.5:
            otros = {n: f for n, f in otros.items() if _preferencia(f, nombre, n)[0]}

        filas = []
        for n in numeros:
            ejemplares = tomos[n]
            r0, f0 = ejemplares[0]
            prestados = sum(1 for r, _ in ejemplares if r.get("prestado"))
            filas.append({
                "numero": n, "estado": "propio", "titulo": r0.get("titulo") or f0.get("titulo"),
                "anio": _anio(r0, f0), "isbn": r0.get("isbn"), "ejemplares": len(ejemplares),
                "prestados": prestados,
                "prestamos": sum(r.get("n_prestamos") or 0 for r, _ in ejemplares) or None,
                "signatura": r0.get("signatura_real"),
                "cubierta": next((_cubierta(f) for _, f in ejemplares if _cubierta(f)), None),
            })
        faltan = 0
        for n in range(1, ultimo):
            if n in tomos:
                continue
            f = otros.get(n) or {}
            # ¿Está en el fondo sin ficha de DILVE (sin ISBN o sin descargar)?
            buscado = _titulo_propio(f.get("titulo"))
            propio = next((r for t, r in titulos_fondo.items()
                           if buscado and len(buscado) >= 8 and (t == buscado or t.endswith(buscado))), None)
            if propio:
                filas.append({"numero": n, "estado": "propio", "titulo": propio.get("titulo"),
                              "anio": _anio(propio, f), "isbn": propio.get("isbn"), "ejemplares": 1,
                              "prestados": 1 if propio.get("prestado") else 0,
                              "prestamos": propio.get("n_prestamos") or None,
                              "signatura": propio.get("signatura_real"), "sin_ficha": True})
                continue
            filas.append({"numero": n, "estado": "hueco", "titulo": f.get("titulo"), "anio": _anio(None, f),
                          "isbn": f.get("isbn"), "fecha_publicacion": f.get("fecha_publicacion"),
                          "cubierta": _cubierta(f)})
            faltan += 1
        posteriores = sorted(n for n in otros if n > ultimo)
        for n in posteriores:
            f = otros[n]
            filas.append({"numero": n, "estado": "posterior", "titulo": f.get("titulo"), "anio": _anio(None, f),
                          "isbn": f.get("isbn"), "fecha_publicacion": f.get("fecha_publicacion"),
                          "cubierta": _cubierta(f)})
        # Posiblemente de la serie: libros propios sin ficha de colección, del
        # mismo autor y con la misma signatura que los tomos de la serie
        # (lo habitual cuando el libro no tiene ISBN o su ficha no se ha
        # descargado). No se les pone número: se enseñan aparte.
        en_serie = {id(r) for r, _ in g["ejemplares"]}
        firmas = collections.Counter((_clave(r.get("autor")), _clave(r.get("signatura_real")))
                                     for r, _ in g["ejemplares"] if r.get("autor"))
        firmas = {f for f, n in firmas.items() if n >= 2}
        # …y cuyo título empieza como los de la serie («El misterio del…»)
        comienzos = collections.Counter(inicio(r.get("titulo")) for r, _ in g["ejemplares"])
        comienzos = {c for c, n in comienzos.items() if c and n >= 2}
        for r, comienzo in (par for firma in firmas for par in sin_coleccion_por_firma.get(firma, ())):
            if id(r) not in en_serie and comienzo in comienzos:
                filas.append({"numero": None, "estado": "posible", "titulo": r.get("titulo"), "anio": _anio(r, None),
                              "isbn": r.get("isbn"), "ejemplares": 1, "prestados": 1 if r.get("prestado") else 0,
                              "prestamos": r.get("n_prestamos") or None, "signatura": r.get("signatura_real")})
        for r, f in sin_numero:
            filas.append({"numero": None, "estado": "propio", "titulo": r.get("titulo") or f.get("titulo"),
                          "anio": _anio(r, f), "isbn": r.get("isbn"), "ejemplares": 1,
                          "prestados": 1 if r.get("prestado") else 0, "prestamos": r.get("n_prestamos") or None,
                          "signatura": r.get("signatura_real")})
        filas.sort(key=lambda x: (x["numero"] is None, x["estado"] == "posible", x["numero"] or 0))

        propias = [x for x in filas if x["estado"] == "propio"]
        # Portada: la del primer tomo que la tenga (el 1, si se conoce)
        portada = next((x["cubierta"] for x in filas if x.get("cubierta") and x["numero"] is not None), None) \
            or next((x["cubierta"] for x in filas if x.get("cubierta")), None)
        anios = [x["anio"] for x in propias if x.get("anio")]
        ejemplares = sum(x["ejemplares"] for x in propias)
        autores = collections.Counter(autor_normalizado(r.get("autor")) for r, _ in g["ejemplares"] if r.get("autor"))
        # Secciones de la biblioteca donde están sus tomos (la que más primero)
        # y público, por mayoría de ejemplares: para filtrar las series
        secciones = collections.Counter(r.get("categoria") for r, _ in g["ejemplares"] if r.get("categoria"))
        infantiles = sum(1 for r, _ in g["ejemplares"] if clasificacion.es_categoria_infantil(r.get("categoria") or ""))
        series.append({
            "nombre": visible, "clave": clave, "claves": sorted(g["claves"]), "portada": portada,
            "secciones": [x for x, _ in secciones.most_common()],
            "publico": "infantil" if infantiles * 2 > len(g["ejemplares"]) else "adultos",
            "autor": autores.most_common(1)[0][0] if autores else None,
            "tomos": len(numeros) + len(sin_numero) + sum(1 for x in filas if x.get("sin_ficha")),
            "ultimo": ultimo,
            "ejemplares": ejemplares,
            "prestados": sum(x["prestados"] for x in propias),
            "prestamos": sum(x["prestamos"] or 0 for x in propias) or None,
            "huecos": faltan, "posteriores": len(posteriores),
            "posibles": sum(1 for x in filas if x["estado"] == "posible"),
            "anio_min": min(anios) if anios else None, "anio_max": max(anios) if anios else None,
            "filas": filas,
        })
    # Primero las que más se prestan
    series.sort(key=lambda x: (-(x["prestados"] / x["ejemplares"] if x["ejemplares"] else 0), -x["tomos"]))
    return series
