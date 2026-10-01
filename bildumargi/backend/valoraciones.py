# -*- coding: utf-8 -*-
"""Valoraciones y comentarios de los títulos, escritos por las bibliotecas.

Vive en su propia base de datos, separada del catálogo a propósito: el `.db`
del catálogo se regenera con `conversor.py` cada vez que se actualiza el fondo
de la red, y si las valoraciones estuvieran ahí desaparecerían en cada
actualización.

Pensado para un despliegue central en la intranet: una sola instancia de
Bildumargi en el servidor de la biblioteca central, a la que acceden las demás
por el navegador. Cada biblioteca firma con su nombre, detectado a partir del
código de sucursal de sus propios listados, así que no hace falta ni registro
ni contraseñas ni guardar ningún dato personal.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone

PUNTUACION_MINIMA = 1
PUNTUACION_MAXIMA = 5
LIMITE_COMENTARIO = 2000
LIMITE_RESPUESTA = 1000

ESQUEMA = """
CREATE TABLE IF NOT EXISTS valoraciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_sistema   TEXT NOT NULL,
    biblioteca   TEXT NOT NULL,
    puntuacion   INTEGER,
    comentario   TEXT,
    creado       TEXT NOT NULL,
    actualizado  TEXT NOT NULL,
    -- Una valoración por biblioteca y título. Sin esta restricción, pulsar
    -- dos veces «Guardar» dejaría dos filas y la media saldría sesgada.
    UNIQUE (id_sistema, biblioteca)
);
CREATE INDEX IF NOT EXISTS idx_valoraciones_id_sistema ON valoraciones(id_sistema);
CREATE INDEX IF NOT EXISTS idx_valoraciones_biblioteca ON valoraciones(biblioteca);
-- Respuestas a un comentario: hilos cortos entre bibliotecas. Cuelgan del id
-- de la valoración, que se conserva aunque esta se reedite (el UPSERT no
-- cambia el id); si la valoración se borra, sus respuestas se borran con ella.
CREATE TABLE IF NOT EXISTS respuestas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_valoracion  INTEGER NOT NULL,
    biblioteca     TEXT NOT NULL,
    texto          TEXT NOT NULL,
    creado         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_respuestas_valoracion ON respuestas(id_valoracion);
CREATE INDEX IF NOT EXISTS idx_respuestas_creado ON respuestas(creado);
"""


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ErrorValoracion(Exception):
    pass


class Valoraciones:
    """Almacén de valoraciones sobre SQLite.

    Un único fichero y un candado propio: en una intranet con unas decenas de
    personas, las escrituras son esporádicas y SQLite sobra. El modo WAL
    permite que varias lecturas convivan con una escritura sin bloquearse.
    """

    def __init__(self, ruta, activo=True):
        self.ruta = ruta
        self.activo = activo
        self.conn = None
        self.error = None
        self._candado = threading.Lock()
        if activo:
            self._abrir()

    def _abrir(self):
        try:
            carpeta = os.path.dirname(os.path.abspath(self.ruta))
            os.makedirs(carpeta, exist_ok=True)
            self.conn = sqlite3.connect(self.ruta, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.executescript(ESQUEMA)
            self.conn.commit()
        except (sqlite3.Error, OSError) as exc:
            self.conn = None
            # Lo más habitual es que la carpeta no tenga permiso de escritura
            # para el usuario que ejecuta el servidor.
            self.error = (f"No se ha podido abrir el fichero de valoraciones "
                          f"«{self.ruta}»: {exc}")

    @property
    def disponible(self):
        return self.conn is not None

    def estado(self):
        return {"activo": self.activo, "disponible": self.disponible,
                "error": self.error, "ruta": self.ruta}

    # -- escritura ---------------------------------------------------------
    def guardar(self, id_sistema, biblioteca, puntuacion=None, comentario=None):
        """Crea o actualiza la valoración de una biblioteca sobre un título."""
        if not self.disponible:
            raise ErrorValoracion(self.error or "Las valoraciones están desactivadas.")
        id_sistema = str(id_sistema or "").strip()
        biblioteca = str(biblioteca or "").strip()
        if not id_sistema or not biblioteca:
            raise ErrorValoracion("Faltan el título o la biblioteca.")

        if puntuacion is not None:
            try:
                puntuacion = int(puntuacion)
            except (TypeError, ValueError):
                raise ErrorValoracion("La puntuación debe ser un número.")
            if not PUNTUACION_MINIMA <= puntuacion <= PUNTUACION_MAXIMA:
                raise ErrorValoracion(
                    f"La puntuación debe estar entre {PUNTUACION_MINIMA} y {PUNTUACION_MAXIMA}.")

        comentario = (comentario or "").strip()[:LIMITE_COMENTARIO] or None
        if puntuacion is None and comentario is None:
            raise ErrorValoracion("No hay nada que guardar: pon una puntuación o un comentario.")

        ahora = _ahora()
        with self._candado:
            self.conn.execute("""
                INSERT INTO valoraciones (id_sistema, biblioteca, puntuacion, comentario,
                                          creado, actualizado)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(id_sistema, biblioteca) DO UPDATE SET
                    puntuacion = excluded.puntuacion,
                    comentario = excluded.comentario,
                    actualizado = excluded.actualizado
            """, (id_sistema, biblioteca, puntuacion, comentario, ahora, ahora))
            self.conn.commit()
        return self.de_titulo(id_sistema)

    def borrar(self, id_sistema, biblioteca):
        """Una biblioteca solo puede borrar lo suyo: la condición del WHERE es
        la única autorización que hay, y es suficiente en una intranet."""
        if not self.disponible:
            raise ErrorValoracion(self.error or "Las valoraciones están desactivadas.")
        with self._candado:
            self.conn.execute("""
                DELETE FROM respuestas WHERE id_valoracion IN (
                    SELECT id FROM valoraciones WHERE id_sistema = ? AND biblioteca = ?)
            """, (str(id_sistema), str(biblioteca)))
            self.conn.execute("DELETE FROM valoraciones WHERE id_sistema = ? AND biblioteca = ?",
                              (str(id_sistema), str(biblioteca)))
            self.conn.commit()
        return self.de_titulo(id_sistema)

    def responder(self, id_valoracion, biblioteca, texto):
        """Añade una respuesta a un comentario. Devuelve el id_sistema del
        título, para que quien llama pueda devolver el hilo actualizado."""
        if not self.disponible:
            raise ErrorValoracion(self.error or "Las valoraciones están desactivadas.")
        texto = (texto or "").strip()[:LIMITE_RESPUESTA]
        biblioteca = str(biblioteca or "").strip()
        if not texto or not biblioteca:
            raise ErrorValoracion("La respuesta está vacía.")
        fila = self.conn.execute("SELECT id_sistema, comentario FROM valoraciones WHERE id = ?",
                                 (int(id_valoracion),)).fetchone()
        if fila is None or not (fila["comentario"] or "").strip():
            raise ErrorValoracion("Ese comentario ya no existe.")
        with self._candado:
            self.conn.execute("INSERT INTO respuestas (id_valoracion, biblioteca, texto, creado) VALUES (?,?,?,?)",
                              (int(id_valoracion), biblioteca, texto, _ahora()))
            self.conn.commit()
        return fila["id_sistema"]

    def borrar_respuesta(self, id_respuesta, biblioteca):
        """Cada biblioteca borra solo sus respuestas (misma regla que arriba)."""
        if not self.disponible:
            raise ErrorValoracion(self.error or "Las valoraciones están desactivadas.")
        fila = self.conn.execute("""
            SELECT v.id_sistema FROM respuestas r JOIN valoraciones v ON v.id = r.id_valoracion
            WHERE r.id = ? AND r.biblioteca = ?""", (int(id_respuesta), str(biblioteca))).fetchone()
        if fila is None:
            raise ErrorValoracion("No se encuentra esa respuesta, o no es de tu biblioteca.")
        with self._candado:
            self.conn.execute("DELETE FROM respuestas WHERE id = ? AND biblioteca = ?",
                              (int(id_respuesta), str(biblioteca)))
            self.conn.commit()
        return fila["id_sistema"]

    # -- lectura -----------------------------------------------------------
    def de_titulo(self, id_sistema):
        """Valoraciones de un título, con su media y su recuento."""
        if not self.disponible:
            return {"media": None, "n_puntuaciones": 0, "n_comentarios": 0, "valoraciones": []}
        filas = self.conn.execute("""
            SELECT id, biblioteca, puntuacion, comentario, creado, actualizado
            FROM valoraciones WHERE id_sistema = ?
            ORDER BY actualizado DESC
        """, (str(id_sistema),)).fetchall()
        valoraciones = [dict(f) for f in filas]
        ids = [v["id"] for v in valoraciones]
        hilos = {}
        if ids:
            marcas = ",".join("?" * len(ids))
            for r in self.conn.execute(f"""
                SELECT id, id_valoracion, biblioteca, texto, creado FROM respuestas
                WHERE id_valoracion IN ({marcas}) ORDER BY creado""", ids).fetchall():
                hilos.setdefault(r["id_valoracion"], []).append(dict(r))
        for v in valoraciones:
            v["respuestas"] = hilos.get(v["id"], [])

        puntuaciones = [v["puntuacion"] for v in valoraciones if v["puntuacion"] is not None]
        return {
            "media": round(sum(puntuaciones) / len(puntuaciones), 2) if puntuaciones else None,
            "n_puntuaciones": len(puntuaciones),
            "n_comentarios": sum(1 for v in valoraciones if v["comentario"]),
            "valoraciones": valoraciones,
        }

    def mia(self, id_sistema, biblioteca):
        if not self.disponible:
            return None
        fila = self.conn.execute("""
            SELECT puntuacion, comentario, actualizado FROM valoraciones
            WHERE id_sistema = ? AND biblioteca = ?
        """, (str(id_sistema), str(biblioteca))).fetchone()
        return dict(fila) if fila else None

    def resumen_de(self, ids_sistema):
        """Media y recuento de varios títulos a la vez.

        Se consulta en bloque, no título a título: una tabla de cincuenta
        recomendaciones haría cincuenta viajes a la base para pintar una
        columna."""
        resumen = {}
        if not self.disponible or not ids_sistema:
            return resumen
        lista = [str(i) for i in ids_sistema if i]
        for i in range(0, len(lista), 800):
            bloque = lista[i:i + 800]
            marcas = ",".join("?" * len(bloque))
            filas = self.conn.execute(f"""
                SELECT id_sistema,
                       AVG(puntuacion) AS media,
                       COUNT(puntuacion) AS n_puntuaciones,
                       SUM(CASE WHEN comentario IS NOT NULL AND TRIM(comentario) <> ''
                                THEN 1 ELSE 0 END) AS n_comentarios
                FROM valoraciones WHERE id_sistema IN ({marcas})
                GROUP BY id_sistema
            """, bloque).fetchall()
            for f in filas:
                resumen[str(f["id_sistema"])] = {
                    "media": round(f["media"], 2) if f["media"] is not None else None,
                    "n_puntuaciones": f["n_puntuaciones"],
                    "n_comentarios": f["n_comentarios"] or 0,
                }
        return resumen

    def recientes(self, limite=30):
        """Últimas valoraciones con comentario, para una vista de novedades."""
        if not self.disponible:
            return []
        filas = self.conn.execute("""
            SELECT id_sistema, biblioteca, puntuacion, comentario, actualizado
            FROM valoraciones
            WHERE comentario IS NOT NULL AND TRIM(comentario) <> ''
            ORDER BY actualizado DESC LIMIT ?
        """, (int(limite),)).fetchall()
        return [dict(f) for f in filas]

    def estadisticas(self, desde=None):
        """Cifras de participación. `desde` (ISO) cuenta además la actividad
        reciente: valoraciones escritas o reeditadas y respuestas."""
        vacio = {"titulos": 0, "valoraciones": 0, "comentarios": 0, "respuestas": 0,
                 "bibliotecas": 0, "actividad_reciente": 0}
        if not self.disponible:
            return vacio
        fila = dict(self.conn.execute("""
            SELECT COUNT(DISTINCT id_sistema) AS titulos, COUNT(*) AS valoraciones,
                   SUM(CASE WHEN comentario IS NOT NULL AND TRIM(comentario) <> '' THEN 1 ELSE 0 END) AS comentarios
            FROM valoraciones""").fetchone())
        fila["comentarios"] = fila["comentarios"] or 0
        fila["respuestas"] = self.conn.execute("SELECT COUNT(*) FROM respuestas").fetchone()[0]
        fila["bibliotecas"] = self.conn.execute("""
            SELECT COUNT(*) FROM (SELECT biblioteca FROM valoraciones
                                  UNION SELECT biblioteca FROM respuestas)""").fetchone()[0]
        fila["actividad_reciente"] = 0
        if desde:
            fila["actividad_reciente"] = (
                self.conn.execute("SELECT COUNT(*) FROM valoraciones WHERE actualizado >= ?", (desde,)).fetchone()[0]
                + self.conn.execute("SELECT COUNT(*) FROM respuestas WHERE creado >= ?", (desde,)).fetchone()[0])
        return fila

    def actividad(self, limite=60, biblioteca=None, filtro="todo"):
        """Valoraciones y respuestas mezcladas, de la más reciente a la más
        antigua. `filtro`: 'todo', 'a_mi' (respuestas a comentarios de
        `biblioteca`) o 'mia' (lo que ha escrito `biblioteca`)."""
        if not self.disponible:
            return []
        valoraciones = """
            SELECT 'valoracion' AS tipo, v.id AS id, v.id AS id_valoracion, v.id_sistema, v.biblioteca,
                   v.puntuacion, v.comentario AS texto, v.actualizado AS fecha, NULL AS destino
            FROM valoraciones v"""
        respuestas = """
            SELECT 'respuesta' AS tipo, r.id AS id, r.id_valoracion, v.id_sistema, r.biblioteca,
                   NULL AS puntuacion, r.texto, r.creado AS fecha, v.biblioteca AS destino
            FROM respuestas r JOIN valoraciones v ON v.id = r.id_valoracion"""
        params = []
        if filtro == "a_mi" and biblioteca:
            sql = respuestas + " WHERE v.biblioteca = ? AND r.biblioteca <> ?"
            params = [biblioteca, biblioteca]
        elif filtro == "mia" and biblioteca:
            sql = f"{valoraciones} WHERE v.biblioteca = ? UNION ALL {respuestas} WHERE r.biblioteca = ?"
            params = [biblioteca, biblioteca]
        else:
            sql = f"{valoraciones} UNION ALL {respuestas}"
        filas = self.conn.execute(f"SELECT * FROM ({sql}) ORDER BY fecha DESC LIMIT ?",
                                  params + [int(limite)]).fetchall()
        return [dict(f) for f in filas]

    def mejor_valorados(self, minimo=2, limite=15):
        """Títulos con al menos `minimo` puntuaciones, por media y luego por
        número de puntuaciones: una sola nota de 5 no pasa por delante de
        cuatro notas de 4,5."""
        if not self.disponible:
            return []
        return [dict(f) for f in self.conn.execute("""
            SELECT id_sistema, ROUND(AVG(puntuacion), 2) AS media, COUNT(puntuacion) AS n_puntuaciones
            FROM valoraciones WHERE puntuacion IS NOT NULL
            GROUP BY id_sistema HAVING COUNT(puntuacion) >= ?
            ORDER BY media DESC, n_puntuaciones DESC LIMIT ?""", (int(minimo), int(limite))).fetchall()]

    def mas_comentados(self, limite=15):
        """Títulos con más conversación: comentarios más respuestas."""
        if not self.disponible:
            return []
        return [dict(f) for f in self.conn.execute("""
            SELECT v.id_sistema,
                   SUM(CASE WHEN v.comentario IS NOT NULL AND TRIM(v.comentario) <> '' THEN 1 ELSE 0 END) AS comentarios,
                   (SELECT COUNT(*) FROM respuestas r JOIN valoraciones v2 ON v2.id = r.id_valoracion
                    WHERE v2.id_sistema = v.id_sistema) AS respuestas,
                   MAX(v.actualizado) AS ultima
            FROM valoraciones v GROUP BY v.id_sistema
            HAVING comentarios > 0
            ORDER BY (comentarios + respuestas) DESC, ultima DESC LIMIT ?""", (int(limite),)).fetchall()]
