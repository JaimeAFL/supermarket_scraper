"""database/init_db.py - Inicialización de la base de datos en PostgreSQL."""

import logging
import os

logger = logging.getLogger(__name__)

try:
    import psycopg2
except ImportError:
    raise ImportError("Instala psycopg2-binary: pip install psycopg2-binary")


def _get_database_url():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError("Variable de entorno DATABASE_URL no definida.")
    return url.replace("postgres://", "postgresql://", 1)


def inicializar_base_datos(db_path: str = None) -> str:
    """Crea tablas e índices en PostgreSQL. db_path se ignora (compatibilidad)."""

    url = _get_database_url()
    conn = psycopg2.connect(url, sslmode="require")
    conn.autocommit = False
    cur = conn.cursor()

    logger.info("Inicializando BD PostgreSQL...")

    # ── Tablas base ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id                      SERIAL PRIMARY KEY,
            id_externo              TEXT    NOT NULL,
            nombre                  TEXT    NOT NULL,
            supermercado            TEXT    NOT NULL,
            categoria               TEXT,
            formato                 TEXT,
            url                     TEXT,
            url_imagen              TEXT,
            fecha_creacion          TEXT,
            fecha_actualizacion     TEXT,
            tipo_producto           TEXT    DEFAULT '',
            marca                   TEXT    DEFAULT '',
            nombre_normalizado      TEXT    DEFAULT '',
            categoria_normalizada   TEXT    DEFAULT '',
            formato_normalizado     TEXT    DEFAULT '',
            UNIQUE(id_externo, supermercado)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id                SERIAL PRIMARY KEY,
            producto_id       INTEGER NOT NULL REFERENCES productos(id),
            precio            REAL    NOT NULL,
            precio_por_unidad TEXT,
            fecha_captura     TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS equivalencias (
            id                      SERIAL PRIMARY KEY,
            nombre_comun            TEXT NOT NULL,
            producto_mercadona_id   TEXT,
            producto_carrefour_id   TEXT,
            producto_dia_id         TEXT,
            producto_alcampo_id     TEXT,
            producto_eroski_id      TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS favoritos (
            id              SERIAL PRIMARY KEY,
            producto_id     INTEGER NOT NULL REFERENCES productos(id),
            fecha_agregado  TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
            UNIQUE(producto_id)
        )
    """)

    # ── Índices ───────────────────────────────────────────────────────
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_precios_producto      ON precios(producto_id)",
        "CREATE INDEX IF NOT EXISTS idx_precios_fecha         ON precios(fecha_captura)",
        "CREATE INDEX IF NOT EXISTS idx_productos_super       ON productos(supermercado)",
        "CREATE INDEX IF NOT EXISTS idx_productos_nombre      ON productos(nombre)",
        "CREATE INDEX IF NOT EXISTS idx_productos_tipo        ON productos(tipo_producto)",
        "CREATE INDEX IF NOT EXISTS idx_productos_nombre_norm ON productos(nombre_normalizado)",
        "CREATE INDEX IF NOT EXISTS idx_productos_cat_norm    ON productos(categoria_normalizada)",
        "CREATE INDEX IF NOT EXISTS idx_productos_marca       ON productos(marca)",
    ]
    for idx in indices:
        cur.execute(idx)

    conn.commit()
    cur.close()
    conn.close()

    logger.info("Base de datos PostgreSQL verificada.")
    return "postgresql (Aiven)"
