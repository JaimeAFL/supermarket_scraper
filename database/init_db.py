"""database/init_db.py - Inicialización y migración de la base de datos."""

import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

# Ruta absoluta basada en la ubicación REAL de este archivo, no en cwd
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "database", "supermercados.db")


def inicializar_base_datos(db_path: str = None) -> str:
    """Crea tablas, índices y migra datos existentes. Devuelve ruta usada."""
    if db_path is None:
        db_path = os.environ.get("SUPERMARKET_DB_PATH", _DEFAULT_DB)

    db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info("Inicializando BD: %s", db_path)

    conn = sqlite3.connect(db_path)

    # ── Tablas base ───────────────────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS productos (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            id_externo              TEXT    NOT NULL,
            nombre                  TEXT    NOT NULL,
            supermercado            TEXT    NOT NULL,
            categoria               TEXT,
            formato                 TEXT,
            url                     TEXT,
            url_imagen              TEXT,
            fecha_creacion          TEXT,
            fecha_actualizacion     TEXT,
            UNIQUE(id_externo, supermercado)
        );

        CREATE TABLE IF NOT EXISTS precios (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id       INTEGER NOT NULL REFERENCES productos(id),
            precio            REAL    NOT NULL,
            precio_por_unidad TEXT,
            fecha_captura     TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS equivalencias (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_comun          TEXT NOT NULL,
            producto_mercadona_id TEXT,
            producto_carrefour_id TEXT,
            producto_dia_id       TEXT,
            producto_alcampo_id   TEXT,
            producto_eroski_id    TEXT
        );

        CREATE TABLE IF NOT EXISTS favoritos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id    INTEGER NOT NULL REFERENCES productos(id),
            fecha_agregado TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(producto_id)
        );

        CREATE INDEX IF NOT EXISTS idx_precios_producto ON precios(producto_id);
        CREATE INDEX IF NOT EXISTS idx_precios_fecha    ON precios(fecha_captura);
        CREATE INDEX IF NOT EXISTS idx_productos_super  ON productos(supermercado);
        CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre);
    """)

    # ── Migración: añadir columnas de normalización ───────────────────
    columnas_nuevas = {
        "tipo_producto":          "TEXT DEFAULT ''",
        "marca":                  "TEXT DEFAULT ''",
        "nombre_normalizado":     "TEXT DEFAULT ''",
        "categoria_normalizada":  "TEXT DEFAULT ''",
        "formato_normalizado":    "TEXT DEFAULT ''",
    }

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(productos)")
    columnas_existentes = {row[1] for row in cur.fetchall()}

    for col, tipo in columnas_nuevas.items():
        if col not in columnas_existentes:
            cur.execute(f"ALTER TABLE productos ADD COLUMN {col} {tipo}")
            logger.info("Columna añadida: productos.%s", col)

    # ── Índices para búsqueda normalizada ─────────────────────────────
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_productos_tipo
            ON productos(tipo_producto);
        CREATE INDEX IF NOT EXISTS idx_productos_nombre_norm
            ON productos(nombre_normalizado);
        CREATE INDEX IF NOT EXISTS idx_productos_cat_norm
            ON productos(categoria_normalizada);
        CREATE INDEX IF NOT EXISTS idx_productos_marca
            ON productos(marca);
    """)

    # ── Migración: normalizar productos existentes sin normalizar ─────
    cur.execute("""
        SELECT COUNT(*) FROM productos
        WHERE nombre_normalizado IS NULL OR nombre_normalizado = ''
    """)
    sin_normalizar = cur.fetchone()[0]

    if sin_normalizar > 0:
        logger.info(
            "Migrando %d productos sin normalizar...", sin_normalizar
        )
        try:
            import sys
            if _PROJECT_ROOT not in sys.path:
                sys.path.insert(0, _PROJECT_ROOT)
            from matching.normalizer import normalizar_producto

            cur.execute("""
                SELECT id, nombre, supermercado, formato FROM productos
                WHERE nombre_normalizado IS NULL OR nombre_normalizado = ''
            """)
            rows = cur.fetchall()

            for row_id, nombre, supermercado, formato in rows:
                r = normalizar_producto(nombre, supermercado, formato or "")
                cur.execute("""
                    UPDATE productos SET
                        tipo_producto = ?,
                        marca = ?,
                        nombre_normalizado = ?,
                        categoria_normalizada = ?,
                        formato_normalizado = ?
                    WHERE id = ?
                """, (
                    r["tipo_producto"],
                    r["marca"],
                    r["nombre_normalizado"],
                    r["categoria_normalizada"],
                    r["formato_normalizado"],
                    row_id,
                ))

            conn.commit()
            logger.info("Migración completada: %d productos normalizados.", len(rows))
        except ImportError:
            logger.warning(
                "matching.normalizer no disponible — "
                "los productos se normalizarán en la próxima ejecución del scraper."
            )
        except Exception as e:
            logger.error("Error en migración: %s", e)
            conn.rollback()

    # ── Migración: rellenar formato_normalizado en productos que ya
    #    tienen nombre_normalizado pero no formato_normalizado ─────────
    cur.execute("""
        SELECT COUNT(*) FROM productos
        WHERE nombre_normalizado != ''
          AND (formato_normalizado IS NULL OR formato_normalizado = '')
    """)
    sin_formato = cur.fetchone()[0]

    if sin_formato > 0:
        logger.info("Migrando formato de %d productos...", sin_formato)
        try:
            import sys
            if _PROJECT_ROOT not in sys.path:
                sys.path.insert(0, _PROJECT_ROOT)
            from matching.normalizer import normalizar_formato

            cur.execute("""
                SELECT id, nombre, formato FROM productos
                WHERE nombre_normalizado != ''
                  AND (formato_normalizado IS NULL OR formato_normalizado = '')
            """)
            rows = cur.fetchall()

            for row_id, nombre, formato in rows:
                fmt = normalizar_formato(formato or "", nombre)
                cur.execute(
                    "UPDATE productos SET formato_normalizado = ? WHERE id = ?",
                    (fmt, row_id),
                )

            conn.commit()
            logger.info("Migración de formato completada: %d productos.", len(rows))
        except ImportError:
            pass
        except Exception as e:
            logger.error("Error migrando formato: %s", e)
            conn.rollback()

    conn.commit()
    conn.close()
    logger.info("Base de datos verificada: %s", db_path)
    return db_path
