# -*- coding: utf-8 -*-
"""Orden de las novedades por afinidad con el préstamo de la biblioteca.

Modelo de tasa de préstamo (Poisson-Gamma) por rasgo
----------------------------------------------------
Para cada rasgo —un autor, una serie, un sello, cada nivel de un código
THEMA (F, FR, FRD, FRDA), un calificador, una palabra clave, tener premio—
se calcula su tasa de préstamo: préstamos / exposición, donde la exposición
son ejemplares × años en la estantería. Es el «uso relativo» de Bonn (1974)
llevado del nivel de sección al de rasgo, con dos correcciones:

  - Los títulos nunca prestados cuentan (préstamos 0 con su exposición): son
    tan informativos como los muy prestados.
  - Los rasgos con pocos datos se acercan a lo esperado (contracción
    empírico-bayesiana): r = (L + m·r_previa) / (E + m). Un autor con dos
    títulos no se convierte en estrella; uno con veinte, sí. En THEMA la
    tasa previa de cada código es la de su padre (FRD se apoya en FR).

El peso de un rasgo es w = ln(r / r_previa): 0 si no dice nada, positivo si
se presta más de lo esperado, negativo si menos. La previsión de una novedad
es la tasa de su sección más la suma ponderada de sus rasgos por grupos:

  ln λ = ln μ_sección + Σ β_grupo · señal_grupo  (+ término local, opcional)

λ son préstamos esperados por ejemplar y año. Los pesos β por grupo siguen
lo que dice la literatura sobre qué predice la demanda de un libro nuevo:
el historial del autor y la editorial pesan más que la materia (Wang et al.
2019, EPJ Data Science 8:31; Suominen 2023, Informaatiotutkimus). Son
valores por defecto razonables, no validados: se ajustan por red en
datos/afinidad.json y se comprueban con `evaluar`.

Reordenación
------------
La lista final se calibra por secciones (Steck 2018, RecSys): se elige de uno
en uno lo que más suma sin alejar el reparto por secciones del objetivo
(sobre todo, el reparto del préstamo propio). Con topes por serie y autor en
cada bloque de 50, para que una saga no copa la lista.

Todo en Python puro, sin dependencias.
"""

import collections
import json
import math
import os
import random
import re

from backend import materias as mod_materias
from backend.sugerencias import PALABRAS_VACIAS, es_autor_corporativo, isbn13, normaliza

# ---------------------------------------------------------------------------
# Parámetros por defecto (se pueden cambiar en datos/afinidad.json)
# ---------------------------------------------------------------------------
DEFECTO = {
    # Años de préstamo que cubren los listados de AbsysNet: tope de exposición
    "ventana_anios": 5,
    # Préstamos estimados por ejemplar cuando el listado no da la cifra:
    # nunca prestado, prestado alguna vez, en «más prestados» sin número
    "prestamos_estimados": [0.0, 1.0, 3.0],
    # Fuerza de la contracción (en ejemplares-año) por grupo de rasgos
    "m": {"autor": 3, "serie": 3, "thema": 5, "calificador": 10, "sello": 10,
          "clave": 20, "premio": 10, "seccion": 20},
    # Peso de cada grupo en la previsión
    "beta": {"autor": 1.0, "serie": 0.8, "thema": 0.7, "sello": 0.4,
             "calificador": 0.4, "clave": 0.3, "premio": 1.0},
    "peso_thema_secundario": 0.5,
    "premio_minimo": 0.1,           # un premio nunca resta, aunque aquí no haya datos
    # Interés local: término de política, no de predicción. Vacío = sin efecto.
    # Ejemplo: {"prefijos": ["1DSE-ES-NA"], "autores": ["urkia asier"], "peso": 0.2}
    "local": {"prefijos": [], "autores": [], "editoriales": [], "peso": 0.2},
    # Reordenación calibrada
    "calibracion": 0.3,             # 0 = solo previsión; 1 = solo reparto por secciones
    "calibracion_prestamo": 0.7,    # objetivo: 70 % reparto del préstamo, 30 % reparto uniforme
    "calibrar_primeros": 200,
    "tope_serie": 2, "tope_autor": 3, "bloque": 50,
}


def cargar_parametros(ruta=None):
    """Parámetros por defecto, sustituidos por los de la red si hay fichero."""
    p = json.loads(json.dumps(DEFECTO))
    if ruta and os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                propios = json.load(f)
            for k, v in propios.items():
                if isinstance(v, dict) and isinstance(p.get(k), dict):
                    p[k].update(v)
                elif not k.startswith("_"):
                    p[k] = v
        except (OSError, ValueError):
            pass
    return p


# ---------------------------------------------------------------------------
# Rasgos
# ---------------------------------------------------------------------------
_FECHAS = re.compile(r"\([^)]*\)|\b1[89]\d\d\b|\b20\d\d\b")


def clave_autor(texto):
    """«García Márquez, Gabriel (1927-2014)» y «GARCIA MARQUEZ, GABRIEL» dan la
    misma clave: apellidos + inicial del nombre. Sirve para cruzar el
    catálogo de AbsysNet con los contribuidores de DILVE."""
    if not texto or es_autor_corporativo(texto):
        return None
    texto = _FECHAS.sub(" ", str(texto))
    apellidos, _, nombre = texto.partition(",")
    apellidos, nombre = normaliza(apellidos), normaliza(nombre)
    if not apellidos:
        return None
    return f"{apellidos}|{nombre[:1]}"


def autores_dilve(ficha):
    claves = []
    for c in ficha.get("contribuidores") or []:
        if c.get("rol") not in ("A01", None):
            continue
        clave = clave_autor(c.get("invertido") or "")
        if not clave and c.get("nombre") and "," not in c["nombre"]:
            partes = c["nombre"].split()                     # «Nombre Apellido»
            if len(partes) >= 2:
                clave = clave_autor(f"{' '.join(partes[1:])}, {partes[0]}")
        if clave:
            claves.append(clave)
    return list(dict.fromkeys(claves))


def _serie(ficha):
    coleccion = normaliza(ficha.get("coleccion"))
    coleccion = re.sub(r"\b(n|no|num|vol|volumen|tomo|libro|book|\d+)\b", " ", coleccion)
    coleccion = " ".join(coleccion.split())
    return coleccion or None


def _prefijos(codigo, minimo=1):
    codigo = (codigo or "").strip().upper()
    return [codigo[:i] for i in range(minimo, len(codigo) + 1) if codigo[:i][-1] != "-"]


def rasgos_ficha(ficha):
    """Rasgos DILVE de una ficha, por grupo. Los códigos jerárquicos (THEMA y
    calificadores) se devuelven como caminos de prefijos."""
    materias = ficha.get("materias") or []
    principal = [m["codigo"] for m in materias if m.get("esquema") == "93" and m.get("codigo") and m.get("principal")]
    thema = [m["codigo"] for m in materias if m.get("esquema") == "93" and m.get("codigo")]
    if not principal and thema:
        principal = thema[:1]
    secundarios = [c for c in dict.fromkeys(thema) if c not in principal]
    calificadores = [m["codigo"] for m in materias
                     if (m.get("esquema") or "") in ("94", "95", "96", "97", "98", "99") and m.get("codigo")]
    claves = []
    for m in materias:
        if m.get("esquema") == "20" and m.get("texto"):
            claves += [p for p in normaliza(m["texto"]).split() if len(p) > 3 and p not in PALABRAS_VACIAS]
    serie = _serie(ficha) if ficha.get("num_coleccion") else None
    sellos = []
    if ficha.get("coleccion") and not serie:
        sellos.append("c:" + normaliza(ficha["coleccion"]))
    if ficha.get("sello") or ficha.get("editorial"):
        sellos.append("e:" + normaliza(ficha.get("sello") or ficha.get("editorial")))
    return {
        "autores": autores_dilve(ficha),
        "serie": serie,
        "sellos": sellos,
        # Sin caminos vacíos: un código de un solo carácter o mal formado no da
        # prefijos válidos y no debe romper nada
        "thema_principal": [c for c in (_prefijos(x) for x in principal[:1]) if c],
        "thema_secundario": [c for c in (_prefijos(x) for x in secundarios) if c],
        "calificadores": [c for c in (_prefijos(x, 2) for x in dict.fromkeys(calificadores)) if c],
        "claves": list(dict.fromkeys(claves))[:15],
        "premio": bool(ficha.get("premios")),
    }


def _lista_rasgos(r):
    """Claves planas de un juego de rasgos (para contar préstamos)."""
    salida = []
    if r["serie"]:
        salida.append("s:" + r["serie"])
    salida += r["sellos"]
    for camino in r["thema_principal"] + r["thema_secundario"]:
        salida += ["t:" + p for p in camino]
    for camino in r["calificadores"]:
        salida += ["q:" + p for p in camino]
    salida += ["k:" + k for k in r["claves"]]
    if r["premio"]:
        salida.append("p")
    return list(dict.fromkeys(salida))


def _grupo(clave):
    return {"s": "serie", "c": "sello", "e": "sello", "t": "thema", "q": "calificador",
            "k": "clave", "p": "premio", "a": "autor"}[clave.split(":", 1)[0]]


def _padre(clave):
    """Padre jerárquico de un rasgo THEMA o calificador; None en los demás."""
    if clave[:2] not in ("t:", "q:"):
        return None
    codigo = clave[2:].rstrip("-")
    minimo = 1 if clave[:2] == "t:" else 2
    if len(codigo) <= minimo:
        return None
    padre = codigo[:-1].rstrip("-")
    return clave[:2] + padre if len(padre) >= minimo else None


# ---------------------------------------------------------------------------
# Títulos propios con préstamos y exposición
# ---------------------------------------------------------------------------
def titulos_propios(registros, anio_actual, parametros=None):
    """Agrupa los ejemplares por título: préstamos estimados y exposición."""
    p = parametros or DEFECTO
    ventana = float(p["ventana_anios"])
    estimados = p["prestamos_estimados"]
    por = {}
    for r in registros:
        if r.get("es_audiovisual") or "DVD" in str(r.get("categoria_estandar") or r.get("categoria") or ""):
            continue
        isbn = isbn13(r.get("isbn"))
        clave = isbn or f"{normaliza(r.get('autor'))[:30]}|{normaliza(r.get('titulo'))[:40]}"
        anio = r.get("year")
        anios = ventana if not anio else min(ventana, max(0.5, anio_actual - int(anio) + 0.5))
        if r.get("n_prestamos"):
            prestamos = float(r["n_prestamos"])
        else:
            prestamos = float(estimados[min(max(int(r.get("prestamos") or 0), 0), 2)])
        t = por.setdefault(clave, {
            "isbn": isbn, "autor": clave_autor(r.get("autor")), "titulo": r.get("titulo"),
            "seccion": mod_materias.seccion_de_signatura(r.get("categoria_estandar") or r.get("categoria")),
            "anio": int(anio) if anio else None, "L": 0.0, "E": 0.0, "ejemplares": 0,
        })
        t["L"] += prestamos
        t["E"] += anios
        t["ejemplares"] += 1
    return list(por.values())


# ---------------------------------------------------------------------------
# Construcción del modelo
# ---------------------------------------------------------------------------
def _tasas_seccion(titulos, m):
    L = sum(t["L"] for t in titulos)
    E = sum(t["E"] for t in titulos) or 1.0
    mu = max(L / E, 1e-6)
    por = collections.defaultdict(lambda: [0.0, 0.0])
    for t in titulos:
        por[t["seccion"]][0] += t["L"]
        por[t["seccion"]][1] += t["E"]
    secciones = {s: max((l + m * mu) / (e + m), 1e-6) for s, (l, e) in por.items() if s}
    return mu, secciones, {s: l for s, (l, e) in por.items() if s}


def construir(registros, fichas_propias, anio_actual, parametros=None):
    """Modelo serializable (JSON) con las tasas y los pesos de cada rasgo."""
    p = parametros or DEFECTO
    m = p["m"]
    titulos = titulos_propios(registros, anio_actual, p)
    if not titulos:
        return None
    mu, mu_sec, prestamos_sec = _tasas_seccion(titulos, m["seccion"])

    # Autores: con todo el catálogo propio, tenga o no ficha DILVE
    por_autor = collections.defaultdict(lambda: [0.0, 0.0, collections.Counter()])
    for t in titulos:
        if t["autor"]:
            a = por_autor[t["autor"]]
            a[0] += t["L"]
            a[1] += t["E"]
            a[2][t["seccion"]] += 1
    pesos, datos = {}, {}
    for autor, (l, e, secciones) in por_autor.items():
        previa = mu_sec.get(secciones.most_common(1)[0][0], mu)
        r = (l + m["autor"] * previa) / (e + m["autor"])
        w = math.log(r / previa)
        if abs(w) > 0.01:
            pesos["a:" + autor] = round(w, 4)
            datos["a:" + autor] = [round(l, 1), sum(secciones.values())]

    # Rasgos DILVE: solo con los títulos que tienen ficha. Sus tasas previas
    # se calculan dentro de ese mismo subconjunto, para que la selección de
    # qué fichas se descargaron (más prestados, sobre todo) no las sesgue.
    con_ficha = [(t, fichas_propias[t["isbn"]]) for t in titulos
                 if t["isbn"] and t["isbn"] in (fichas_propias or {})]
    cobertura = {"titulos": len(titulos), "con_ficha": len(con_ficha),
                 "nunca_con_ficha": sum(1 for t, _ in con_ficha if t["L"] == 0)}
    if con_ficha:
        sub = [t for t, _ in con_ficha]
        mu_f, mu_sec_f, _ = _tasas_seccion(sub, m["seccion"])
        L, E, seccion_de = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
        for t, ficha in con_ficha:
            for clave in _lista_rasgos(rasgos_ficha(ficha)):
                L[clave] += t["L"]
                E[clave] += t["E"]
                seccion_de[clave][t["seccion"]] += 1
        tasas = {}
        for clave in sorted(E, key=lambda c: (len(c), c)):      # padres antes que hijos
            padre = _padre(clave)
            if padre is not None or clave[:2] in ("t:", "q:"):
                previa = tasas.get(padre, mu_f) if padre else mu_f
            else:
                previa = mu_sec_f.get(seccion_de[clave].most_common(1)[0][0], mu_f)
            r = (L[clave] + m[_grupo(clave)] * previa) / (E[clave] + m[_grupo(clave)])
            tasas[clave] = r
            w = math.log(r / previa)
            if abs(w) > 0.01:
                pesos[clave] = round(w, 4)
                datos[clave] = [round(L[clave], 1), sum(seccion_de[clave].values())]

    total_prestamos = sum(prestamos_sec.values()) or 1.0
    return {
        "version": 2, "mu": mu, "mu_seccion": mu_sec,
        "reparto_prestamo": {s: l / total_prestamos for s, l in prestamos_sec.items()},
        "pesos": pesos, "datos": datos, "cobertura": cobertura, "parametros": p,
    }


# ---------------------------------------------------------------------------
# Previsión de una novedad
# ---------------------------------------------------------------------------
def _camino(pesos, prefijo, camino):
    return sum(pesos.get(prefijo + c, 0.0) for c in camino)


def prever(ficha, modelo, seccion=None):
    """(préstamos esperados por ejemplar y año, explicación, veces lo habitual
    en su sección) de una ficha. La tercera cifra es la que se enseña: una
    novedad no tiene años de estantería, y compararla con su sección se
    entiende mejor que una tasa anual."""
    p = modelo["parametros"]
    beta, pesos = p["beta"], modelo["pesos"]
    r = rasgos_ficha(ficha)
    senal, motivo = {}, {}

    autores = [(pesos.get("a:" + a, 0.0), a) for a in r["autores"]]
    if autores:
        senal["autor"], motivo["autor"] = max(autores)
        motivo["autor"] = "a:" + motivo["autor"]
    if r["serie"]:
        senal["serie"], motivo["serie"] = pesos.get("s:" + r["serie"], 0.0), "s:" + r["serie"]
    if r["sellos"]:
        valores = [(pesos.get(s, 0.0), s) for s in r["sellos"]]
        senal["sello"] = sum(v for v, _ in valores) / len(valores)
        motivo["sello"] = max(valores)[1]
    principal = [_camino(pesos, "t:", c) for c in r["thema_principal"]]
    secundario = [_camino(pesos, "t:", c) for c in r["thema_secundario"]]
    if principal or secundario:
        senal["thema"] = (sum(principal) + p["peso_thema_secundario"]
                          * (sum(secundario) / len(secundario) if secundario else 0.0))
        caminos = r["thema_principal"] + r["thema_secundario"]
        motivo["thema"] = "t:" + max(caminos, key=lambda c: _camino(pesos, "t:", c))[-1]
    if r["calificadores"]:
        valores = [(_camino(pesos, "q:", c), c[-1]) for c in r["calificadores"]]
        senal["calificador"] = sum(v for v, _ in valores) / len(valores)
        motivo["calificador"] = "q:" + max(valores)[1]
    if r["claves"]:
        valores = sorted(((pesos.get("k:" + k, 0.0), k) for k in r["claves"]), key=lambda x: -abs(x[0]))[:5]
        senal["clave"] = sum(v for v, _ in valores) / len(valores)
        motivo["clave"] = "k:" + max(valores)[1]
    if r["premio"]:
        senal["premio"] = max(pesos.get("p", 0.0), p["premio_minimo"])
        motivo["premio"] = "p"

    seccion = seccion or mod_materias.clasificar(ficha)[0]
    base = modelo["mu_seccion"].get(seccion, modelo["mu"])
    aportes = {g: beta.get(g, 0.0) * v for g, v in senal.items()}
    log_lambda = math.log(base) + sum(aportes.values())

    local = p.get("local") or {}
    es_local = (any(c[-1].startswith(tuple(local.get("prefijos") or ["\0"])) for c in r["calificadores"])
                or any(a.split("|")[0] in {normaliza(x) for x in local.get("autores") or []} for a in r["autores"])
                or normaliza(ficha.get("editorial")) in {normaliza(x) for x in local.get("editoriales") or []})
    if es_local and local.get("peso"):
        aportes["local"] = float(local["peso"])
        motivo["local"] = "local"
        log_lambda += aportes["local"]

    # Explicación: los tres aportes positivos mayores, con sus datos
    explicacion = []
    for grupo, valor in sorted(aportes.items(), key=lambda x: -x[1]):
        if valor <= 0.02 or len(explicacion) == 3:
            continue
        clave = motivo.get(grupo, "")
        prestamos, titulos = (modelo["datos"].get(clave) or [None, None])
        explicacion.append({"tipo": grupo, "valor": _rotulo(clave, ficha), "prestamos": prestamos,
                            "titulos": titulos})
    return math.exp(log_lambda), explicacion, math.exp(log_lambda) / base


def _rotulo(clave, ficha):
    tipo, _, valor = clave.partition(":")
    if tipo == "a":
        for c in ficha.get("contribuidores") or []:
            if clave_autor(c.get("invertido") or "") == valor:
                return c.get("invertido") or c.get("nombre")
        return valor.split("|")[0].title()
    if tipo == "s":
        return ficha.get("coleccion") or valor
    if tipo == "e":
        return ficha.get("sello") or ficha.get("editorial") or valor
    if tipo == "c":
        return ficha.get("coleccion") or valor
    return valor or tipo


# ---------------------------------------------------------------------------
# Reordenación calibrada por secciones, con topes
# ---------------------------------------------------------------------------
def _kl(objetivo, conteo, total):
    kl = 0.0
    for s, q in objetivo.items():
        p = 0.99 * (conteo.get(s, 0) / total if total else 0.0) + 0.01 * q
        kl += q * math.log(q / p)
    return kl


def reordenar(propuestas, modelo):
    """Calibra los primeros puestos al reparto objetivo por secciones y
    aplica topes por serie y autor en cada bloque. `propuestas` llega
    ordenada por previsión (campo «prevision») y cada una trae «seccion»,
    «_serie» y «_autores»."""
    p = modelo["parametros"]
    n = min(len(propuestas), int(p["calibrar_primeros"]))
    if n < 3:
        return propuestas
    cabeza, cola = propuestas[:n], propuestas[n:]
    secciones = {x["seccion"] for x in cabeza}
    reparto = modelo.get("reparto_prestamo") or {}
    alfa = float(p["calibracion_prestamo"])
    objetivo = {s: alfa * reparto.get(s, 0.0) + (1 - alfa) / len(secciones) for s in secciones}
    suma = sum(objetivo.values()) or 1.0
    objetivo = {s: v / suma for s, v in objetivo.items() if v > 0}
    logs = [math.log(max(x["prevision"], 1e-9)) for x in cabeza]
    bajo, alto = min(logs), max(logs)
    norma = [(v - bajo) / (alto - bajo) if alto > bajo else 1.0 for v in logs]
    lam = float(p["calibracion"])
    bloque, tope_s, tope_a = int(p["bloque"]), int(p["tope_serie"]), int(p["tope_autor"])

    elegidos, pendientes = [], list(range(n))
    conteo = collections.Counter()
    por_serie, por_autor = collections.Counter(), collections.Counter()
    while pendientes:
        if len(elegidos) % bloque == 0:
            por_serie.clear()
            por_autor.clear()
        mejor, mejor_valor = None, None
        for i in pendientes:
            x = cabeza[i]
            if x.get("_serie") and por_serie[x["_serie"]] >= tope_s:
                continue
            if any(por_autor[a] >= tope_a for a in x.get("_autores") or []):
                continue
            conteo[x["seccion"]] += 1
            valor = (1 - lam) * norma[i] - lam * _kl(objetivo, conteo, len(elegidos) + 1)
            conteo[x["seccion"]] -= 1
            if mejor_valor is None or valor > mejor_valor:
                mejor, mejor_valor = i, valor
        if mejor is None:                   # todo lo que queda choca con los topes
            elegidos += pendientes
            break
        x = cabeza[mejor]
        elegidos.append(mejor)
        pendientes.remove(mejor)
        conteo[x["seccion"]] += 1
        if x.get("_serie"):
            por_serie[x["_serie"]] += 1
        for a in x.get("_autores") or []:
            por_autor[a] += 1
    return [cabeza[i] for i in elegidos] + cola


# ---------------------------------------------------------------------------
# Evaluación retrospectiva (back-test temporal)
# ---------------------------------------------------------------------------
def _rangos(valores):
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    rangos = [0.0] * len(valores)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and valores[orden[j + 1]] == valores[orden[i]]:
            j += 1
        for k in range(i, j + 1):
            rangos[orden[k]] = (i + j) / 2 + 1
        i = j + 1
    return rangos


def spearman(x, y):
    if len(x) < 3:
        return None
    rx, ry = _rangos(x), _rangos(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def ndcg(puntos, ganancia, k):
    orden = sorted(range(len(puntos)), key=lambda i: -puntos[i])[:k]
    ideal = sorted(ganancia, reverse=True)[:k]
    dcg = sum(ganancia[i] / math.log2(p + 2) for p, i in enumerate(orden))
    idcg = sum(g / math.log2(p + 2) for p, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def auc(puntos, positivo):
    pos = [s for s, z in zip(puntos, positivo) if z]
    neg = [s for s, z in zip(puntos, positivo) if not z]
    if not pos or not neg:
        return None
    r = _rangos(puntos)
    suma_pos = sum(ri for ri, z in zip(r, positivo) if z)
    return (suma_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def _metricas(puntos, tasa, prestado, k):
    orden = sorted(range(len(puntos)), key=lambda i: -puntos[i])[:k]
    return {
        "spearman": spearman(puntos, tasa),
        "ndcg": ndcg(puntos, [math.log1p(v) for v in tasa], k),
        "auc": auc(puntos, prestado),
        "nunca_en_top": sum(1 for i in orden if not prestado[i]) / len(orden) if orden else None,
    }


def evaluar(registros, fichas_propias, anio_actual, corte=None, parametros=None,
            perfil_v1=None, parecido_v1=None, nucleo_v1=None, repeticiones=1000, semilla=7):
    """Compara el modelo con el orden anterior y con dos referencias.

    Entrenamiento: títulos editados antes de `corte`. Prueba: los editados
    entre `corte` y `corte`+2 que tienen ficha DILVE. Todo lo que usa el
    modelo (tasas, pesos, perfil anterior) sale solo del entrenamiento."""
    p = parametros or DEFECTO
    corte = int(corte or anio_actual - 3)
    entrenamiento = [r for r in registros if r.get("year") and int(r["year"]) < corte]
    prueba_reg = [r for r in registros if r.get("year") and corte <= int(r["year"]) <= corte + 2]
    modelo = construir(entrenamiento, fichas_propias, anio_actual, p)
    prueba = [t for t in titulos_propios(prueba_reg, anio_actual, p)
              if t["isbn"] and t["isbn"] in fichas_propias and t["E"] > 0]
    avisos = []
    if not any((r.get("prestamos") == 0) for r in registros):
        avisos.append("sin_no_prestados")
    if len(prueba) < 150:
        avisos.append("muestra_pequena")
    if not modelo or len(prueba) < 10:
        return {"corte": corte, "n_prueba": len(prueba), "avisos": avisos + ["insuficiente"], "metodos": {}}

    tasa = [t["L"] / t["E"] for t in prueba]
    prestado = [t["L"] > 0 for t in prueba]
    k = min(50, len(prueba))
    rng = random.Random(semilla)
    puntos = {
        "azar": [rng.random() for _ in prueba],
        "seccion": [modelo["mu_seccion"].get(t["seccion"], modelo["mu"]) for t in prueba],
        "nuevo": [prever(fichas_propias[t["isbn"]], modelo, t["seccion"])[0] for t in prueba],
    }
    if perfil_v1 and parecido_v1 and nucleo_v1:
        nucleo = nucleo_v1(entrenamiento)
        perfil = perfil_v1(fichas_propias and {t["isbn"]: fichas_propias[t["isbn"]]
                                               for t in nucleo if t.get("isbn") in fichas_propias}, nucleo)
        puntos["anterior"] = [parecido_v1(fichas_propias[t["isbn"]], perfil)[0] for t in prueba]

    metodos = {nombre: _metricas(v, tasa, prestado, k) for nombre, v in puntos.items()}

    # Intervalo bootstrap de la mejora del modelo nuevo frente a cada referencia
    diferencias = {}
    n = len(prueba)
    for rival in [r for r in ("anterior", "seccion") if r in puntos]:
        muestras = {"spearman": [], "ndcg": []}
        for _ in range(repeticiones):
            idx = [rng.randrange(n) for _ in range(n)]
            t_ = [tasa[i] for i in idx]
            for metrica in muestras:
                a = [puntos["nuevo"][i] for i in idx]
                b = [puntos[rival][i] for i in idx]
                if metrica == "spearman":
                    va, vb = spearman(a, t_), spearman(b, t_)
                else:
                    g = [math.log1p(v) for v in t_]
                    va, vb = ndcg(a, g, k), ndcg(b, g, k)
                if va is not None and vb is not None:
                    muestras[metrica].append(va - vb)
        diferencias[rival] = {m: _intervalo(v) for m, v in muestras.items()}

    return {"corte": corte, "anios_prueba": [corte, corte + 2], "n_prueba": n,
            "n_entrenamiento": modelo["cobertura"]["titulos"], "k": k,
            "cobertura": modelo["cobertura"], "base_nunca": 1 - sum(prestado) / n,
            "metodos": metodos, "mejora": diferencias, "avisos": avisos}


def _intervalo(valores):
    if not valores:
        return None
    v = sorted(valores)
    return {"media": sum(v) / len(v), "bajo": v[int(0.025 * (len(v) - 1))], "alto": v[int(0.975 * (len(v) - 1))]}
