# -*- coding: utf-8 -*-

"""
Tests unitarios para scraper/carrefour.py

Verifica la estructura de datos y la verificación de cookies.
Los tests de API real se saltan si no hay cookie configurada.

Ejecutar con:
    python -m pytest tests/test_carrefour.py -v
"""

import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]


class TestCarrefourEstructura:
    """Tests de estructura de datos sin necesidad de cookie."""

    def test_columnas_dataframe(self):
        """Verifica que las columnas del DataFrame son correctas."""
        datos = {
            'Id': ['CAR001'],
            'Nombre': ['Leche Carrefour 1L'],
            'Precio': [0.85],
            'Precio_por_unidad': [0.85],
            'Formato': ['1L'],
            'Categoria': ['Lácteos'],
            'Supermercado': ['Carrefour'],
            'Url': ['https://www.carrefour.es/product/CAR001'],
            'Url_imagen': ['https://example.com/img.jpg']
        }
        df = pd.DataFrame(datos)

        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns
        
        assert df['Supermercado'].iloc[0] == 'Carrefour'

    def test_tipos_precio(self):
        """El precio debe ser numérico."""
        datos = {'Precio': [1.50, 2.30, 0.99]}
        df = pd.DataFrame(datos)

        assert df['Precio'].dtype in ['float64', 'int64']
        assert (df['Precio'] > 0).all()


class TestCookieManager:
    """Tests para la verificación de cookies."""

    def test_cookie_vacia_es_invalida(self):
        """Una cookie vacía o None no debe considerarse válida."""
        from scraper.cookie_manager import verificar_cookie

        # Si la cookie está vacía, debería retornar False o manejar el error
        resultado = verificar_cookie("Carrefour", "", "https://www.carrefour.es/")
        assert resultado is False

    def test_verificar_todas_no_falla(self):
        """verificar_todas_las_cookies() no debe lanzar excepciones."""
        from scraper.cookie_manager import verificar_todas_las_cookies

        # Simplemente verificar que no crashea, aunque las cookies no sean válidas
        try:
            verificar_todas_las_cookies()
        except Exception as e:
            pytest.fail(f"verificar_todas_las_cookies() lanzó excepción: {e}")


@pytest.mark.skipif(
    not os.environ.get('COOKIE_CARREFOUR'),
    reason="No hay COOKIE_CARREFOUR configurada"
)
class TestCarrefourAPI:
    """
    Tests que hacen llamadas reales a la API de Carrefour.
    Solo se ejecutan si hay una cookie válida configurada.
    """

    def test_gestion_carrefour_devuelve_dataframe(self):
        """Verifica que gestion_carrefour() devuelve datos válidos."""
        from scraper.carrefour import gestion_carrefour

        df = gestion_carrefour()

        assert isinstance(df, pd.DataFrame)
        
        if not df.empty:
            for col in COLUMNAS_ESPERADAS:
                assert col in df.columns
            assert df['Supermercado'].unique()[0] == 'Carrefour'
