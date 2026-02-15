# -*- coding: utf-8 -*-

"""
Script de inicialización de la base de datos.

Crea el archivo SQLite con todas las tablas necesarias.
Ejecutar una sola vez al configurar el proyecto:
    python -m database.init_db

Si la base de datos ya existe, no sobreescribe los datos.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "supermercados.db")

SCHEMA = """
-- =============================================================================
-- TABLA: productos
-- Almacena la información estática de cada producto.
-- Un producto se identifica por su ID original + supermercado.
-- =============================================================================
CREATE TABLE IF NOT EXISTS productos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_externo      TEXT NOT NULL,
    nombre          TEXT NOT NULL,
    supermercado    TEXT NOT NULL,
    categoria       TEXT,
    formato         TEXT,
    url             TEXT,
    url_imagen      TEXT,
    fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id_externo, supermercado)
);

-- =============================================================================
-- TABLA: precios
-- Almacena un registro de precio por cada ejecución del scraper.
-- Cada fila es: "el producto X costaba Y euros en la fecha Z".
-- Esta tabla crece con cada ejecución y es la base del histórico.
-- =============================================================================
CREATE TABLE IF NOT EXISTS precios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id     INTEGER NOT NULL,
    precio          REAL NOT NULL,
    precio_por_unidad REAL,
    fecha_captura   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- =============================================================================
-- TABLA: equivalencias
-- Vincula productos que son el mismo artículo en distintos supermercados.
-- Ejemplo: "Coca-Cola 2L" tiene un grupo, y dentro de ese grupo están
-- los IDs de Mercadona, Carrefour, Dia, etc.
-- =============================================================================
CREATE TABLE IF NOT EXISTS equivalencias (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_comun    TEXT NOT NULL,
    producto_id     INTEGER NOT NULL,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- =============================================================================
-- TABLA: favoritos
-- Productos marcados como favoritos por el usuario.
-- =============================================================================
CREATE TABLE IF NOT EXISTS favoritos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id     INTEGER NOT NULL UNIQUE,
    fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- =============================================================================
-- ÍNDICES para mejorar rendimiento de consultas frecuentes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_precios_producto_id ON precios(producto_id);
CREATE INDEX IF NOT EXISTS idx_precios_fecha ON precios(fecha_captura);
CREATE INDEX IF NOT EXISTS idx_productos_supermercado ON productos(supermercado);
CREATE INDEX IF NOT EXISTS idx_productos_id_externo ON productos(id_externo);
CREATE INDEX IF NOT EXISTS idx_equivalencias_nombre ON equivalencias(nombre_comun);
CREATE INDEX IF NOT EXISTS idx_equivalencias_producto ON equivalencias(producto_id);
"""


def inicializar_base_datos():
    """
    Crea la base de datos y todas las tablas si no existen.
    
    Returns:
        str: Ruta del archivo de base de datos creado.
    """
    # Crear carpeta si no existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    ya_existia = os.path.exists(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(SCHEMA)
    conn.commit()
    conn.close()

    if ya_existia:
        logger.info(f"Base de datos ya existente verificada: {DB_PATH}")
    else:
        logger.info(f"Base de datos creada: {DB_PATH}")

    return DB_PATH


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    ruta = inicializar_base_datos()
    print(f"Base de datos lista en: {ruta}")
    
    # Mostrar las tablas creadas
    conn = sqlite3.connect(ruta)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tablas = cursor.fetchall()
    conn.close()
    
    print(f"Tablas creadas: {', '.join(t[0] for t in tablas)}")
