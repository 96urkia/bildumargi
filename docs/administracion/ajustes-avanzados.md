# Ajustes avanzados

Casi todo se cambia en [Configuración](../uso/configuracion.md). Esta página
recoge lo que va en ficheros, para instalaciones con Python o en servidor.

## `config_local.py`

Con el zip, las claves y rutas propias de ese ordenador pueden ir en un
fichero `config_local.py`, junto a `config.py`. Lo que se escriba ahí manda
sobre `config.py`, y **no se sube al repositorio ni entra en el zip**:

```python
DILVE_USUARIO = "..."
DILVE_CLAVE = "..."
CLAVE_ADMIN = "una-clave-larga-que-no-uses-para-nada-más"
PUERTO = 8000
```

En un servidor, lo mismo va en variables de entorno (ver
[Ficheros y carpetas](../referencia/ficheros.md#variables-de-entorno)).

## Clave de configuración

Por defecto, cualquiera que use Bildumargi puede cambiar la configuración,
que es lo normal en un solo ordenador. En una instalación compartida (un
servidor al que entran varios ordenadores), conviene poner una clave:
`CLAVE_ADMIN` en `config_local.py` o `BILDUMARGI_CLAVE_ADMIN`. El paquete
`.deb` la genera sola en `/etc/bildumargi/secretos.env`.

Con clave, la Configuración la pide antes de abrirse. El acceso dura dos
horas. No hay recuperación por correo: si se olvida, se pone otra y se
reinicia Bildumargi.

## Referencia de fondo por habitante: `pautas.json`

El Diagnóstico compara los documentos por habitante con una referencia. Por
defecto, las **Pautas sobre los servicios de las bibliotecas públicas
(2002)**: de 1,5 a 2,5 documentos por habitante y un fondo mínimo de 2.500.

Se puede poner otra, por tramos de población, en `pautas.json` (carpeta de
datos):

```json
{
  "fuente": "Estándar de la red (nombre completo y año)",
  "fuente_corta": "Estándar de la red",
  "tramos": [
    {"hasta_habitantes": 3000,  "docs_hab_min": 3.0, "docs_hab_max": 3.0},
    {"hasta_habitantes": 10000, "docs_hab_min": 2.5, "docs_hab_max": 2.5},
    {"hasta_habitantes": null,  "docs_hab_min": 1.5, "docs_hab_max": 2.5, "fondo_minimo": 2500}
  ]
}
```

Se aplica el primer tramo cuyo `hasta_habitantes` sea mayor o igual que la
población; `null` significa «sin límite».

## Materias y secciones: `materias_secciones.json`

Ajusta cómo se asignan secciones a los libros de DILVE a partir de sus
materias Thema:

```json
{"secciones": {"MKM": "6", "WH": "N"}}
```

## Modelo de préstamo: `afinidad.json`

Ajusta los pesos del orden «Afines a lo que más se presta». Compruébalo
después con **Comparar con el histórico**:

```json
{"beta": {"thema": 0.9}, "ventana_anios": 4}
```

## Encabezados Thema: `thema_es.json`

Para ver el nombre de cada materia junto a su código («Novela gráfica · XAM»),
descarga de editeur.org la lista oficial en castellano (JSON o XML), guárdala
como `thema_es.json` en la carpeta de datos y reinicia Bildumargi.

!!! info "Licencia de la lista Thema"
    Si se redistribuye, debe ser el fichero oficial sin modificar.
