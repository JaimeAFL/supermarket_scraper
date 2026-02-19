"""database/init_db.py - Inicialización de la base de datos SQLite."""

import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "database", "supermercados.db")
)


def inicializar_base_datos(db_path: str = None) -> str:
    """Crea las tablas e índices si no existen. Devuelve la ruta absoluta usada."""
    if db_path is None:
        db_path = os.environ.get("SUPERMARKET_DB_PATH", _DEFAULT_DB)

    db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS productos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            id_externo          TEXT    NOT NULL,
            nombre              TEXT    NOT NULL,
            supermercado        TEXT    NOT NULL,
            categoria           TEXT,
            formato             TEXT,
            url                 TEXT,
            url_imagen          TEXT,
            fecha_creacion      TEXT,
            fecha_actualizacion TEXT,
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
    conn.commit()
    conn.close()

    logger.info(f"Base de datos verificada: {db_path}")
    return db_path
