"""database/database_db_manager.py - Gestor de la BD con normalización integrada."""

import sqlite3
import logging
import os
import pandas as pd
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Ruta absoluta basada en ubicación REAL de este archivo
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "database", "supermercados.db")

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
        logger.info("DB conectada: %s", self.db_path)

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

    # ── Guardar productos (con normalización + formato) ───────────────
    def guardar_productos(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return {"nuevos": 0, "productos_nuevos": 0,
                    "actualizados": 0, "productos_actualizados": 0,
                    "precios": 0, "precios_registrados": 0}

        cur = self._cursor()
        nuevos = actualizados = precios_ok = precios_skip = 0
        ts = datetime.now().isoformat()
        fecha_hoy = date.today().isoformat()  # "2026-02-28"

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
                url        = str(row.get("URL") or row.get("Url") or "").strip()
                url_imagen = str(row.get("URL_imagen") or row.get("Url_imagen") or "").strip()

                # ── Normalización ──
                if _NORMALIZER_OK:
                    norm = normalizar_producto(nombre, supermercado, formato)
                    tipo_producto         = norm["tipo_producto"]
                    marca                 = norm["marca"]
                    nombre_normalizado    = norm["nombre_normalizado"]
                    categoria_normalizada = norm["categoria_normalizada"]
                    formato_normalizado   = norm["formato_normalizado"]
                else:
                    tipo_producto = nombre
                    marca = ""
                    nombre_normalizado = nombre.lower().strip()
                    categoria_normalizada = ""
                    formato_normalizado = formato

                cur.execute("""
                    INSERT INTO productos
                        (id_externo, nombre, supermercado, categoria, formato,
                         url, url_imagen, fecha_creacion, fecha_actualizacion,
                         tipo_producto, marca, nombre_normalizado,
                         categoria_normalizada, formato_normalizado)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                        categoria_normalizada = excluded.categoria_normalizada,
                        formato_normalizado   = excluded.formato_normalizado
                """, (id_externo, nombre, supermercado, categoria, formato,
                      url, url_imagen, ts, ts,
                      tipo_producto, marca, nombre_normalizado,
                      categoria_normalizada, formato_normalizado))
                nuevos += cur.rowcount > 0

                cur.execute(
                    "SELECT id FROM productos "
                    "WHERE id_externo=? AND supermercado=?",
                    (id_externo, supermercado),
                )
                prod_id = cur.fetchone()[0]

                # ── Insertar precio: 1 registro por producto por DÍA ──
                # Usar DATE() para comparación robusta (no LIKE)
                cur.execute(
                    "SELECT id FROM precios "
                    "WHERE producto_id=? AND DATE(fecha_captura)=?",
                    (prod_id, fecha_hoy),
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
                    precios_skip += 1
            except Exception as e:
                logger.debug("Error guardando producto: %s", e)

        self._conn.commit()

        logger.info(
            "guardar_productos [%s]: fecha_hoy=%s, "
            "precios_insertados=%d, precios_ya_existían=%d",
            supermercado if 'supermercado' in dir() else "?",
            fecha_hoy, precios_ok, precios_skip,
        )

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
                "SELECT COUNT(DISTINCT DATE(fecha_captura)) FROM precios"
            )
            dias_datos = cur.fetchone()[0]
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
                       p.formato_normalizado,
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

    # ── Búsqueda inteligente ──────────────────────────────────────────
    def buscar_productos(self, nombre=None, supermercado=None, limite=25):
        cur = self._cursor()
        try:
            limite_por_super = max(5, int(limite) // 5)
            palabras = nombre.strip().split() if nombre else []

            if not palabras:
                return pd.DataFrame()

            where_tipo = []
            where_nombre = []
            params_tipo = []
            params_nombre = []
            for p in palabras:
                where_tipo.append("p.nombre_normalizado LIKE ?")
                params_tipo.append(f"{p.lower()}%")
                where_nombre.append("p.nombre LIKE ?")
                params_nombre.append(f"%{p}%")

            tipo_sql = " AND ".join(where_tipo)
            nombre_sql = " AND ".join(where_nombre)

            super_filter = ""
            super_params = []
            if supermercado:
                super_filter = " AND p.supermercado=?"
                super_params = [supermercado]

            sql = f"""
                SELECT id, retailer_id, nombre, supermercado, categoria,
                       formato, formato_normalizado, precio, tipo_producto,
                       marca, nombre_normalizado, categoria_normalizada,
                       prioridad
                FROM (
                    SELECT p.id, p.id_externo AS retailer_id,
                           p.nombre, p.supermercado, p.categoria, p.formato,
                           p.formato_normalizado,
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
                           p.formato_normalizado,
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
                    WHERE ({nombre_sql}) {super_filter}
                      AND p.id NOT IN (
                          SELECT p2.id FROM productos p2
                          WHERE ({tipo_sql.replace('p.', 'p2.')})
                      )
                ) sub
                WHERE sub.rn <= ?
                ORDER BY sub.prioridad, sub.supermercado, sub.nombre
            """
            params = (params_tipo + super_params +
                      params_nombre + super_params +
                      params_tipo +
                      [limite_por_super])

            cur.execute(sql, params)
            rows = cur.fetchall()
            return (pd.DataFrame(rows, columns=[d[0] for d in cur.description])
                    if rows else pd.DataFrame())
        except Exception as e:
            logger.error("buscar_productos: %s", e)
            return pd.DataFrame()

    # ── Búsqueda para comparador ──────────────────────────────────────
    def buscar_para_comparar(self, texto, limite_por_super=30):
        cur = self._cursor()
        try:
            palabras = texto.strip().split()
            if not palabras:
                return pd.DataFrame()

            where_tipo = " AND ".join(
                ["p.nombre_normalizado LIKE ?" for _ in palabras]
            )
            params_tipo = [f"{p.lower()}%" for p in palabras]

            where_nombre = " AND ".join(
                ["p.nombre LIKE ?" for _ in palabras]
            )
            params_nombre = [f"%{p}%" for p in palabras]

            sql = f"""
                SELECT id, nombre, supermercado, formato,
                       formato_normalizado, precio,
                       precio_unidad, url, url_imagen,
                       tipo_producto, marca, categoria_normalizada, prioridad
                FROM (
                    SELECT p.id, p.nombre, p.supermercado, p.formato,
                           p.formato_normalizado,
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
                    WHERE {where_tipo}

                    UNION ALL

                    SELECT p.id, p.nombre, p.supermercado, p.formato,
                           p.formato_normalizado,
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
                    WHERE {where_nombre}
                      AND p.id NOT IN (
                          SELECT p2.id FROM productos p2
                          WHERE {where_tipo.replace('p.', 'p2.')}
                      )
                ) sub WHERE sub.rn <= ?
                ORDER BY sub.prioridad, sub.supermercado, sub.precio
            """
            params = params_tipo + params_nombre + params_tipo + [limite_por_super]
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
                    SELECT p.id, p.nombre, p.supermercado, p.formato,
                           p.formato_normalizado, pr.precio
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
                       p.formato_normalizado,
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
    
    # ── Cesta de la compra ─────────────────────────────────────────────

    def obtener_producto_por_id(self, producto_id):
        """Devuelve dict con datos del producto + ultimo precio.

        Returns:
            dict o None si no se encuentra.
        """
        cur = self._cursor()
        try:
            cur.execute("""
                SELECT p.id, p.nombre, p.supermercado, p.marca,
                       p.categoria_normalizada, p.formato_normalizado,
                       p.tipo_producto, p.nombre_normalizado,
                       (SELECT precio FROM precios WHERE producto_id=p.id
                        ORDER BY fecha_captura DESC LIMIT 1) AS precio
                FROM productos p
                WHERE p.id = ?
            """, (producto_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("obtener_producto_por_id: %s", e)
            return None

    def buscar_alternativa_mas_barata(self, producto_id):
        """Busca el producto equivalente mas barato en otro supermercado.

        Busca por misma categoria + formato + nombre similar (tipo_producto).
        Solo devuelve alternativa si es estrictamente mas barata.

        Returns:
            dict con {id, nombre, supermercado, precio, formato_normalizado}
            o None si no hay alternativa mas barata.
        """
        cur = self._cursor()
        try:
            # 1) Obtener datos del producto original
            producto = self.obtener_producto_por_id(producto_id)
            if not producto or not producto.get('precio'):
                return None

            cat = producto.get('categoria_normalizada', '')
            fmt = producto.get('formato_normalizado', '')
            super_orig = producto.get('supermercado', '')
            precio_orig = producto['precio']

            # Si no hay categoria o formato, no se puede buscar
            if not cat or not fmt:
                return None

            # 2) Extraer tipo de producto (sin marca) para busqueda
            tipo = producto.get('tipo_producto', '')
            if not tipo:
                tipo = producto.get('nombre_normalizado', '')
            if not tipo:
                return None

            # Usar primeras 2-3 palabras del tipo como termino
            palabras_tipo = tipo.strip().split()[:3]
            if not palabras_tipo:
                return None

            # Construir LIKE conditions
            where_parts = []
            params = [cat, fmt, super_orig]
            for p in palabras_tipo:
                where_parts.append("p.nombre_normalizado LIKE ?")
                params.append(f"%{p.lower()}%")

            where_nombre = " AND ".join(where_parts)

            # 3) Query: mismo cat+fmt, distinto super, nombre similar
            sql = f"""
                SELECT p.id, p.nombre, p.supermercado,
                       p.formato_normalizado,
                       (SELECT precio FROM precios
                        WHERE producto_id = p.id
                        ORDER BY fecha_captura DESC LIMIT 1
                       ) AS precio
                FROM productos p
                WHERE p.categoria_normalizada = ?
                  AND p.formato_normalizado = ?
                  AND p.supermercado != ?
                  AND {where_nombre}
                ORDER BY precio ASC
                LIMIT 1
            """
            cur.execute(sql, params)
            row = cur.fetchone()

            if row:
                alt = dict(row)
                if alt.get('precio') and alt['precio'] < precio_orig:
                    return alt

            return None
        except Exception as e:
            logger.error("buscar_alternativa_mas_barata: %s", e)
            return None