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
import re
import unicodedata

MAX_NUMERO_SERIE = 60      # por encima, numeración de colección de editorial


def _clave(nombre):
    texto = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode()
    return " ".join(texto.lower().split())


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
    ocultas = {_clave(x) for x in ocultas or ()}
    # Títulos de todo el fondo, también de lo que no tiene ficha de DILVE
    titulos_fondo = {}
    for r in registros:
        clave_titulo = _clave(r.get("titulo")).strip(" /")
        if clave_titulo:
            titulos_fondo.setdefault(clave_titulo, r)
    # Ejemplares propios por colección y número
    grupos = collections.defaultdict(lambda: {"nombres": collections.Counter(), "ejemplares": []})
    for r in registros:
        ficha = fichas_propias.get(r.get("isbn") or "")
        if not ficha or not ficha.get("coleccion"):
            continue
        g = grupos[_clave(ficha["coleccion"])]
        g["nombres"][ficha["coleccion"]] += 1
        g["ejemplares"].append((r, ficha))

    series = []
    for clave, g in grupos.items():
        nombre = g["nombres"].most_common(1)[0][0]
        tomos = collections.defaultdict(list)          # número -> ejemplares propios
        sin_numero = []
        for r, ficha in g["ejemplares"]:
            n = numero_de(ficha, nombre)
            (tomos[n].append((r, ficha)) if n is not None else sin_numero.append((r, ficha)))
        numeros = sorted(tomos)
        # Serie: al menos dos tomos propios numerados, con numeración de serie
        if len(numeros) < 2 or numeros[-1] > MAX_NUMERO_SERIE:
            continue
        if not es_serie(nombre, g["ejemplares"]):
            continue
        if clave in ocultas:
            continue
        ultimo = numeros[-1]

        # Lo que DILVE sabe de esta colección (otros tomos, con su título)
        otros = {}
        for nombre_conocido, lista in conocidas.items():
            if _clave(nombre_conocido) != clave:
                continue
            for f in lista:
                n = numero_de(f, nombre)
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
        inicio = lambda texto: " ".join(_clave(texto).split()[:2])
        comienzos = collections.Counter(inicio(r.get("titulo")) for r, _ in g["ejemplares"])
        comienzos = {c for c, n in comienzos.items() if c and n >= 2}
        for r in registros:
            if id(r) in en_serie or (r.get("isbn") and fichas_propias.get(r["isbn"], {}).get("coleccion")):
                continue
            if ((_clave(r.get("autor")), _clave(r.get("signatura_real"))) in firmas
                    and inicio(r.get("titulo")) in comienzos):
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
        series.append({
            "nombre": nombre, "clave": clave, "portada": portada,
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
