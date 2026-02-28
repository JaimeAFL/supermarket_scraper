"""database/database_db_manager.py - Gestor de la BD con normalización integrada."""

import sqlite3
import logging
import os
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "database", "supermercados.db")
)

# Importar normalizador (graceful fallback)
try:
    from matching.normalizer import normalizar_producto
    _NORMALIZER_OK = True
except ImportError:
    _NORMALIZER_OK = False
    logger.warning("matching.normalizer no disponible — normalización desactivada.")


class DatabaseManager:

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.environ.get("SUPERMARKET_DB_PATH", _DEFAULT_DB)
        self.db_path = os.path.abspath(db_path)
        self._conn = None
        self._conectar()

    # ── Conexión ──────────────────────────────────────────────────────
    def _conectar(self):
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def _cursor(self):
        try:
            self._conn.execute("SELECT 1")
        except Exception:
            self._conectar()
        return self._conn.cursor()

    def cerrar(self):
        if self._conn:
            self._conn.close()

    # ── Guardar productos (con normalización) ─────────────────────────
    def guardar_productos(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return {"nuevos": 0, "productos_nuevos": 0,
                    "actualizados": 0, "productos_actualizados": 0,
                    "precios": 0, "precios_registrados": 0}

        cur = self._cursor()
        nuevos = actualizados = precios_ok = 0
        ts = datetime.now().isoformat()

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
                categoria  = str(row.get("Categoria") or "").strip()
                formato    = str(row.get("Formato") or "").strip()
                url        = str(row.get("URL") or "").strip()
                url_imagen = str(row.get("URL_imagen") or "").strip()

                # ── Normalización ──
                if _NORMALIZER_OK:
                    norm = normalizar_producto(nombre, supermercado)
                    tipo_producto         = norm["tipo_producto"]
                    marca                 = norm["marca"]
                    nombre_normalizado    = norm["nombre_normalizado"]
                    categoria_normalizada = norm["categoria_normalizada"]
                else:
                    tipo_producto = nombre
                    marca = ""
                    nombre_normalizado = nombre.lower().strip()
                    categoria_normalizada = ""

                cur.execute("""
                    INSERT INTO productos
                        (id_externo, nombre, supermercado, categoria, formato,
                         url, url_imagen, fecha_creacion, fecha_actualizacion,
                         tipo_producto, marca, nombre_normalizado,
                         categoria_normalizada)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id_externo, supermercado) DO UPDATE SET
                        nombre                = excluded.nombre,
                        categoria             = excluded.categoria,
                        formato               = excluded.formato,
                        url                   = excluded.url,
                        url_imagen            = excluded.url_imagen,
                        fecha_actualizacion   = excluded.fecha_actualizacion,
                        tipo_producto         = excluded.tipo_producto,
                        marca                 = excluded.marca,
                        nombre_normalizado    = excluded.nombre_normalizado,
                        categoria_normalizada = excluded.categoria_normalizada
                """, (id_externo, nombre, supermercado, categoria, formato,
                      url, url_imagen, ts, ts,
                      tipo_producto, marca, nombre_normalizado,
                      categoria_normalizada))
                nuevos += cur.rowcount > 0

                cur.execute(
                    "SELECT id FROM productos "
                    "WHERE id_externo=? AND supermercado=?",
                    (id_externo, supermercado),
                )
                prod_id = cur.fetchone()[0]

                fecha_hoy = ts[:10]
                cur.execute(
                    "SELECT id FROM precios "
                    "WHERE producto_id=? AND fecha_captura LIKE ?",
                    (prod_id, f"{fecha_hoy}%"),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO precios "
                        "(producto_id, precio, precio_por_unidad, fecha_captura)"
                        " VALUES (?,?,?,?)",
                        (prod_id, precio, precio_por_unidad, ts),
                    )
                    precios_ok += 1
                else:
                    actualizados += 1
            except Exception as e:
                logger.debug("Error guardando producto: %s", e)

        self._conn.commit()
        return {"nuevos": nuevos, "productos_nuevos": nuevos,
                "actualizados": actualizados, "productos_actualizados": actualizados,
                "precios": precios_ok, "precios_registrados": precios_ok}

    # ── Estadísticas ──────────────────────────────────────────────────
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
            cur.execute(
                "SELECT COUNT(DISTINCT substr(fecha_captura,1,10)) FROM precios"
            )
            dias_datos = cur.fetchone()[0]
            # Categorías normalizadas
            cur.execute("""
                SELECT categoria_normalizada, COUNT(*) FROM productos
                WHERE categoria_normalizada != ''
                GROUP BY categoria_normalizada ORDER BY COUNT(*) DESC
            """)
            por_cat = dict(cur.fetchall())
            return {
                "total_productos": total_prod,
                "total_registros_precios": total_precios,
                "total_supermercados": total_supers,
                "total_equivalencias": total_equiv,
                "productos_por_supermercado": por_super,
                "productos_por_categoria": por_cat,
                "primera_captura": fechas[0] if fechas else None,
                "ultima_captura": fechas[1] if fechas else None,
                "dias_con_datos": dias_datos,
            }
        except Exception as e:
            logger.error("Error en obtener_estadisticas: %s", e)
            return {"total_productos": 0, "total_registros_precios": 0,
                    "total_supermercados": 0, "total_equivalencias": 0,
                    "productos_por_supermercado": {},
                    "productos_por_categoria": {},
                    "primera_captura": None, "ultima_captura": None,
                    "dias_con_datos": 0}

    # ── Productos con precio actual ───────────────────────────────────
    def obtener_productos_con_precio_actual(self, supermercado=None):
        cur = self._cursor()
        try:
            sql = """
                SELECT p.id, p.id_externo AS retailer_id,
                       p.nombre, p.supermercado, p.categoria, p.formato,
                       p.url, p.url_imagen,
                       p.tipo_producto, p.marca,
                       p.nombre_normalizado, p.categoria_normalizada,
                       pr.precio, pr.precio_por_unidad AS precio_unidad,
                       pr.fecha_captura
                FROM productos p
                JOIN precios pr ON pr.id = (
                    SELECT id FROM precios WHERE producto_id=p.id
                    ORDER BY fecha_captura DESC LIMIT 1
                )
            """
            params = ()
            if supermercado:
                sql += " WHERE p.supermercado=?"
                params = (supermercado,)
            cur.execute(sql, params)
            rows = cur.fetchall()
            return (pd.DataFrame(rows, columns=[d[0] for d in cur.description])
                    if rows else pd.DataFrame())
        except Exception as e:
            logger.error("obtener_productos_con_precio_actual: %s", e)
            return pd.DataFrame()

    # ── Búsqueda inteligente (3 prioridades: tipo → marca → nombre) ──
    def buscar_productos(self, nombre=None, supermercado=None, limite=25):
        """Búsqueda inteligente con 3 niveles de prioridad:
        1. tipo_producto: primera palabra empieza, resto contenidas
        2. marca: todas las palabras contenidas en la marca
        3. nombre: todas las palabras contenidas (fallback)

        Buscar 'leche' → lácteos primero (tipo), no café con leche.
        Buscar 'coca cola' → encuentra por marca cuando tipo es 'refresco'.
        Distribuye resultados entre todos los supermercados.
        """
        cur = self._cursor()
        try:
            limite_por_super = max(5, int(limite) // 5)
            palabras = nombre.strip().lower().split() if nombre else []

            if not palabras:
                return pd.DataFrame()

            # Prioridad 1: tipo — primera palabra empieza, resto contenidas
            tipo_conds = ["p.nombre_normalizado LIKE ?"]
            params_tipo = [f"{palabras[0]}%"]
            for p in palabras[1:]:
                tipo_conds.append("p.nombre_normalizado LIKE ?")
                params_tipo.append(f"%{p}%")
            tipo_sql = " AND ".join(tipo_conds)

            # Prioridad 2: marca
            marca_conds = ["LOWER(p.marca) LIKE ?" for _ in palabras]
            params_marca = [f"%{p}%" for p in palabras]
            marca_sql = " AND ".join(marca_conds)

            # Prioridad 3: nombre completo (fallback)
            nombre_conds = ["p.nombre LIKE ?" for _ in palabras]
            params_nombre = [f"%{p}%" for p in palabras]
            nombre_sql = " AND ".join(nombre_conds)

            super_filter = ""
            super_params = []
            if supermercado:
                super_filter = " AND p.supermercado=?"
                super_params = [supermercado]

            sql = f"""
                SELECT id, retailer_id, nombre, supermercado, categoria,
                       formato, precio, tipo_producto, marca,
                       nombre_normalizado, categoria_normalizada, prioridad
                FROM (
                    SELECT p.id, p.id_externo AS retailer_id,
                           p.nombre, p.supermercado, p.categoria, p.formato,
                           (SELECT precio FROM precios WHERE producto_id=p.id
                            ORDER BY fecha_captura DESC LIMIT 1) AS precio,
                           p.tipo_producto, p.marca,
                           p.nombre_normalizado, p.categoria_normalizada,
                           1 AS prioridad,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.supermercado
                               ORDER BY p.nombre_normalizado
                           ) AS rn
                    FROM productos p
                    WHERE ({tipo_sql}) {super_filter}

                    UNION ALL

                    SELECT p.id, p.id_externo AS retailer_id,
                           p.nombre, p.supermercado, p.categoria, p.formato,
                           (SELECT precio FROM precios WHERE producto_id=p.id
                            ORDER BY fecha_captura DESC LIMIT 1) AS precio,
                           p.tipo_producto, p.marca,
                           p.nombre_normalizado, p.categoria_normalizada,
                           2 AS prioridad,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.supermercado
                               ORDER BY p.nombre
                           ) AS rn
                    FROM productos p
                    WHERE ({marca_sql}) {super_filter}
                      AND p.id NOT IN (
                          SELECT p2.id FROM productos p2
                          WHERE ({tipo_sql.replace('p.', 'p2.')})
                      )

                    UNION ALL

                    SELECT p.id, p.id_externo AS retailer_id,
                           p.nombre, p.supermercado, p.categoria, p.formato,
                           (SELECT precio FROM precios WHERE producto_id=p.id
                            ORDER BY fecha_captura DESC LIMIT 1) AS precio,
                           p.tipo_producto, p.marca,
                           p.nombre_normalizado, p.categoria_normalizada,
                           3 AS prioridad,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.supermercado
                               ORDER BY p.nombre
                           ) AS rn
                    FROM productos p
                    WHERE ({nombre_sql}) {super_filter}
                      AND p.id NOT IN (
                          SELECT p2.id FROM productos p2
                          WHERE ({tipo_sql.replace('p.', 'p2.')})
                      )
                      AND p.id NOT IN (
                          SELECT p3.id FROM productos p3
                          WHERE ({marca_sql.replace('p.', 'p3.')})
                      )
                ) sub
                WHERE sub.rn <= ?
                ORDER BY sub.prioridad, sub.supermercado, sub.nombre
            """
            params = (params_tipo + super_params +
                      params_marca + super_params + params_tipo +
                      params_nombre + super_params + params_tipo + params_marca +
                      [limite_por_super])

            cur.execute(sql, params)
            rows = cur.fetchall()
            return (pd.DataFrame(rows, columns=[d[0] for d in cur.description])
                    if rows else pd.DataFrame())
        except Exception as e:
            logger.error("buscar_productos: %s", e)
            return pd.DataFrame()

    # ── Búsqueda para comparador (3 prioridades) ────────────────────
    def buscar_para_comparar(self, texto, limite_por_super=30):
        """Búsqueda para comparador: tipo → marca → nombre."""
        cur = self._cursor()
        try:
            palabras = texto.strip().lower().split()
            if not palabras:
                return pd.DataFrame()

            # Prioridad 1: tipo
            tipo_conds = ["p.nombre_normalizado LIKE ?"]
            params_tipo = [f"{palabras[0]}%"]
            for p in palabras[1:]:
                tipo_conds.append("p.nombre_normalizado LIKE ?")
                params_tipo.append(f"%{p}%")
            tipo_sql = " AND ".join(tipo_conds)

            # Prioridad 2: marca
            marca_conds = ["LOWER(p.marca) LIKE ?" for _ in palabras]
            params_marca = [f"%{p}%" for p in palabras]
            marca_sql = " AND ".join(marca_conds)

            # Prioridad 3: nombre
            nombre_conds = ["p.nombre LIKE ?" for _ in palabras]
            params_nombre = [f"%{p}%" for p in palabras]
            nombre_sql = " AND ".join(nombre_conds)

            sql = f"""
                SELECT id, nombre, supermercado, formato, precio,
                       precio_unidad, url, url_imagen,
                       tipo_producto, marca, categoria_normalizada, prioridad
                FROM (
                    SELECT p.id, p.nombre, p.supermercado, p.formato,
                           pr.precio, pr.precio_por_unidad AS precio_unidad,
                           p.url, p.url_imagen,
                           p.tipo_producto, p.marca, p.categoria_normalizada,
                           1 AS prioridad,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.supermercado
                               ORDER BY pr.precio ASC
                           ) AS rn
                    FROM productos p
                    JOIN precios pr ON pr.id = (
                        SELECT id FROM precios WHERE producto_id=p.id
                        ORDER BY fecha_captura DESC LIMIT 1
                    )
                    WHERE {tipo_sql}

                    UNION ALL

                    SELECT p.id, p.nombre, p.supermercado, p.formato,
                           pr.precio, pr.precio_por_unidad AS precio_unidad,
                           p.url, p.url_imagen,
                           p.tipo_producto, p.marca, p.categoria_normalizada,
                           2 AS prioridad,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.supermercado
                               ORDER BY pr.precio ASC
                           ) AS rn
                    FROM productos p
                    JOIN precios pr ON pr.id = (
                        SELECT id FROM precios WHERE producto_id=p.id
                        ORDER BY fecha_captura DESC LIMIT 1
                    )
                    WHERE {marca_sql}
                      AND p.id NOT IN (
                          SELECT p2.id FROM productos p2
                          WHERE {tipo_sql.replace('p.', 'p2.')}
                      )

                    UNION ALL

                    SELECT p.id, p.nombre, p.supermercado, p.formato,
                           pr.precio, pr.precio_por_unidad AS precio_unidad,
                           p.url, p.url_imagen,
                           p.tipo_producto, p.marca, p.categoria_normalizada,
                           3 AS prioridad,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.supermercado
                               ORDER BY pr.precio ASC
                           ) AS rn
                    FROM productos p
                    JOIN precios pr ON pr.id = (
                        SELECT id FROM precios WHERE producto_id=p.id
                        ORDER BY fecha_captura DESC LIMIT 1
                    )
                    WHERE {nombre_sql}
                      AND p.id NOT IN (
                          SELECT p2.id FROM productos p2
                          WHERE {tipo_sql.replace('p.', 'p2.')}
                      )
                      AND p.id NOT IN (
                          SELECT p3.id FROM productos p3
                          WHERE {marca_sql.replace('p.', 'p3.')}
                      )
                ) sub WHERE sub.rn <= ?
                ORDER BY sub.prioridad, sub.supermercado, sub.precio
            """
            params = (params_tipo +
                      params_marca + params_tipo +
                      params_nombre + params_tipo + params_marca +
                      [limite_por_super])
            cur.execute(sql, params)
            rows = cur.fetchall()
            return (pd.DataFrame(rows, columns=[d[0] for d in cur.description])
                    if rows else pd.DataFrame())
        except Exception as e:
            logger.error("buscar_para_comparar: %s", e)
            return pd.DataFrame()

    # ── Categorías disponibles ────────────────────────────────────────
    def obtener_categorias(self):
        cur = self._cursor()
        try:
            cur.execute("""
                SELECT categoria_normalizada, COUNT(*) as cnt
                FROM productos
                WHERE categoria_normalizada != '' AND categoria_normalizada IS NOT NULL
                GROUP BY categoria_normalizada
                ORDER BY cnt DESC
            """)
            return [(r[0], r[1]) for r in cur.fetchall()]
        except Exception:
            return []

    # ── Histórico de precios ──────────────────────────────────────────
    def obtener_historico_precios(self, producto_id):
        cur = self._cursor()
        try:
            cur.execute("""
                SELECT fecha_captura, precio,
                       precio_por_unidad AS precio_unidad
                FROM precios WHERE producto_id=?
                ORDER BY fecha_captura ASC
            """, (producto_id,))
            rows = cur.fetchall()
            return (pd.DataFrame(rows,
                    columns=["fecha_captura", "precio", "precio_unidad"])
                    if rows else pd.DataFrame())
        except Exception as e:
            logger.error("obtener_historico_precios: %s", e)
            return pd.DataFrame()

    # ── Equivalencias ─────────────────────────────────────────────────
    def listar_grupos_equivalencia(self):
        cur = self._cursor()
        try:
            cur.execute(
                "SELECT DISTINCT nombre_comun FROM equivalencias ORDER BY nombre_comun"
            )
            return [r[0] for r in cur.fetchall()]
        except Exception:
            return []

    def obtener_equivalencias(self, nombre_comun):
        cur = self._cursor()
        try:
            cur.execute(
                "SELECT * FROM equivalencias WHERE nombre_comun=?",
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
            for sn, id_ext in ids_por_super.items():
                if not id_ext:
                    continue
                cur.execute("""
                    SELECT p.id, p.nombre, p.supermercado, p.formato, pr.precio
                    FROM productos p
                    LEFT JOIN precios pr ON pr.id = (
                        SELECT id FROM precios WHERE producto_id=p.id
                        ORDER BY fecha_captura DESC LIMIT 1
                    )
                    WHERE p.id_externo=? AND p.supermercado=?
                """, (id_ext, sn))
                r = cur.fetchone()
                if r:
                    resultados.append(dict(r))
            return pd.DataFrame(resultados) if resultados else pd.DataFrame()
        except Exception as e:
            logger.error("obtener_equivalencias: %s", e)
            return pd.DataFrame()

    def obtener_historico_equivalencia(self, nombre_comun):
        df = self.obtener_equivalencias(nombre_comun)
        if df.empty:
            return pd.DataFrame()
        historicos = []
        for _, row in df.iterrows():
            hist = self.obtener_historico_precios(row['id'])
            if not hist.empty:
                hist['supermercado'] = row['supermercado']
                hist['nombre'] = row['nombre']
                historicos.append(hist)
        return pd.concat(historicos, ignore_index=True) if historicos else pd.DataFrame()

    def guardar_equivalencia(self, nombre_comun, ids_por_super):
        cur = self._cursor()
        cur.execute("""
            INSERT INTO equivalencias
                (nombre_comun, producto_mercadona_id, producto_carrefour_id,
                 producto_dia_id, producto_alcampo_id, producto_eroski_id)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (nombre_comun,
              ids_por_super.get("Mercadona"),
              ids_por_super.get("Carrefour"),
              ids_por_super.get("Dia"),
              ids_por_super.get("Alcampo"),
              ids_por_super.get("Eroski")))
        self._conn.commit()

    def crear_equivalencia(self, nombre_comun, lista_producto_ids):
        cur = self._cursor()
        ids_por_super = {}
        for pid in lista_producto_ids:
            cur.execute(
                "SELECT id_externo, supermercado FROM productos WHERE id=?",
                (pid,),
            )
            row = cur.fetchone()
            if row:
                ids_por_super[row["supermercado"]] = row["id_externo"]
        if ids_por_super:
            self.guardar_equivalencia(nombre_comun, ids_por_super)

    # ── Favoritos ─────────────────────────────────────────────────────
    def agregar_favorito(self, producto_id):
        cur = self._cursor()
        try:
            cur.execute(
                "INSERT OR IGNORE INTO favoritos (producto_id) VALUES (?)",
                (producto_id,),
            )
            self._conn.commit()
        except Exception as e:
            logger.error("agregar_favorito: %s", e)

    def eliminar_favorito(self, producto_id):
        cur = self._cursor()
        try:
            cur.execute("DELETE FROM favoritos WHERE producto_id=?", (producto_id,))
            self._conn.commit()
        except Exception as e:
            logger.error("eliminar_favorito: %s", e)

    def obtener_favoritos(self):
        cur = self._cursor()
        try:
            cur.execute("""
                SELECT p.id, p.nombre, p.supermercado, p.formato,
                       p.tipo_producto, p.marca, p.categoria_normalizada,
                       pr.precio, f.fecha_agregado
                FROM favoritos f
                JOIN productos p ON p.id=f.producto_id
                LEFT JOIN precios pr ON pr.id = (
                    SELECT id FROM precios WHERE producto_id=p.id
                    ORDER BY fecha_captura DESC LIMIT 1
                )
                ORDER BY f.fecha_agregado DESC
            """)
            rows = cur.fetchall()
            return (pd.DataFrame(rows, columns=[d[0] for d in cur.description])
                    if rows else pd.DataFrame())
        except Exception as e:
            logger.error("obtener_favoritos: %s", e)
            return pd.DataFrame()
