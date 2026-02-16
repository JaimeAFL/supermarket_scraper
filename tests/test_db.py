# -*- coding: utf-8 -*-

"""
Tests unitarios para database/db_manager.py

Ejecutar con:
    python -m pytest tests/test_db.py -v
"""

import os
import sys
import tempfile
import pandas as pd
import pytest
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos, SCHEMA

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def db_temporal():
    """Crea una base de datos temporal para cada test."""
    # Crear archivo temporal
    fd, ruta = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Inicializar esquema
    import sqlite3
    conn = sqlite3.connect(ruta)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    # Crear manager
    db = DatabaseManager(db_path=ruta)
    
    yield db
    
    # Limpiar
    db.cerrar()
    os.unlink(ruta)


@pytest.fixture
def df_ejemplo():
    """DataFrame de ejemplo simulando datos de un scraper."""
    return pd.DataFrame([
        {
            'Id': 'MER001', 'Nombre': 'Leche entera Hacendado 1L',
            'Precio': 0.89, 'Precio_por_unidad': 0.89,
            'Formato': '1L', 'Categoria': 'Lácteos',
            'Supermercado': 'Mercadona', 'Url': 'https://example.com/1',
            'Url_imagen': 'https://example.com/img1.jpg'
        },
        {
            'Id': 'MER002', 'Nombre': 'Pan de molde Hacendado',
            'Precio': 1.20, 'Precio_por_unidad': 2.40,
            'Formato': '500g', 'Categoria': 'Panadería',
            'Supermercado': 'Mercadona', 'Url': 'https://example.com/2',
            'Url_imagen': 'https://example.com/img2.jpg'
        },
        {
            'Id': 'CAR001', 'Nombre': 'Leche entera Carrefour 1L',
            'Precio': 0.85, 'Precio_por_unidad': 0.85,
            'Formato': '1L', 'Categoria': 'Lácteos',
            'Supermercado': 'Carrefour', 'Url': 'https://example.com/3',
            'Url_imagen': 'https://example.com/img3.jpg'
        },
    ])


# =============================================================================
# TESTS DE PRODUCTOS
# =============================================================================

class TestGuardarProductos:
    
    def test_insertar_productos_nuevos(self, db_temporal, df_ejemplo):
        """Debe insertar productos correctamente la primera vez."""
        resumen = db_temporal.guardar_productos(df_ejemplo)
        
        assert resumen['productos_nuevos'] == 3
        assert resumen['precios_registrados'] == 3
    
    def test_no_duplicar_productos(self, db_temporal, df_ejemplo):
        """La segunda ejecución debe actualizar, no duplicar."""
        db_temporal.guardar_productos(df_ejemplo)
        resumen = db_temporal.guardar_productos(df_ejemplo)
        
        # La segunda vez ya existen, así que no son "nuevos"
        assert resumen['productos_nuevos'] == 0 or resumen['productos_actualizados'] > 0
    
    def test_registrar_precios_en_cada_ejecucion(self, db_temporal, df_ejemplo):
        """Cada ejecución debe crear nuevos registros de precio."""
        db_temporal.guardar_productos(df_ejemplo)
        db_temporal.guardar_productos(df_ejemplo)
        
        stats = db_temporal.obtener_estadisticas()
        
        # 3 productos × 2 ejecuciones = 6 registros de precio
        assert stats['total_registros_precios'] == 6


class TestBuscarProductos:
    
    def test_buscar_por_nombre(self, db_temporal, df_ejemplo):
        """Debe encontrar productos por nombre parcial."""
        db_temporal.guardar_productos(df_ejemplo)
        
        resultados = db_temporal.buscar_productos(nombre='leche')
        assert len(resultados) == 2  # Mercadona y Carrefour
    
    def test_buscar_por_supermercado(self, db_temporal, df_ejemplo):
        """Debe filtrar por supermercado."""
        db_temporal.guardar_productos(df_ejemplo)
        
        resultados = db_temporal.buscar_productos(supermercado='Mercadona')
        assert len(resultados) == 2  # Solo los de Mercadona
    
    def test_buscar_sin_resultados(self, db_temporal, df_ejemplo):
        """Debe devolver DataFrame vacío si no hay coincidencias."""
        db_temporal.guardar_productos(df_ejemplo)
        
        resultados = db_temporal.buscar_productos(nombre='inexistente')
        assert resultados.empty


# =============================================================================
# TESTS DE PRECIOS
# =============================================================================

class TestHistoricoPrecios:
    
    def test_obtener_historico(self, db_temporal, df_ejemplo):
        """Debe devolver el histórico de precios ordenado por fecha."""
        db_temporal.guardar_productos(df_ejemplo)
        
        # Buscar el ID del primer producto
        productos = db_temporal.buscar_productos(nombre='Leche entera Hacendado')
        producto_id = productos.iloc[0]['id']
        
        historico = db_temporal.obtener_historico_precios(producto_id)
        assert len(historico) == 1
        assert historico.iloc[0]['precio'] == 0.89
    
    def test_ultimo_precio(self, db_temporal, df_ejemplo):
        """Debe devolver el último precio registrado."""
        db_temporal.guardar_productos(df_ejemplo)
        
        productos = db_temporal.buscar_productos(nombre='Pan de molde')
        producto_id = productos.iloc[0]['id']
        
        ultimo = db_temporal.obtener_ultimo_precio(producto_id)
        assert ultimo is not None
        assert ultimo['precio'] == 1.20


# =============================================================================
# TESTS DE EQUIVALENCIAS
# =============================================================================

class TestEquivalencias:
    
    def test_crear_equivalencia(self, db_temporal, df_ejemplo):
        """Debe crear un grupo de equivalencia correctamente."""
        db_temporal.guardar_productos(df_ejemplo)
        
        # IDs de las leches (Mercadona y Carrefour)
        productos = db_temporal.buscar_productos(nombre='Leche entera')
        ids = productos['id'].tolist()
        
        db_temporal.crear_equivalencia("Leche entera 1L", ids)
        
        grupos = db_temporal.listar_grupos_equivalencia()
        assert "Leche entera 1L" in grupos
    
    def test_obtener_equivalencia(self, db_temporal, df_ejemplo):
        """Debe obtener los productos de un grupo de equivalencia."""
        db_temporal.guardar_productos(df_ejemplo)
        
        productos = db_temporal.buscar_productos(nombre='Leche entera')
        ids = productos['id'].tolist()
        db_temporal.crear_equivalencia("Leche entera 1L", ids)
        
        df_equiv = db_temporal.obtener_equivalencias("Leche entera 1L")
        assert len(df_equiv) == 2


# =============================================================================
# TESTS DE FAVORITOS
# =============================================================================

class TestFavoritos:
    
    def test_agregar_favorito(self, db_temporal, df_ejemplo):
        """Debe añadir un producto a favoritos."""
        db_temporal.guardar_productos(df_ejemplo)
        
        productos = db_temporal.buscar_productos(limite=1)
        producto_id = productos.iloc[0]['id']
        
        db_temporal.agregar_favorito(producto_id)
        
        favoritos = db_temporal.obtener_favoritos()
        assert len(favoritos) == 1
    
    def test_eliminar_favorito(self, db_temporal, df_ejemplo):
        """Debe quitar un producto de favoritos."""
        db_temporal.guardar_productos(df_ejemplo)
        
        productos = db_temporal.buscar_productos(limite=1)
        producto_id = productos.iloc[0]['id']
        
        db_temporal.agregar_favorito(producto_id)
        db_temporal.eliminar_favorito(producto_id)
        
        favoritos = db_temporal.obtener_favoritos()
        assert len(favoritos) == 0


# =============================================================================
# TESTS DE ESTADÍSTICAS
# =============================================================================

class TestEstadisticas:
    
    def test_estadisticas_basicas(self, db_temporal, df_ejemplo):
        """Debe devolver estadísticas correctas."""
        db_temporal.guardar_productos(df_ejemplo)
        
        stats = db_temporal.obtener_estadisticas()
        
        assert stats['total_productos'] == 3
        assert stats['total_registros_precios'] == 3
        assert stats['total_supermercados'] == 2
        assert 'Mercadona' in stats['productos_por_supermercado']
        assert stats['productos_por_supermercado']['Mercadona'] == 2
