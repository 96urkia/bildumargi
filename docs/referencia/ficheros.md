# Ficheros y carpetas

## Carpeta de datos

En el zip, `datos/` junto al programa; en el servidor, `/var/lib/bildumargi`.

```
bibliotecas.xlsx         Directorio de bibliotecas (con claves)
pautas.json              Referencia de fondo por habitante
configuracion_red.json   Configuración de la red (se crea al guardar)
valoraciones.db          Valoraciones y comentarios (¡copia de seguridad!)
base_red.db              Catálogo colectivo (generado con conversor.py)
dilve/novedades.db       Novedades de DILVE
dilve/fichas.db          Fichas de DILVE por ISBN
materias_secciones.json  (opcional) Materias -> secciones
afinidad.json            (opcional) Pesos del modelo de préstamo
thema_es.json            (opcional) Encabezados Thema de EDItEUR
bibliotecas/             Una carpeta por biblioteca
```

## Carpeta de cada biblioteca

```
bibliotecas/biblioteca-de-monteagudo/
  biblioteca.txt           Nombre de la biblioteca
  preferencias.json        Su configuración
  signaturas.json          Su tabla de secciones por signatura (si la tiene)
  cargas/20260919-093012/  Una carpeta por carga, con los listados
    resumen.json           Indicadores de la carga, para Seguimiento
```

## Variables de entorno

| Variable | Para qué |
|---|---|
| `BILDUMARGI_DATOS` | Carpeta de datos. |
| `BILDUMARGI_CACHE` | Carpeta de caché. |
| `BILDUMARGI_DB_URL` | Dirección de la base del catálogo de la red. |
| `BILDUMARGI_CLAVE_ADMIN` | Clave de administración. |
| `BILDUMARGI_DILVE_USUARIO`, `BILDUMARGI_DILVE_CLAVE` | Credenciales de DILVE. |
