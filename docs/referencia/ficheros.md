# Ficheros y carpetas

## Carpeta de datos

En Windows, `%LOCALAPPDATA%\Bildumargi\datos`; con el zip, `datos/` junto al
programa; en el servidor, `/var/lib/bildumargi`.

```
configuracion.json       Toda la configuración (biblioteca, apariencia, DILVE…)
pautas.json              Referencia de fondo por habitante
marc_idiomas.db          Idioma de los ejemplares, extraído del catálogo MARC
dilve/novedades.db       Novedades de DILVE
dilve/fichas.db          Fichas de DILVE por ISBN (también las de las series)
dilve/credenciales.json  Cuenta de DILVE (si se escribió en Configuración)
dilve/cuota.json         Llamadas de hoy, bloqueos y avisos de DILVE
materias_secciones.json  (opcional) Materias -> secciones
afinidad.json            (opcional) Pesos del modelo de préstamo
thema_es.json            (opcional) Encabezados Thema de EDItEUR
bibliotecas/             El historial de la biblioteca
registro.txt             (Windows) Mensajes del programa, para resolver problemas
```

## Carpeta de la biblioteca

```
bibliotecas/biblioteca/
  sugerencias_autores.json Último cálculo de «Autores más prestados»
  cargas/20261006-165233/  Una carpeta por carga, con los listados
    resumen.json           Indicadores de la carga, altas y bajas
```

## Variables de entorno

| Variable | Para qué |
|---|---|
| `BILDUMARGI_DATOS` | Carpeta de datos. |
| `BILDUMARGI_CLAVE_ADMIN` | Clave de configuración. |
| `BILDUMARGI_DILVE_USUARIO`, `BILDUMARGI_DILVE_CLAVE` | Cuenta de DILVE. |

Con el zip, lo mismo puede ir en `config_local.py` (ver
[Ajustes avanzados](../administracion/ajustes-avanzados.md)).
