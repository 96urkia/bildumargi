# Requisitos y modos de uso

## Dos modos de uso

| | **En un ordenador** | **En un servidor de la red** |
|---|---|---|
| Para | Una biblioteca que lo usa sola | Todas las bibliotecas de la red |
| Acceso | Desde ese ordenador | Desde el navegador, por la intranet |
| Valoraciones entre bibliotecas | No (se quedan en ese equipo) | Sí |
| Historial y acceso con clave | Sí, para esa biblioteca | Sí, para todas |
| Instalación | Zip (Windows, Linux, macOS) | Paquete `.deb` o zip |

Bildumargi **no necesita estar publicado en internet** ni salida a internet
para analizar la colección. Solo se conecta fuera si se activa DILVE.

## Requisitos

- **Ordenador**: Python 3.10 o superior. El zip incluye todo lo demás.
- **Servidor**: Debian 12, Debian 13 o Ubuntu 24.04 para el paquete `.deb`.
  Cualquier otro sistema con Python 3.10+ sirve con el zip.
- **Navegador**: Edge, Chrome o Firefox actuales.
- **Recursos**: un servidor modesto basta. El catálogo colectivo puede ocupar
  de cientos de megas a unos pocos gigas según su tamaño (ver
  [Catálogo colectivo de la red](catalogo-red.md)).

## Una demo sin instalar nada

Para enseñar Bildumargi en un equipo donde no se puede instalar nada, se
puede preparar una demo que se abre con doble clic, como un PDF. Instrucciones
en el README del proyecto, apartado «Demostración sin instalar nada».
