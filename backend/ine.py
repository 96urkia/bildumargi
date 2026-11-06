# -*- coding: utf-8 -*-
"""Población y demografía del municipio, desde la API JSON del INE (Tempus3).

De un código postal a los datos, en tres pasos:

  1. Código postal -> municipios. El INE no publica esta relación en su API:
     sale de su Callejero del Censo Electoral (datos/codigos_postales.csv). Un
     código puede abarcar varios municipios (31522: Monteagudo y Tulebras), y
     una ciudad, varios códigos: por eso quien configura elige los municipios.
  2. Código de municipio (31173) -> identificador interno del INE (481).
  3. Una consulta por tabla, filtrada por ese identificador.

Dos fuentes, a propósito, que no dan la misma cifra:

  · Cifras oficiales del Padrón (operación DPOP): el «número de habitantes»,
    el que se usa para los documentos por habitante. Una tabla por provincia.
  · Censo anual de población (operación CENSOP): la composición, por edad,
    nacionalidad y país de nacimiento. Es el que sustituyó a la Estadística
    del Padrón continuo, cuyas tablas municipales acaban en 2021.

Lo descargado se guarda en datos/ine/: si el INE no responde (cortafuegos, sin
conexión), se sigue trabajando con la última copia.
"""

import csv
import datetime
import json
import os
import re
import threading

URL_BASE = "https://servicios.ine.es/wstempus/js/ES/"
TIEMPO_MAXIMO = 40          # segundos por consulta
DIAS_VIGENCIA = 30          # el INE publica una vez al año: basta con mirar al mes
VARIABLE_MUNICIPIOS = 19
VARIABLE_SEXO = 18

# Tablas nacionales del Censo anual, con todos los municipios
TABLA_EDAD = 68535          # sexo, edad (quinquenal) y nacionalidad (española/extranjera)
TABLA_NACIONALIDAD = 66323  # sexo y país de nacionalidad
TABLA_NACIMIENTO = 66322    # sexo y país de nacimiento
TABLA_EDAD_MEDIA = 68541    # población y edad media, por lugar de nacimiento
TABLA_EDAD_SIMPLE = 68542   # sexo y edad, año a año (para el corte de los 18 años)

# Cifras oficiales del Padrón: «<Provincia>: Población por municipios y sexo»
TABLAS_PADRON = {
    "01": 2854, "02": 2855, "03": 2856, "04": 2857, "05": 2858, "06": 2859,
    "07": 2860, "08": 2861, "09": 2862, "10": 2863, "11": 2864, "12": 2865,
    "13": 2866, "14": 2901, "15": 2868, "16": 2869, "17": 2870, "18": 2871,
    "19": 2872, "20": 2873, "21": 2874, "22": 2875, "23": 2876, "24": 2877,
    "25": 2878, "26": 2879, "27": 2880, "28": 2881, "29": 2882, "30": 2883,
    "31": 2884, "32": 2885, "33": 2886, "34": 2888, "35": 2889, "36": 2890,
    "37": 2891, "38": 2892, "39": 2893, "40": 2894, "41": 2895, "42": 2896,
    "43": 2900, "44": 2899, "45": 2902, "46": 2903, "47": 2904, "48": 2905,
    "49": 2906, "50": 2907, "51": 2908, "52": 2909,
}

# Identificadores de valores del INE. Se usan estos y no los nombres porque el
# orden y el rótulo de los metadatos cambian de una serie a otra de la tabla.
SEXOS = {451: "total", 452: "hombres", 453: "mujeres"}
TOTAL_PAISES = 16420
TODAS_LAS_EDADES = 15668
ESPANOLA = 21386
ESPANA = 274511
EXTRANJERO = 274512         # «Extranjera» en nacionalidad, «Extranjero» en nacimiento
CONCEPTO_POBLACION = 17338
CONCEPTO_EDAD_MEDIA = 274520
EDADES = (
    (15073, "0-4", 0), (15664, "5-9", 5), (15660, "10-14", 10), (15665, "15-19", 15),
    (15661, "20-24", 20), (15666, "25-29", 25), (15662, "30-34", 30), (15658, "35-39", 35),
    (15663, "40-44", 40), (15667, "45-49", 45), (15648, "50-54", 50), (15649, "55-59", 55),
    (15650, "60-64", 60), (15651, "65-69", 65), (15652, "70-74", 70), (15653, "75-79", 75),
    (15654, "80-84", 80), (15655, "85-89", 85), (15656, "90-94", 90), (15070, "95-99", 95),
    (15071, "100+", 100),
)


class ErrorINE(Exception):
    """El INE no responde o responde algo que no se entiende."""


class CodigoNoValido(ValueError):
    pass


# --- 1. Código postal -> municipios -------------------------------------------
_CODIGOS = {}
_CODIGOS_CANDADO = threading.Lock()


def _tabla_codigos(ruta):
    with _CODIGOS_CANDADO:
        if ruta not in _CODIGOS:
            tabla = {}
            with open(ruta, encoding="utf-8", newline="") as f:
                for fila in csv.DictReader(f):
                    tabla.setdefault(fila["codigo_postal"], []).append(
                        {"codigo": fila["municipio"], "nombre": fila["nombre"]})
            _CODIGOS[ruta] = tabla
        return _CODIGOS[ruta]


def municipios_de_cp(codigo_postal, ruta):
    """Municipios de un código postal: primero los de su propia provincia."""
    cp = str(codigo_postal or "").strip()
    if not re.fullmatch(r"\d{5}", cp):
        raise CodigoNoValido("El código postal tiene cinco cifras.")
    lista = _tabla_codigos(ruta).get(cp, [])
    return sorted(lista, key=lambda m: (m["codigo"][:2] != cp[:2], m["nombre"]))


def validar_municipios(codigos):
    salida = []
    for codigo in codigos or []:
        codigo = str(codigo).strip()
        if not re.fullmatch(r"\d{5}", codigo) or codigo[:2] not in TABLAS_PADRON:
            raise CodigoNoValido(f"Código de municipio no válido: {codigo}")
        if codigo not in salida:
            salida.append(codigo)
    return salida


# --- Cliente de la API --------------------------------------------------------
class Cliente:
    """Consultas a la API, con una copia en disco de lo ya descargado."""

    def __init__(self, carpeta, sesion=None):
        self.carpeta = carpeta
        self._sesion = sesion
        self._candado = threading.Lock()

    def _http(self):
        if self._sesion is None:
            import requests
            self._sesion = requests.Session()
            self._sesion.headers["User-Agent"] = "Bildumargi"
        return self._sesion

    def _pedir(self, ruta, parametros=None):
        try:
            r = self._http().get(URL_BASE + ruta, params=parametros, timeout=TIEMPO_MAXIMO)
            r.raise_for_status()
            datos = r.json()
        except Exception as exc:    # red, cortafuegos, JSON roto: todo es «no responde»
            raise ErrorINE(f"El INE no ha respondido ({type(exc).__name__}).") from exc
        if not isinstance(datos, list):
            raise ErrorINE("El INE ha respondido con un formato inesperado.")
        return datos

    # --- 2. Código de municipio -> identificador del INE
    def _ruta(self, nombre):
        return os.path.join(self.carpeta, nombre)

    def _leer(self, nombre):
        try:
            with open(self._ruta(nombre), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _escribir(self, nombre, datos):
        os.makedirs(self.carpeta, exist_ok=True)
        temporal = self._ruta(nombre) + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(temporal, self._ruta(nombre))

    def identificadores(self):
        """{código de municipio: (identificador, nombre)}. Unos 800 KB: se
        descarga una vez y se conserva."""
        guardado = self._leer("municipios.json")
        if guardado:
            return guardado
        grupos = self._pedir(f"GRUPOS_TABLA/{TABLA_EDAD}")
        grupo = next((g["Id"] for g in grupos if g.get("Nombre") == "Municipios"), None)
        if grupo is None:
            raise ErrorINE("La tabla de municipios del INE ha cambiado.")
        tabla = {v["Codigo"]: [v["Id"], v["Nombre"]]
                 for v in self._pedir(f"VALORES_GRUPOSTABLA/{TABLA_EDAD}/{grupo}")
                 if v.get("FK_Variable") == VARIABLE_MUNICIPIOS}
        if not tabla:
            raise ErrorINE("El INE no ha devuelto municipios.")
        self._escribir("municipios.json", tabla)
        return tabla

    # --- 3. Datos de un municipio
    def _tabla(self, tabla, identificador, nult=1, solo_total=False):
        parametros = [("tv", f"{VARIABLE_MUNICIPIOS}:{identificador}")]
        if solo_total:
            parametros.append(("tv", f"{VARIABLE_SEXO}:451"))
        parametros += [("nult", nult), ("tip", "AM")]
        return self._pedir(f"DATOS_TABLA/{tabla}", parametros)

    def _descargar(self, codigo):
        fila = self.identificadores().get(codigo)
        if not fila:
            raise ErrorINE(f"El INE no tiene el municipio {codigo}.")
        identificador, nombre = fila
        datos = {
            "codigo": codigo, "nombre": nombre,
            "descargado": datetime.date.today().isoformat(),
            "padron": leer_padron(self._tabla(TABLAS_PADRON[codigo[:2]], identificador, nult=10)),
            "censo": leer_censo(
                self._tabla(TABLA_EDAD, identificador),
                self._tabla(TABLA_NACIONALIDAD, identificador, solo_total=True),
                self._tabla(TABLA_NACIMIENTO, identificador, solo_total=True),
                self._tabla(TABLA_EDAD_MEDIA, identificador),
                self._tabla(TABLA_EDAD_SIMPLE, identificador, solo_total=True)),
        }
        return datos

    def municipio(self, codigo, actualizar=False):
        """Datos de un municipio: la copia si está al día; si no, se descarga.
        Si el INE no responde se sirve la copia, aunque sea vieja, con
        `sin_conexion` para que la interfaz lo diga."""
        nombre = f"municipio_{codigo}.json"
        with self._candado:
            copia = self._leer(nombre)
            if copia and not actualizar and _vigente(copia):
                return copia
            try:
                datos = self._descargar(codigo)
            except ErrorINE as exc:
                if copia:
                    return {**copia, "sin_conexion": str(exc)}
                raise
            self._escribir(nombre, datos)
            return datos


def _vigente(copia):
    if not (copia.get("censo") or {}).get("edades_simples"):
        return False            # copia anterior al corte de los 18 años
    try:
        fecha = datetime.date.fromisoformat(copia["descargado"])
    except (KeyError, TypeError, ValueError):
        return False
    return (datetime.date.today() - fecha).days < DIAS_VIGENCIA


# --- Lectura de las respuestas ------------------------------------------------
def _ids(serie):
    return {m.get("Id") for m in serie.get("MetaData") or []}


def _sexo(serie):
    return next((SEXOS[i] for i in _ids(serie) if i in SEXOS), None)


def _ultimo(serie):
    """(año, valor) del dato más reciente de la serie; None si no hay dato."""
    puntos = [p for p in serie.get("Data") or [] if p.get("Valor") is not None]
    if not puntos:
        return None
    p = max(puntos, key=lambda x: x["Anyo"])
    return p["Anyo"], p["Valor"]


def leer_padron(series):
    salida = {"anio": None, "total": None, "hombres": None, "mujeres": None, "serie": []}
    for s in series:
        sexo = _sexo(s)
        if not sexo:
            continue
        ultimo = _ultimo(s)
        if ultimo:
            salida["anio"], salida[sexo] = ultimo[0], int(ultimo[1])
        if sexo == "total":
            salida["serie"] = sorted(({"anio": p["Anyo"], "valor": int(p["Valor"])}
                                      for p in s.get("Data") or [] if p.get("Valor") is not None),
                                     key=lambda p: p["anio"])
    if salida["total"] is None:
        raise ErrorINE("El Padrón no trae el total de habitantes de este municipio.")
    return salida


def _paises(series, excluir):
    """[{codigo, nombre, valor}] de las series «Total sexo». El país es el
    metadato que no es municipio, sexo, edad ni tipo de dato."""
    salida = []
    for s in series:
        if _sexo(s) != "total":
            continue
        ultimo = _ultimo(s)
        if not ultimo:
            continue
        for m in s.get("MetaData") or []:
            if m.get("T3_Variable") in ("Nacionalidad", "Países", "Lugar de nacimiento", "País de nacimiento"):
                if m.get("Id") not in excluir and ultimo[1]:
                    salida.append({"codigo": m.get("Codigo"), "nombre": m.get("Nombre"),
                                   "valor": int(ultimo[1])})
                break
    return salida


def _edades_simples(series):
    """{edad: personas}, con «100 y más» como 100. El código del INE es Y15 o Y-GE100."""
    salida = {}
    for s in series:
        ultimo = _ultimo(s)
        if not ultimo or _sexo(s) != "total":
            continue
        for m in s.get("MetaData") or []:
            encontrado = re.fullmatch(r"Y(?:-GE)?(\d+)", str(m.get("Codigo") or ""))
            if encontrado:
                salida[encontrado.group(1)] = int(ultimo[1])
                break
    return salida


def leer_censo(edad, nacionalidad, nacimiento, edad_media, edad_simple):
    salida = {"anio": None, "total": None, "hombres": None, "mujeres": None,
              "espanola": None, "extranjera": None,
              "nacidos_espana": None, "nacidos_extranjero": None,
              "edad_media": None, "edad_media_espana": None, "edad_media_extranjero": None,
              "edades": [], "paises_nacionalidad": [], "paises_nacimiento": []}
    tramos = {t[0]: {"tramo": t[1], "desde": t[2], "total": 0, "hombres": 0, "mujeres": 0} for t in EDADES}
    for s in edad:
        ids, sexo, ultimo = _ids(s), _sexo(s), _ultimo(s)
        if not sexo or not ultimo:
            continue
        salida["anio"] = ultimo[0]
        valor = int(ultimo[1])
        if TOTAL_PAISES in ids:
            if TODAS_LAS_EDADES in ids:
                salida[sexo] = valor
            else:
                for clave, tramo in tramos.items():
                    if clave in ids:
                        tramo[sexo] = valor
        elif TODAS_LAS_EDADES in ids and sexo == "total":
            if ESPANOLA in ids:
                salida["espanola"] = valor
            elif EXTRANJERO in ids:
                salida["extranjera"] = valor
    if salida["total"] is None:
        raise ErrorINE("El Censo no trae el total de población de este municipio.")
    salida["edades"] = [tramos[t[0]] for t in EDADES]
    salida["edades_simples"] = _edades_simples(edad_simple)
    salida["paises_nacionalidad"] = _paises(nacionalidad, {TOTAL_PAISES, ESPANOLA})
    salida["paises_nacimiento"] = _paises(nacimiento, {TOTAL_PAISES, ESPANA})
    for s in edad_media:
        ids, ultimo = _ids(s), _ultimo(s)
        if _sexo(s) != "total" or not ultimo:
            continue
        if CONCEPTO_POBLACION in ids:
            if ESPANA in ids:
                salida["nacidos_espana"] = int(ultimo[1])
            elif EXTRANJERO in ids:
                salida["nacidos_extranjero"] = int(ultimo[1])
        elif CONCEPTO_EDAD_MEDIA in ids:
            if TOTAL_PAISES in ids:
                salida["edad_media"] = float(ultimo[1])
            elif ESPANA in ids:
                salida["edad_media_espana"] = float(ultimo[1])
            elif EXTRANJERO in ids:
                salida["edad_media_extranjero"] = float(ultimo[1])
    return salida


# --- Suma de los municipios atendidos e indicadores -----------------------------
def _sumar_paises(municipios, clave):
    suma = {}
    for m in municipios:
        for p in m["censo"][clave]:
            fila = suma.setdefault(p["codigo"], {"codigo": p["codigo"], "nombre": p["nombre"], "valor": 0})
            fila["valor"] += p["valor"]
    return sorted(suma.values(), key=lambda p: (-p["valor"], p["nombre"]))


def _suma(municipios, fuente, clave):
    valores = [m[fuente].get(clave) for m in municipios]
    return None if any(v is None for v in valores) else sum(valores)


def _media_ponderada(municipios, clave, peso):
    pares = [(m["censo"].get(clave), m["censo"].get(peso)) for m in municipios]
    if any(v is None or p is None for v, p in pares):
        return None
    total = sum(p for _, p in pares)
    return round(sum(v * p for v, p in pares) / total, 2) if total else None


def _porcentaje(parte, total):
    return round(100 * parte / total, 1) if parte is not None and total else None


def agregar(municipios):
    """Los datos de uno o varios municipios, sumados, con los indicadores. Los
    años de la serie del Padrón solo se dan si los tienen todos los municipios."""
    primero = municipios[0]
    anios = set.intersection(*[{p["anio"] for p in m["padron"]["serie"]} for m in municipios])
    serie = [{"anio": a, "valor": sum(next(p["valor"] for p in m["padron"]["serie"] if p["anio"] == a)
                                      for m in municipios)} for a in sorted(anios)]
    total_censo = _suma(municipios, "censo", "total")
    edades = []
    for i, tramo in enumerate(primero["censo"]["edades"]):
        edades.append({"tramo": tramo["tramo"], "desde": tramo["desde"],
                       **{k: sum(m["censo"]["edades"][i][k] for m in municipios)
                          for k in ("total", "hombres", "mujeres")}})
    simples = None
    if all(m["censo"].get("edades_simples") for m in municipios):
        simples = {}
        for m in municipios:
            for edad, n in m["censo"]["edades_simples"].items():
                simples[edad] = simples.get(edad, 0) + n
    menores = sum(e["total"] for e in edades if e["desde"] < 15)
    mayores = sum(e["total"] for e in edades if e["desde"] >= 65)
    muy_mayores = sum(e["total"] for e in edades if e["desde"] >= 80)
    extranjera = _suma(municipios, "censo", "extranjera")
    nacidos_fuera = _suma(municipios, "censo", "nacidos_extranjero")
    paises_nac = _sumar_paises(municipios, "paises_nacionalidad")
    paises_nacim = _sumar_paises(municipios, "paises_nacimiento")
    avisos = []
    if sum(e["total"] for e in edades) != total_censo:
        avisos.append("Los tramos de edad no suman el total del Censo.")
    if extranjera is not None and sum(p["valor"] for p in paises_nac) != extranjera:
        avisos.append("Los países de nacionalidad no suman el total de población extranjera.")
    if nacidos_fuera is not None and sum(p["valor"] for p in paises_nacim) != nacidos_fuera:
        avisos.append("Los países de nacimiento no suman el total de nacidos en el extranjero.")
    sin_conexion = next((m["sin_conexion"] for m in municipios if m.get("sin_conexion")), None)
    poblacion_3_o_mas = {m["codigo"]: sum(n for e, n in (m["censo"].get("edades_simples") or {}).items() if int(e) >= 3)
                         for m in municipios}
    return {
        "municipios": [{"codigo": m["codigo"], "nombre": m["nombre"]} for m in municipios],
        "descargado": min(m["descargado"] for m in municipios),
        "sin_conexion": sin_conexion,
        "poblacion_3_o_mas": poblacion_3_o_mas,
        "avisos": avisos,
        "padron": {"anio": primero["padron"]["anio"],
                   "total": _suma(municipios, "padron", "total"),
                   "hombres": _suma(municipios, "padron", "hombres"),
                   "mujeres": _suma(municipios, "padron", "mujeres"),
                   "serie": serie},
        "censo": {
            "anio": primero["censo"]["anio"],
            "total": total_censo,
            "hombres": _suma(municipios, "censo", "hombres"),
            "mujeres": _suma(municipios, "censo", "mujeres"),
            "extranjera": extranjera,
            "pct_extranjera": _porcentaje(extranjera, total_censo),
            "nacidos_extranjero": nacidos_fuera,
            "pct_nacidos_extranjero": _porcentaje(nacidos_fuera, total_censo),
            "edad_media": _media_ponderada(municipios, "edad_media", "total"),
            "edad_media_espana": _media_ponderada(municipios, "edad_media_espana", "nacidos_espana"),
            "edad_media_extranjero": _media_ponderada(municipios, "edad_media_extranjero", "nacidos_extranjero"),
            "menores_15": menores, "pct_menores_15": _porcentaje(menores, total_censo),
            "mayores_65": mayores, "pct_mayores_65": _porcentaje(mayores, total_censo),
            "mayores_80": muy_mayores, "pct_mayores_80": _porcentaje(muy_mayores, total_censo),
            "edades": edades,
            "edades_simples": simples,
            "paises_nacionalidad": paises_nac,
            "paises_nacimiento": paises_nacim,
        },
    }


# --- Cotejo con el fondo --------------------------------------------------------
# Lengua oficial principal de cada país del Censo (por su código INE). Es una
# aproximación, y por eso la interfaz lo avisa: en Marruecos también se habla
# amazig, en Senegal wólof, etc. Los grupos «Otros países de…» y los países de
# lengua castellana no se asignan: el fondo en castellano no se puede cotejar
# con la población, porque el Censo no recoge la lengua de nadie.
LENGUA_DE_PAIS = {
    "103": "Neerlandés", "104": "Búlgaro", "107": "Danés", "109": "Finés", "110": "Francés",
    "113": "Inglés", "115": "Italiano", "120": "Noruego", "121": "Neerlandés", "122": "Polaco",
    "123": "Portugués", "125": "Inglés", "126": "Alemán", "128": "Rumano", "131": "Sueco",
    "132": "Alemán", "135": "Ucraniano", "137": "Rumano", "142": "Lituano", "154": "Ruso",
    "203": "Árabe", "216": "Inglés", "217": "Inglés", "218": "Francés", "227": "Francés",
    "228": "Árabe", "230": "Árabe", "234": "Inglés", "239": "Francés",
    "301": "Inglés", "302": "Inglés", "342": "Portugués",
    "404": "Bengalí", "407": "Chino", "409": "Filipino", "410": "Hindi", "426": "Urdu",
}
_RE_JUVENIL = re.compile(r"JUVENIL|XUVENIL|GAZTE|^JN(\s|$)", re.IGNORECASE)
GRUPOS_EDAD = (("infantil", 0, 15), ("juvenil", 15, 18), ("adultos", 18, 999))
SIN_IDIOMA = "Sin determinar"


# Conocimiento de euskera en Navarra, por municipio (datos/euskera_navarra.csv).
# Fuente: Nastat, Estadística de población según conocimiento de euskera, 2022.
# Porcentajes sobre la población de 3 años o más. No hay API: la tabla la exporta
# una persona del informe de Nastat y se actualiza con cada edición.
ANIO_EUSKERA = 2022
_EUSKERA = {}


def tabla_euskera(ruta):
    with _CODIGOS_CANDADO:
        if ruta not in _EUSKERA:
            try:
                with open(ruta, encoding="utf-8", newline="") as f:
                    _EUSKERA[ruta] = {
                        fila["municipio"]: (float(fila["vascohablante"]), float(fila["receptor"]))
                        for fila in csv.DictReader(f)}
            except (OSError, ValueError, KeyError):
                _EUSKERA[ruta] = {}
        return _EUSKERA[ruta]


def _cotejo_euskera(datos, tabla, documentos, total_fondo):
    """El euskera frente al fondo, si hay dato de todos los municipios (si no, no
    se muestra: un agregado parcial engañaría). Varios municipios: media ponderada
    por su población de 3 años o más, que es la base de los porcentajes."""
    municipios = datos.get("municipios") or []
    pesos = datos.get("poblacion_3_o_mas") or {}
    if not municipios or any(m["codigo"] not in tabla or not pesos.get(m["codigo"]) for m in municipios):
        return None
    base = sum(pesos[m["codigo"]] for m in municipios)
    vasco = sum(tabla[m["codigo"]][0] * pesos[m["codigo"]] for m in municipios) / base
    receptor = sum(tabla[m["codigo"]][1] * pesos[m["codigo"]] for m in municipios) / base
    alguno = vasco + receptor
    return {
        "lengua": "Euskera", "anio": ANIO_EUSKERA, "documentos": documentos,
        "pct_vascohablante": round(vasco, 1), "pct_receptor": round(receptor, 1), "pct_alguno": round(alguno, 1),
        "personas": round(base * alguno / 100),
        "indice": round((documentos / total_fondo) / (alguno / 100), 2) if alguno and total_fondo else None,
    }


def _publico(registro):
    if _RE_JUVENIL.search(str(registro.get("categoria") or "")):
        return "juvenil"
    return "infantil" if registro.get("es_infantil") else "adultos"


def cotejar(registros, datos, tabla_euskera_navarra=None):
    """Población frente a fondo: quién vive aquí y para quién es lo que hay. Los
    ejemplares sin público claro cuentan como adultos, igual que en el resto
    de Bildumargi; los audiovisuales van con su público."""
    censo = datos["censo"]
    total_poblacion = censo["total"] or 0
    total_fondo = len(registros)
    total_prestados = sum(1 for r in registros if r.get("prestado"))
    if not censo.get("edades_simples"):
        raise ErrorINE("Hace falta conexión con el INE para actualizar los datos de edad.")
    edades = []
    for clave, desde, hasta in GRUPOS_EDAD:
        personas = sum(n for e, n in censo["edades_simples"].items() if desde <= int(e) < hasta)
        fondo = [r for r in registros if _publico(r) == clave]
        prestados = sum(1 for r in fondo if r.get("prestado"))
        edades.append({
            "clave": clave, "personas": personas, "documentos": len(fondo), "prestados": prestados,
            "pct_poblacion": _porcentaje(personas, total_poblacion),
            "pct_fondo": _porcentaje(len(fondo), total_fondo),
            "pct_prestados": _porcentaje(prestados, total_prestados),
            "docs_persona": round(len(fondo) / personas, 1) if personas else None,
            "pct_uso": _porcentaje(prestados, len(fondo)),
        })

    conteo = {}
    for r in registros:
        idioma = r.get("idioma") or SIN_IDIOMA
        fila = conteo.setdefault(idioma, {"documentos": 0, "prestados": 0})
        fila["documentos"] += 1
        fila["prestados"] += 1 if r.get("prestado") else 0
    con_idioma = total_fondo - conteo.get(SIN_IDIOMA, {}).get("documentos", 0)
    lenguas = {}
    sin_asignar = 0
    for pais in censo["paises_nacimiento"]:
        lengua = LENGUA_DE_PAIS.get(pais["codigo"])
        if not lengua:
            sin_asignar += pais["valor"]
            continue
        fila = lenguas.setdefault(lengua, {"lengua": lengua, "personas": 0, "paises": []})
        fila["personas"] += pais["valor"]
        fila["paises"].append(pais["nombre"])
    for fila in lenguas.values():
        fondo = conteo.get(fila["lengua"], {"documentos": 0, "prestados": 0})
        fila.update(fondo)
        # Como el uso relativo: 1,0 = la lengua pesa lo mismo en el fondo que entre los vecinos
        fila["indice"] = (round((fondo["documentos"] / total_fondo) / (fila["personas"] / total_poblacion), 2)
                          if fila["personas"] and total_fondo and total_poblacion else None)
    euskera = _cotejo_euskera(datos, tabla_euskera_navarra or {},
                              conteo.get("Euskera", {}).get("documentos", 0), total_fondo)
    otras = sorted(({"lengua": k, "documentos": v["documentos"]} for k, v in conteo.items()
                    if k not in lenguas and k not in (SIN_IDIOMA, "Castellano")
                    and not (euskera and k == "Euskera")),
                   key=lambda x: -x["documentos"])
    return {
        "anio": censo["anio"],
        "total_poblacion": total_poblacion, "total_fondo": total_fondo, "total_prestados": total_prestados,
        # Con el Padrón, como el Diagnóstico: la misma cifra en las dos pantallas
        "habitantes": datos["padron"]["total"],
        "anio_padron": datos["padron"]["anio"],
        "docs_habitante": round(total_fondo / datos["padron"]["total"], 2) if datos["padron"]["total"] else None,
        "edades": edades,
        "lenguas": sorted(lenguas.values(), key=lambda x: -x["personas"]),
        "personas_sin_lengua": sin_asignar,
        "euskera": euskera,
        "otras_lenguas": otras,
        "documentos_con_idioma": con_idioma,
        "cobertura_idioma": _porcentaje(con_idioma, total_fondo) or 0.0,
    }
