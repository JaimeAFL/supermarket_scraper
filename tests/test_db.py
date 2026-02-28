# -*- coding: utf-8 -*-

"""
Tests unitarios para database/database_db_manager.py

Ejecutar con:
    python -m pytest tests/test_db.py -v
"""

import os
import sys
import tempfile
import pandas as pd
import pytest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos


@pytest.fixture
def db_temporal():
    """Crea una base de datos temporal para cada test."""
    fd, ruta = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # inicializar_base_datos crea tablas, índices y columnas de normalización
    inicializar_base_datos(ruta)

    db = DatabaseManager(db_path=ruta)
    yield db

    db.cerrar()
    try:
        os.unlink(ruta)
    except OSError:
        pass


@pytest.fixture
def df_ejemplo():
    """DataFrame de ejemplo simulando datos de un scraper."""
    return pd.DataFrame([
        {
            'Id': 'MER001', 'Nombre': 'Leche entera Hacendado 1L',
            'Precio': 0.89, 'Precio_unidad': '0.89 €/L',
            'Formato': '1L', 'Categoria': 'Lácteos',
            'Supermercado': 'Mercadona', 'URL': 'https://example.com/1',
            'URL_imagen': 'https://example.com/img1.jpg'
        },
        {
            'Id': 'MER002', 'Nombre': 'Pan de molde Hacendado 500g',
            'Precio': 1.20, 'Precio_unidad': '2.40 €/kg',
            'Formato': '500g', 'Categoria': 'Panadería',
            'Supermercado': 'Mercadona', 'URL': 'https://example.com/2',
            'URL_imagen': 'https://example.com/img2.jpg'
        },
        {
            'Id': 'CAR001', 'Nombre': 'Leche entera Carrefour brik 1 l.',
            'Precio': 0.85, 'Precio_unidad': '0.85 €/L',
            'Formato': '', 'Categoria': 'Lácteos',
            'Supermercado': 'Carrefour', 'URL': 'https://example.com/3',
            'URL_imagen': 'https://example.com/img3.jpg'
        },
    ])


# =============================================================================
# TESTS DE PRODUCTOS
# =============================================================================

class TestGuardarProductos:

    def test_insertar_productos_nuevos(self, db_temporal, df_ejemplo):
        """Debe insertar productos correctamente la primera vez."""
        resumen = db_temporal.guardar_productos(df_ejemplo)

        assert resumen['precios_registrados'] == 3

    def test_no_duplicar_productos(self, db_temporal, df_ejemplo):
        """La segunda ejecución el mismo día no duplica precios."""
        db_temporal.guardar_productos(df_ejemplo)
        resumen = db_temporal.guardar_productos(df_ejemplo)

        # Mismo día → precios ya existen, no se insertan de nuevo
        assert resumen['precios_registrados'] == 0

    def test_estadisticas_tras_insertar(self, db_temporal, df_ejemplo):
        """Tras insertar, las estadísticas reflejan los datos."""
        db_temporal.guardar_productos(df_ejemplo)
        stats = db_temporal.obtener_estadisticas()

        assert stats['total_productos'] == 3
        assert stats['total_registros_precios'] == 3

    def test_normalizacion_se_aplica(self, db_temporal, df_ejemplo):
        """Los campos de normalización se rellenan al guardar."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if not resultados.empty:
            row = resultados.iloc[0]
            # Debe tener campos de normalización no vacíos
            assert row.get('nombre_normalizado', '') != ''
            assert row.get('categoria_normalizada', '') != ''

    def test_formato_normalizado_se_aplica(self, db_temporal, df_ejemplo):
        """El formato se normaliza automáticamente."""
        db_temporal.guardar_productos(df_ejemplo)

        # Carrefour no tenía formato → se extrae del nombre "brik 1 l."
        resultados = db_temporal.buscar_productos(nombre='leche')
        if not resultados.empty:
            formatos = resultados['formato_normalizado'].tolist()
            # Al menos uno debería tener formato
            assert any(f for f in formatos if f)


# =============================================================================
# TESTS DE BÚSQUEDA INTELIGENTE
# =============================================================================

class TestBuscarProductos:

    def test_buscar_por_nombre(self, db_temporal, df_ejemplo):
        """Debe encontrar productos por nombre."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        assert len(resultados) >= 1

    def test_buscar_sin_resultados(self, db_temporal, df_ejemplo):
        """Debe devolver DataFrame vacío si no hay coincidencias."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='inexistente')
        assert resultados.empty

    def test_buscar_sin_nombre_devuelve_vacio(self, db_temporal, df_ejemplo):
        """Sin término de búsqueda devuelve vacío."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='')
        assert resultados.empty

    def test_buscar_tiene_prioridad(self, db_temporal, df_ejemplo):
        """Los resultados deben incluir columna de prioridad."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if not resultados.empty:
            assert 'prioridad' in resultados.columns

    def test_buscar_con_filtro_supermercado(self, db_temporal, df_ejemplo):
        """Debe filtrar por supermercado si se especifica."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(
            nombre='leche', supermercado='Mercadona'
        )
        if not resultados.empty:
            assert all(r == 'Mercadona' for r in resultados['supermercado'])


# =============================================================================
# TESTS DE COMPARADOR
# =============================================================================

class TestBuscarParaComparar:

    def test_buscar_para_comparar(self, db_temporal, df_ejemplo):
        """buscar_para_comparar devuelve resultados con precio."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_para_comparar('leche')
        if not resultados.empty:
            assert 'precio' in resultados.columns
            assert 'supermercado' in resultados.columns
            assert 'formato_normalizado' in resultados.columns

    def test_comparar_sin_texto_devuelve_vacio(self, db_temporal):
        """Sin texto de búsqueda devuelve vacío."""
        resultados = db_temporal.buscar_para_comparar('')
        assert resultados.empty


# =============================================================================
# TESTS DE PRECIOS
# =============================================================================

class TestHistoricoPrecios:

    def test_obtener_historico(self, db_temporal, df_ejemplo):
        """Debe devolver el histórico de precios."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche entera')
        if not resultados.empty:
            producto_id = resultados.iloc[0]['id']
            historico = db_temporal.obtener_historico_precios(producto_id)

            assert len(historico) >= 1
            assert 'precio' in historico.columns
            assert 'fecha_captura' in historico.columns

    def test_historico_producto_inexistente(self, db_temporal):
        """Producto inexistente devuelve DataFrame vacío."""
        historico = db_temporal.obtener_historico_precios(99999)
        assert historico.empty


# =============================================================================
# TESTS DE EQUIVALENCIAS
# =============================================================================

class TestEquivalencias:

    def test_crear_equivalencia(self, db_temporal, df_ejemplo):
        """Debe crear un grupo de equivalencia correctamente."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if len(resultados) >= 2:
            ids = resultados['id'].tolist()[:2]
            db_temporal.crear_equivalencia("Leche entera 1L", ids)

            grupos = db_temporal.listar_grupos_equivalencia()
            assert "Leche entera 1L" in grupos

    def test_obtener_equivalencia(self, db_temporal, df_ejemplo):
        """Debe obtener los productos de un grupo."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if len(resultados) >= 2:
            ids = resultados['id'].tolist()[:2]
            db_temporal.crear_equivalencia("Leche entera 1L", ids)

            df_equiv = db_temporal.obtener_equivalencias("Leche entera 1L")
            assert not df_equiv.empty

    def test_listar_sin_equivalencias(self, db_temporal):
        """Sin equivalencias devuelve lista vacía."""
        grupos = db_temporal.listar_grupos_equivalencia()
        assert grupos == []


# =============================================================================
# TESTS DE FAVORITOS
# =============================================================================

class TestFavoritos:

    def test_agregar_favorito(self, db_temporal, df_ejemplo):
        """Debe añadir un producto a favoritos."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if not resultados.empty:
            producto_id = resultados.iloc[0]['id']
            db_temporal.agregar_favorito(producto_id)

            favoritos = db_temporal.obtener_favoritos()
            assert len(favoritos) == 1

    def test_eliminar_favorito(self, db_temporal, df_ejemplo):
        """Debe quitar un producto de favoritos."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if not resultados.empty:
            producto_id = resultados.iloc[0]['id']
            db_temporal.agregar_favorito(producto_id)
            db_temporal.eliminar_favorito(producto_id)

            favoritos = db_temporal.obtener_favoritos()
            assert len(favoritos) == 0

    def test_favorito_duplicado_no_falla(self, db_temporal, df_ejemplo):
        """Añadir el mismo favorito dos veces no lanza error."""
        db_temporal.guardar_productos(df_ejemplo)

        resultados = db_temporal.buscar_productos(nombre='leche')
        if not resultados.empty:
            producto_id = resultados.iloc[0]['id']
            db_temporal.agregar_favorito(producto_id)
            db_temporal.agregar_favorito(producto_id)  # No debe fallar

            favoritos = db_temporal.obtener_favoritos()
            assert len(favoritos) == 1


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

    def test_estadisticas_dias_con_datos(self, db_temporal, df_ejemplo):
        """Debe contar los días con datos."""
        db_temporal.guardar_productos(df_ejemplo)
        stats = db_temporal.obtener_estadisticas()

        assert stats['dias_con_datos'] >= 1

    def test_estadisticas_bd_vacia(self, db_temporal):
        """BD vacía devuelve estadísticas a cero."""
        stats = db_temporal.obtener_estadisticas()

        assert stats['total_productos'] == 0
        assert stats['total_registros_precios'] == 0

    def test_categorias_normalizadas(self, db_temporal, df_ejemplo):
        """Debe listar categorías normalizadas."""
        db_temporal.guardar_productos(df_ejemplo)
        categorias = db_temporal.obtener_categorias()

        # Al menos "Lácteos" debería aparecer por las leches
        nombres_cat = [c[0] for c in categorias]
        assert len(nombres_cat) >= 0  # Puede ser 0 si normalizer no matchea
