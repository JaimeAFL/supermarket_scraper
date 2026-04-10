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
    conn = psycopg2.connect(url, sslmode="require", connect_timeout=30)
    conn.autocommit = True  # DDL libera locks inmediatamente, sin transacción colgada
    cur = conn.cursor()
    cur.execute("SET lock_timeout = '15s'")

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

    # ── Listas de la compra ───────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS listas (
            id                  SERIAL PRIMARY KEY,
            nombre              TEXT    NOT NULL,
            etiqueta            TEXT    DEFAULT '',
            notas               TEXT    DEFAULT '',
            fecha_creacion      TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
            fecha_actualizacion TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lista_productos (
            id              SERIAL PRIMARY KEY,
            lista_id        INTEGER NOT NULL REFERENCES listas(id) ON DELETE CASCADE,
            producto_id     INTEGER NOT NULL REFERENCES productos(id),
            cantidad        INTEGER NOT NULL DEFAULT 1,
            notas           TEXT    DEFAULT '',
            fecha_agregado  TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
            UNIQUE(lista_id, producto_id)
        )
    """)

    # ── Envíos ────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS envios (
            id                  SERIAL PRIMARY KEY,
            supermercado        TEXT    NOT NULL UNIQUE,
            coste_envio         REAL    NOT NULL,
            umbral_gratis       REAL,
            pedido_minimo       REAL,
            notas               TEXT    DEFAULT '',
            fecha_verificacion  TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    cur.execute("""
        INSERT INTO envios (supermercado, coste_envio, umbral_gratis, pedido_minimo, notas)
        VALUES
            ('Mercadona', 7.70, NULL, 50.0, 'Pedido mínimo 50€. Sin envío gratis.'),
            ('Carrefour', 7.95, 99.0, NULL, 'Envío gratis a partir de 99€.'),
            ('Dia',       3.99, 39.0, NULL, 'Envío gratis a partir de 39€ con Club Dia.'),
            ('Alcampo',   6.90, 80.0, NULL, 'Envío gratis a partir de 80€.'),
            ('Eroski',    5.95, 50.0, NULL, 'Envío gratis a partir de 50€.'),
            ('Consum',    7.50, 60.0, NULL, 'Envío gratis a partir de 60€ en muchas zonas.'),
            ('Condis',    4.99, 49.0, NULL, 'Envío gratis a partir de 49€.')
        ON CONFLICT (supermercado) DO NOTHING
    """)

    # ── Columnas nuevas (solo si no existen, evita locks concurrentes) ──
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'precios'
          AND column_name IN ('precio_referencia', 'unidad_referencia')
    """)
    existing_cols = {row[0] for row in cur.fetchall()}
    if 'precio_referencia' not in existing_cols:
        cur.execute("ALTER TABLE precios ADD COLUMN precio_referencia REAL")
    if 'unidad_referencia' not in existing_cols:
        cur.execute("ALTER TABLE precios ADD COLUMN unidad_referencia TEXT DEFAULT ''")

    # ── Restricción UNIQUE en productos(id_externo, supermercado) ────────
    # Requerida por el UPSERT ON CONFLICT en guardar_productos.
    # CREATE TABLE IF NOT EXISTS no la añade si la tabla ya existía sin ella.
    cur.execute("""
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        WHERE c.relname = 'productos'
          AND i.indisunique = true
          AND i.indpred IS NULL
          AND ARRAY(
                SELECT a.attname
                FROM pg_attribute a
                WHERE a.attrelid = c.oid
                  AND a.attnum = ANY(i.indkey)
                ORDER BY a.attname
              ) = ARRAY['id_externo', 'supermercado']
        LIMIT 1
    """)
    if not cur.fetchone():
        logger.info("Restricción UNIQUE ausente — deduplicando y añadiendo...")

        # 1. Redirigir precios de duplicados al representante (MIN id)
        cur.execute("""
            UPDATE precios p
            SET producto_id = repr.id_ok
            FROM (
                SELECT id_externo, supermercado, MIN(id) AS id_ok
                FROM productos
                GROUP BY id_externo, supermercado
                HAVING COUNT(*) > 1
            ) repr
            JOIN productos dup
              ON dup.id_externo = repr.id_externo
             AND dup.supermercado = repr.supermercado
             AND dup.id > repr.id_ok
            WHERE p.producto_id = dup.id
        """)

        # 2. Eliminar filas dependientes que apuntan a duplicados
        cur.execute("""
            DELETE FROM favoritos
            WHERE producto_id NOT IN (
                SELECT MIN(id) FROM productos GROUP BY id_externo, supermercado
            )
        """)
        cur.execute("""
            DELETE FROM lista_productos
            WHERE producto_id NOT IN (
                SELECT MIN(id) FROM productos GROUP BY id_externo, supermercado
            )
        """)

        # 3. Borrar duplicados (mantiene el de menor id por par)
        cur.execute("""
            DELETE FROM productos
            WHERE id NOT IN (
                SELECT MIN(id) FROM productos GROUP BY id_externo, supermercado
            )
        """)

        # 4. Crear el índice único (compatible con ON CONFLICT)
        cur.execute("""
            CREATE UNIQUE INDEX productos_id_externo_supermercado_key
            ON productos(id_externo, supermercado)
        """)
        logger.info("Restricción UNIQUE creada en productos(id_externo, supermercado).")

    # ── Índices ───────────────────────────────────────────────────────
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_precios_producto      ON precios(producto_id)",
        "CREATE INDEX IF NOT EXISTS idx_precios_fecha         ON precios(fecha_captura)",
        "CREATE INDEX IF NOT EXISTS idx_precios_referencia    ON precios(precio_referencia)",
        "CREATE INDEX IF NOT EXISTS idx_productos_super       ON productos(supermercado)",
        "CREATE INDEX IF NOT EXISTS idx_productos_nombre      ON productos(nombre)",
        "CREATE INDEX IF NOT EXISTS idx_productos_tipo        ON productos(tipo_producto)",
        "CREATE INDEX IF NOT EXISTS idx_productos_nombre_norm ON productos(nombre_normalizado)",
        "CREATE INDEX IF NOT EXISTS idx_productos_cat_norm    ON productos(categoria_normalizada)",
        "CREATE INDEX IF NOT EXISTS idx_productos_marca       ON productos(marca)",
        "CREATE INDEX IF NOT EXISTS idx_lista_productos_lista    ON lista_productos(lista_id)",
        "CREATE INDEX IF NOT EXISTS idx_lista_productos_producto ON lista_productos(producto_id)",
    ]
    for idx in indices:
        cur.execute(idx)

    cur.close()
    conn.close()

    logger.info("Base de datos PostgreSQL verificada.")
    return "postgresql (Aiven)"
