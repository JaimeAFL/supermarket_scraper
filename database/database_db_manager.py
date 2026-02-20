"""database/database_db_manager.py - Gestor de la base de datos SQLite."""

import sqlite3
import logging
import os
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "database", "supermercados.db")
)


class DatabaseManager:
    """Gestiona todas las operaciones con la BD SQLite del proyecto.

    Esquema real de la BD:
      productos : id, id_externo, nombre, supermercado, categoria, formato,
                  url, url_imagen, fecha_creacion, fecha_actualizacion
      precios   : id, producto_id, precio, precio_por_unidad, fecha_captura
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.environ.get("SUPERMARKET_DB_PATH", _DEFAULT_DB)
        self.db_path = os.path.abspath(db_path)
        self._conn = None
        self._conectar()

    # ── Conexión ──────────────────────────────────────────────────────────────
    def _conectar(self):
        try:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            logger.debug(f"Conexión abierta: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error al conectar con la BD: {e}")
            raise

    def _cursor(self):
        """Cursor con reconexión automática (necesario en Streamlit Cloud)."""
        try:
            self._conn.execute("SELECT 1")
        except Exception:
            logger.warning("Reconectando a la BD...")
            self._conectar()
        return self._conn.cursor()

    def cerrar(self):
        if self._conn:
            self._conn.close()
            logger.debug("Conexión cerrada.")

    # ── Guardar productos (llamado por el scraper) ────────────────────────────
    def guardar_productos(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return {
                "nuevos": 0, "productos_nuevos": 0,
                "actualizados": 0, "productos_actualizados": 0,
                "precios": 0, "precios_registrados": 0,
            }

        cur    = self._cursor()
        nuevos = actualizados = precios_ok = 0
        ts     = datetime.now().isoformat()

        for _, row in df.iterrows():
            try:
                id_externo   = str(row.get("Id") or "").strip()
                nombre       = str(row.get("Nombre") or "").strip()
                supermercado = str(row.get("Supermercado") or "").strip()

                if not id_externo or not nombre or not supermercado:
                    continue

                try:
                    precio = float(row.get("Precio", 0))
                except (ValueError, TypeError):
                    continue
                if precio <= 0:
                    continue

                precio_por_unidad = str(row.get("Precio_unidad") or "").strip()
                categoria         = str(row.get("Categoria") or "").strip()
                formato           = str(row.get("Formato") or "").strip()
                url               = str(row.get("URL") or "").strip()
                url_imagen        = str(row.get("URL_imagen") or "").strip()

                cur.execute("""
                    INSERT INTO productos
                        (id_externo, nombre, supermercado, categoria, formato,
                         url, url_imagen, fecha_creacion, fecha_actualizacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id_externo, supermercado) DO UPDATE SET
                        nombre              = excluded.nombre,
                        categoria           = excluded.categoria,
                        formato             = excluded.formato,
                        url                 = excluded.url,
                        url_imagen          = excluded.url_imagen,
                        fecha_actualizacion = excluded.fecha_actualizacion
                """, (id_externo, nombre, supermercado, categoria, formato,
                      url, url_imagen, ts, ts))

                nuevos += cur.rowcount > 0

                cur.execute(
                    "SELECT id FROM productos WHERE id_externo = ? AND supermercado = ?",
                    (id_externo, supermercado)
                )
                prod_id = cur.fetchone()[0]

                fecha_hoy = ts[:10]
                cur.execute(
                    "SELECT id FROM precios WHERE producto_id = ? AND fecha_captura LIKE ?",
                    (prod_id, f"{fecha_hoy}%")
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO precios (producto_id, precio, precio_por_unidad, fecha_captura) VALUES (?, ?, ?, ?)",
                        (prod_id, precio, precio_por_unidad, ts)
                    )
                    precios_ok += 1
                else:
                    actualizados += 1

            except Exception as e:
                logger.debug(f"Error guardando producto: {e}")

        self._conn.commit()
        # FIX BUG 4: Incluir TODAS las claves que usan main.py y run_scraper.py
        result = {
            "nuevos": nuevos,
            "productos_nuevos": nuevos,
            "actualizados": actualizados,
            "productos_actualizados": actualizados,
            "precios": precios_ok,
            "precios_registrados": precios_ok,
        }
        logger.info(
            f"Guardado: {nuevos} nuevos, {actualizados} actualizados, "
            f"{precios_ok} precios registrados."
        )
        return result

    # ── Estadísticas ──────────────────────────────────────────────────────────
    def obtener_estadisticas(self) -> dict:
        cur = self._cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM productos")
            total_prod = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM precios")
            total_precios = cur.fetchone()[0]

            cur.execute("SELECT COUNT(DISTINCT supermercado) FROM productos")
            total_supers = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM equivalencias")
            total_equiv = cur.fetchone()[0]

            cur.execute(
                "SELECT supermercado, COUNT(*) FROM productos "
                "GROUP BY supermercado ORDER BY COUNT(*) DESC"
            )
            por_super = dict(cur.fetchall())

            cur.execute(
                "SELECT MIN(fecha_captura), MAX(fecha_captura) FROM precios"
            )
            fechas = cur.fetchone()

            return {
                "total_productos":            total_prod,
                "total_registros_precios":    total_precios,
                "total_supermercados":        total_supers,
                "total_equivalencias":        total_equiv,
                "productos_por_supermercado": por_super,
                "primera_captura":            fechas[0] if fechas else None,
                "ultima_captura":             fechas[1] if fechas else None,
            }
        except Exception as e:
            logger.error(f"Error en obtener_estadisticas: {e}")
            return {
                "total_productos": 0, "total_registros_precios": 0,
                "total_supermercados": 0, "total_equivalencias": 0,
                "productos_por_supermercado": {},
                "primera_captura": None, "ultima_captura": None,
            }

    # ── Productos con precio actual ───────────────────────────────────────────
    def obtener_productos_con_precio_actual(
        self, supermercado: str = None
    ) -> pd.DataFrame:
        cur = self._cursor()
        try:
            sql = """
                SELECT
                    p.id,
                    p.id_externo        AS retailer_id,
                    p.nombre,
                    p.supermercado,
                    p.categoria,
                    p.formato,
                    p.url,
                    p.url_imagen,
                    pr.precio,
                    pr.precio_por_unidad AS precio_unidad,
                    pr.fecha_captura
                FROM productos p
                JOIN precios pr ON pr.id = (
                    SELECT id FROM precios
                    WHERE producto_id = p.id
                    ORDER BY fecha_captura DESC
                    LIMIT 1
                )
            """
            params = ()
            if supermercado:
                sql += " WHERE p.supermercado = ?"
                params = (supermercado,)

            cur.execute(sql, params)
            rows = cur.fetchall()
            return (
                pd.DataFrame(rows, columns=[d[0] for d in cur.description])
                if rows else pd.DataFrame()
            )
        except Exception as e:
            logger.error(
                f"Error en obtener_productos_con_precio_actual: {e}"
            )
            return pd.DataFrame()

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    def buscar_productos(
        self,
        nombre: str = None,
        supermercado: str = None,
        limite: int = 20,
    ) -> pd.DataFrame:
        """Busca productos distribuyendo resultados entre supermercados.

        FIX BUG 3: La versión anterior hacía ``SELECT … LIMIT 20`` sin
        ``ORDER BY``, de modo que siempre devolvía solo Mercadona (los
        primeros IDs).  Ahora usa ``ROW_NUMBER() OVER (PARTITION BY
        supermercado)`` para devolver hasta ``limite_por_super`` resultados
        de *cada* supermercado, garantizando diversidad.
        """
        cur = self._cursor()
        try:
            # Si se filtra por supermercado, simplemente devolver por nombre
            if supermercado:
                sql = """
                    SELECT
                        p.id,
                        p.id_externo AS retailer_id,
                        p.nombre,
                        p.supermercado,
                        p.categoria,
                        p.formato,
                        (
                            SELECT precio FROM precios
                            WHERE producto_id = p.id
                            ORDER BY fecha_captura DESC LIMIT 1
                        ) AS precio
                    FROM productos p
                    WHERE p.supermercado = ?
                """
                params = [supermercado]
                if nombre:
                    sql += " AND p.nombre LIKE ?"
                    params.append(f"%{nombre}%")
                sql += f" ORDER BY p.nombre LIMIT {int(limite)}"
                cur.execute(sql, params)
            else:
                # Sin filtro de super → distribuir resultados equitativamente
                limite_por_super = max(4, int(limite) // 5)
                sql = """
                    SELECT id, retailer_id, nombre, supermercado,
                           categoria, formato, precio
                    FROM (
                        SELECT
                            p.id,
                            p.id_externo AS retailer_id,
                            p.nombre,
                            p.supermercado,
                            p.categoria,
                            p.formato,
                            (
                                SELECT precio FROM precios
                                WHERE producto_id = p.id
                                ORDER BY fecha_captura DESC LIMIT 1
                            ) AS precio,
                            ROW_NUMBER() OVER (
                                PARTITION BY p.supermercado
                                ORDER BY p.nombre
                            ) AS rn
                        FROM productos p
                        WHERE 1=1
                """
                params = []
                if nombre:
                    sql += " AND p.nombre LIKE ?"
                    params.append(f"%{nombre}%")

                sql += f"""
                    ) sub
                    WHERE sub.rn <= {limite_por_super}
                    ORDER BY sub.nombre
                """
                cur.execute(sql, params)

            rows = cur.fetchall()
            return (
                pd.DataFrame(
                    rows, columns=[d[0] for d in cur.description]
                )
                if rows else pd.DataFrame()
            )
        except Exception as e:
            logger.error(f"Error en buscar_productos: {e}")
            return pd.DataFrame()

    # ── Histórico de precios ──────────────────────────────────────────────────
    def obtener_historico_precios(self, producto_id: int) -> pd.DataFrame:
        """FIX BUG 1: Devuelve ``fecha_captura`` (no ``fecha``) para que
        coincida con lo que esperan ``charts.py`` y las páginas del dashboard.
        """
        cur = self._cursor()
        try:
            cur.execute("""
                SELECT
                    fecha_captura,
                    precio,
                    precio_por_unidad AS precio_unidad
                FROM precios
                WHERE producto_id = ?
                ORDER BY fecha_captura ASC
            """, (producto_id,))
            rows = cur.fetchall()
            return (
                pd.DataFrame(
                    rows,
                    columns=["fecha_captura", "precio", "precio_unidad"],
                )
                if rows else pd.DataFrame()
            )
        except Exception as e:
            logger.error(f"Error en obtener_historico_precios: {e}")
            return pd.DataFrame()

    # ── Equivalencias ─────────────────────────────────────────────────────────
    def listar_grupos_equivalencia(self) -> list:
        cur = self._cursor()
        try:
            cur.execute(
                "SELECT DISTINCT nombre_comun FROM equivalencias "
                "ORDER BY nombre_comun"
            )
            return [r[0] for r in cur.fetchall()]
        except Exception:
            return []

    def obtener_equivalencias(self, nombre_comun: str) -> pd.DataFrame:
        cur = self._cursor()
        try:
            cur.execute(
                "SELECT * FROM equivalencias WHERE nombre_comun = ?",
                (nombre_comun,),
            )
            row = cur.fetchone()
            if not row:
                return pd.DataFrame()

            ids_por_super = {
                "Mercadona": row["producto_mercadona_id"],
                "Carrefour": row["producto_carrefour_id"],
                "Dia":       row["producto_dia_id"],
                "Alcampo":   row["producto_alcampo_id"],
                "Eroski":    row["producto_eroski_id"],
            }

            resultados = []
            for super_name, id_ext in ids_por_super.items():
                if not id_ext:
                    continue
                cur.execute("""
                    SELECT p.id, p.nombre, p.supermercado, p.formato, pr.precio
                    FROM productos p
                    LEFT JOIN precios pr ON pr.id = (
                        SELECT id FROM precios
                        WHERE producto_id = p.id
                        ORDER BY fecha_captura DESC
                        LIMIT 1
                    )
                    WHERE p.id_externo = ? AND p.supermercado = ?
                """, (id_ext, super_name))
                r = cur.fetchone()
                if r:
                    resultados.append(dict(r))

            return (
                pd.DataFrame(resultados) if resultados
                else pd.DataFrame()
            )
        except Exception as e:
            logger.error(f"Error en obtener_equivalencias: {e}")
            return pd.DataFrame()

    def obtener_historico_equivalencia(
        self, nombre_comun: str
    ) -> pd.DataFrame:
        df = self.obtener_equivalencias(nombre_comun)
        if df.empty:
            return pd.DataFrame()
        historicos = []
        for _, row in df.iterrows():
            hist = self.obtener_historico_precios(row['id'])
            if not hist.empty:
                hist['supermercado'] = row['supermercado']
                hist['nombre']       = row['nombre']
                historicos.append(hist)
        return (
            pd.concat(historicos, ignore_index=True)
            if historicos else pd.DataFrame()
        )

    def guardar_equivalencia(
        self, nombre_comun: str, ids_por_super: dict
    ):
        cur = self._cursor()
        cur.execute("""
            INSERT INTO equivalencias
                (nombre_comun, producto_mercadona_id, producto_carrefour_id,
                 producto_dia_id, producto_alcampo_id, producto_eroski_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """, (
            nombre_comun,
            ids_por_super.get("Mercadona"),
            ids_por_super.get("Carrefour"),
            ids_por_super.get("Dia"),
            ids_por_super.get("Alcampo"),
            ids_por_super.get("Eroski"),
        ))
        self._conn.commit()

    def crear_equivalencia(
        self, nombre_comun: str, lista_producto_ids: list
    ):
        """FIX BUG 2: Crea una equivalencia a partir de IDs internos.

        ``product_matcher.py`` trabaja con IDs internos (enteros), pero
        la tabla ``equivalencias`` almacena ``id_externo`` (texto) por
        supermercado.  Este método hace la conversión.
        """
        cur = self._cursor()
        ids_por_super = {}

        for pid in lista_producto_ids:
            cur.execute(
                "SELECT id_externo, supermercado FROM productos WHERE id = ?",
                (pid,),
            )
            row = cur.fetchone()
            if row:
                ids_por_super[row["supermercado"]] = row["id_externo"]

        if ids_por_super:
            self.guardar_equivalencia(nombre_comun, ids_por_super)

    # ── Favoritos ─────────────────────────────────────────────────────────────
    def agregar_favorito(self, producto_id: int):
        cur = self._cursor()
        try:
            cur.execute(
                "INSERT OR IGNORE INTO favoritos (producto_id) VALUES (?)",
                (producto_id,),
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Error añadiendo favorito: {e}")

    def eliminar_favorito(self, producto_id: int):
        cur = self._cursor()
        try:
            cur.execute(
                "DELETE FROM favoritos WHERE producto_id = ?",
                (producto_id,),
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Error eliminando favorito: {e}")

    def obtener_favoritos(self) -> pd.DataFrame:
        cur = self._cursor()
        try:
            cur.execute("""
                SELECT p.id, p.nombre, p.supermercado, p.formato,
                       pr.precio, f.fecha_agregado
                FROM favoritos f
                JOIN productos p ON p.id = f.producto_id
                LEFT JOIN precios pr ON pr.id = (
                    SELECT id FROM precios
                    WHERE producto_id = p.id
                    ORDER BY fecha_captura DESC
                    LIMIT 1
                )
                ORDER BY f.fecha_agregado DESC
            """)
            rows = cur.fetchall()
            return (
                pd.DataFrame(
                    rows, columns=[d[0] for d in cur.description]
                )
                if rows else pd.DataFrame()
            )
        except Exception as e:
            logger.error(f"Error en obtener_favoritos: {e}")
            return pd.DataFrame()
