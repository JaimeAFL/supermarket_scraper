# -*- coding: utf-8 -*-

"""
Gestor de base de datos SQLite.

Proporciona todas las operaciones necesarias para:
- Insertar y actualizar productos.
- Registrar precios con timestamp.
- Consultar históricos de precios.
- Gestionar equivalencias entre supermercados.
- Gestionar favoritos.
"""

import os
import sqlite3
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "supermercados.db")


class DatabaseManager:
    """
    Clase que gestiona todas las operaciones con la base de datos.
    
    Uso:
        db = DatabaseManager()
        db.guardar_productos(df_mercadona)
        historial = db.obtener_historico_precios(producto_id=42)
        db.cerrar()
    """
    
    def __init__(self, db_path=None):
        """
        Abre conexión con la base de datos.
        
        Args:
            db_path (str): Ruta al archivo .db. Si no se indica, usa la ruta por defecto.
        """
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
        logger.info(f"Conexión abierta: {self.db_path}")
    
    def cerrar(self):
        """Cierra la conexión con la base de datos."""
        if self.conn:
            self.conn.close()
            logger.info("Conexión cerrada.")

    # =========================================================================
    # PRODUCTOS
    # =========================================================================

    def guardar_productos(self, df):
        """
        Inserta o actualiza productos desde un DataFrame del scraper.
        Por cada producto, también registra el precio actual en la tabla de precios.
        
        Args:
            df (pd.DataFrame): DataFrame con columnas:
                Id, Nombre, Precio, Precio_por_unidad, Formato,
                Categoria, Supermercado, Url, Url_imagen
        
        Returns:
            dict: Resumen con productos_nuevos, productos_actualizados y precios_registrados.
        """
        cursor = self.conn.cursor()
        nuevos = 0
        actualizados = 0
        precios_registrados = 0
        ahora = datetime.now().isoformat()

        for _, row in df.iterrows():
            id_externo = str(row.get('Id', ''))
            nombre = str(row.get('Nombre', ''))
            supermercado = str(row.get('Supermercado', ''))
            categoria = str(row.get('Categoria', ''))
            formato = str(row.get('Formato', ''))
            url = str(row.get('Url', ''))
            url_imagen = str(row.get('Url_imagen', ''))
            precio = row.get('Precio')
            precio_por_unidad = row.get('Precio_por_unidad')

            # Intentar insertar el producto (si ya existe, actualizar)
            cursor.execute("""
                INSERT INTO productos (id_externo, nombre, supermercado, categoria, formato, url, url_imagen, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id_externo, supermercado)
                DO UPDATE SET
                    nombre = excluded.nombre,
                    categoria = excluded.categoria,
                    formato = excluded.formato,
                    url = excluded.url,
                    url_imagen = excluded.url_imagen,
                    fecha_actualizacion = excluded.fecha_actualizacion
            """, (id_externo, nombre, supermercado, categoria, formato, url, url_imagen, ahora))

            if cursor.rowcount == 1:
                nuevos += 1
            else:
                actualizados += 1

            # Obtener el ID interno del producto
            cursor.execute(
                "SELECT id FROM productos WHERE id_externo = ? AND supermercado = ?",
                (id_externo, supermercado)
            )
            producto_id = cursor.fetchone()[0]

            # Registrar el precio actual
            if precio is not None:
                try:
                    precio_float = float(precio)
                    precio_unidad_float = float(precio_por_unidad) if precio_por_unidad else None
                    
                    cursor.execute("""
                        INSERT INTO precios (producto_id, precio, precio_por_unidad, fecha_captura)
                        VALUES (?, ?, ?, ?)
                    """, (producto_id, precio_float, precio_unidad_float, ahora))
                    precios_registrados += 1
                except (ValueError, TypeError) as e:
                    logger.warning(f"Precio inválido para {nombre}: {e}")

        self.conn.commit()

        resumen = {
            'productos_nuevos': nuevos,
            'productos_actualizados': actualizados,
            'precios_registrados': precios_registrados
        }
        
        logger.info(
            f"Guardado: {nuevos} nuevos, {actualizados} actualizados, "
            f"{precios_registrados} precios registrados."
        )
        
        return resumen

    def buscar_productos(self, nombre=None, supermercado=None, categoria=None, limite=50):
        """
        Busca productos por nombre, supermercado y/o categoría.
        
        Args:
            nombre (str): Texto a buscar en el nombre (búsqueda parcial).
            supermercado (str): Filtrar por supermercado.
            categoria (str): Filtrar por categoría.
            limite (int): Número máximo de resultados.
        
        Returns:
            pd.DataFrame: Productos encontrados.
        """
        query = "SELECT * FROM productos WHERE 1=1"
        params = []

        if nombre:
            query += " AND nombre LIKE ?"
            params.append(f"%{nombre}%")
        if supermercado:
            query += " AND supermercado = ?"
            params.append(supermercado)
        if categoria:
            query += " AND categoria LIKE ?"
            params.append(f"%{categoria}%")
        
        query += f" ORDER BY nombre LIMIT {limite}"

        return pd.read_sql_query(query, self.conn, params=params)

    # =========================================================================
    # PRECIOS E HISTÓRICO
    # =========================================================================

    def obtener_historico_precios(self, producto_id):
        """
        Obtiene el histórico de precios de un producto.
        
        Args:
            producto_id (int): ID interno del producto.
        
        Returns:
            pd.DataFrame: Histórico con columnas precio, precio_por_unidad, fecha_captura.
        """
        query = """
            SELECT precio, precio_por_unidad, fecha_captura
            FROM precios
            WHERE producto_id = ?
            ORDER BY fecha_captura ASC
        """
        return pd.read_sql_query(query, self.conn, params=[producto_id])

    def obtener_ultimo_precio(self, producto_id):
        """
        Obtiene el último precio registrado de un producto.
        
        Args:
            producto_id (int): ID interno del producto.
        
        Returns:
            dict | None: Último precio con fecha, o None si no hay registros.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT precio, precio_por_unidad, fecha_captura
            FROM precios
            WHERE producto_id = ?
            ORDER BY fecha_captura DESC
            LIMIT 1
        """, (producto_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'precio': row['precio'],
                'precio_por_unidad': row['precio_por_unidad'],
                'fecha_captura': row['fecha_captura']
            }
        return None

    def obtener_productos_con_precio_actual(self, supermercado=None):
        """
        Obtiene todos los productos con su último precio registrado.
        Útil para el dashboard.
        
        Args:
            supermercado (str): Filtrar por supermercado (opcional).
        
        Returns:
            pd.DataFrame: Productos con su precio más reciente.
        """
        query = """
            SELECT 
                p.id, p.id_externo, p.nombre, p.supermercado, p.categoria,
                p.formato, p.url, p.url_imagen,
                pr.precio, pr.precio_por_unidad, pr.fecha_captura
            FROM productos p
            INNER JOIN precios pr ON p.id = pr.producto_id
            INNER JOIN (
                SELECT producto_id, MAX(fecha_captura) as max_fecha
                FROM precios
                GROUP BY producto_id
            ) ultimo ON pr.producto_id = ultimo.producto_id 
                     AND pr.fecha_captura = ultimo.max_fecha
        """
        params = []
        
        if supermercado:
            query += " WHERE p.supermercado = ?"
            params.append(supermercado)
        
        query += " ORDER BY p.nombre"

        return pd.read_sql_query(query, self.conn, params=params)

    # =========================================================================
    # EQUIVALENCIAS
    # =========================================================================

    def crear_equivalencia(self, nombre_comun, lista_producto_ids):
        """
        Crea un grupo de equivalencia entre productos de distintos supermercados.
        
        Args:
            nombre_comun (str): Nombre descriptivo del grupo (ej: "Coca-Cola 2L").
            lista_producto_ids (list): Lista de IDs internos de productos equivalentes.
        """
        cursor = self.conn.cursor()
        
        for producto_id in lista_producto_ids:
            cursor.execute("""
                INSERT OR IGNORE INTO equivalencias (nombre_comun, producto_id)
                VALUES (?, ?)
            """, (nombre_comun, producto_id))
        
        self.conn.commit()
        logger.info(f"Equivalencia creada: '{nombre_comun}' con {len(lista_producto_ids)} productos.")

    def obtener_equivalencias(self, nombre_comun):
        """
        Obtiene todos los productos de un grupo de equivalencia.
        
        Args:
            nombre_comun (str): Nombre del grupo.
        
        Returns:
            pd.DataFrame: Productos del grupo con su último precio.
        """
        query = """
            SELECT 
                e.nombre_comun, p.id, p.nombre, p.supermercado, p.formato,
                pr.precio, pr.fecha_captura
            FROM equivalencias e
            INNER JOIN productos p ON e.producto_id = p.id
            LEFT JOIN precios pr ON p.id = pr.producto_id
            LEFT JOIN (
                SELECT producto_id, MAX(fecha_captura) as max_fecha
                FROM precios
                GROUP BY producto_id
            ) ultimo ON pr.producto_id = ultimo.producto_id 
                     AND pr.fecha_captura = ultimo.max_fecha
            WHERE e.nombre_comun = ?
            ORDER BY pr.precio ASC
        """
        return pd.read_sql_query(query, self.conn, params=[nombre_comun])

    def obtener_historico_equivalencia(self, nombre_comun):
        """
        Obtiene el histórico de precios de todos los productos de una equivalencia.
        Ideal para el gráfico comparativo del dashboard.
        
        Args:
            nombre_comun (str): Nombre del grupo de equivalencia.
        
        Returns:
            pd.DataFrame: Histórico con columnas: supermercado, precio, fecha_captura.
        """
        query = """
            SELECT 
                p.supermercado, p.nombre, pr.precio, pr.fecha_captura
            FROM equivalencias e
            INNER JOIN productos p ON e.producto_id = p.id
            INNER JOIN precios pr ON p.id = pr.producto_id
            WHERE e.nombre_comun = ?
            ORDER BY pr.fecha_captura ASC
        """
        return pd.read_sql_query(query, self.conn, params=[nombre_comun])

    def listar_grupos_equivalencia(self):
        """
        Lista todos los grupos de equivalencia existentes.
        
        Returns:
            list: Lista de nombres comunes de grupos.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT nombre_comun FROM equivalencias ORDER BY nombre_comun")
        return [row['nombre_comun'] for row in cursor.fetchall()]

    # =========================================================================
    # FAVORITOS
    # =========================================================================

    def agregar_favorito(self, producto_id):
        """Marca un producto como favorito."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO favoritos (producto_id) VALUES (?)",
            (producto_id,)
        )
        self.conn.commit()

    def eliminar_favorito(self, producto_id):
        """Quita un producto de favoritos."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM favoritos WHERE producto_id = ?",
            (producto_id,)
        )
        self.conn.commit()

    def obtener_favoritos(self):
        """
        Obtiene todos los productos favoritos con su último precio.
        
        Returns:
            pd.DataFrame: Favoritos con precio actual.
        """
        query = """
            SELECT 
                p.id, p.nombre, p.supermercado, p.formato, p.url_imagen,
                pr.precio, pr.precio_por_unidad, pr.fecha_captura
            FROM favoritos f
            INNER JOIN productos p ON f.producto_id = p.id
            LEFT JOIN precios pr ON p.id = pr.producto_id
            LEFT JOIN (
                SELECT producto_id, MAX(fecha_captura) as max_fecha
                FROM precios
                GROUP BY producto_id
            ) ultimo ON pr.producto_id = ultimo.producto_id 
                     AND pr.fecha_captura = ultimo.max_fecha
            ORDER BY p.supermercado, p.nombre
        """
        return pd.read_sql_query(query, self.conn)

    # =========================================================================
    # ESTADÍSTICAS
    # =========================================================================

    def obtener_estadisticas(self):
        """
        Obtiene estadísticas generales de la base de datos.
        
        Returns:
            dict: Estadísticas del sistema.
        """
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM productos")
        total_productos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM precios")
        total_registros_precios = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT supermercado) FROM productos")
        total_supermercados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT nombre_comun) FROM equivalencias")
        total_equivalencias = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM favoritos")
        total_favoritos = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(fecha_captura), MAX(fecha_captura) FROM precios")
        row = cursor.fetchone()
        primera_captura = row[0]
        ultima_captura = row[1]

        cursor.execute("""
            SELECT supermercado, COUNT(*) as total 
            FROM productos 
            GROUP BY supermercado 
            ORDER BY total DESC
        """)
        productos_por_supermercado = {row['supermercado']: row['total'] for row in cursor.fetchall()}

        return {
            'total_productos': total_productos,
            'total_registros_precios': total_registros_precios,
            'total_supermercados': total_supermercados,
            'total_equivalencias': total_equivalencias,
            'total_favoritos': total_favoritos,
            'primera_captura': primera_captura,
            'ultima_captura': ultima_captura,
            'productos_por_supermercado': productos_por_supermercado
        }
