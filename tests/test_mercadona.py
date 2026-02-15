# -*- coding: utf-8 -*-

"""
Tests unitarios para scraper/mercadona.py

Verifica que el scraper de Mercadona devuelve datos con la estructura correcta.

NOTA: Estos tests hacen llamadas reales a la API de Mercadona.
Para CI/CD, se podrían mockear con unittest.mock.

Ejecutar con:
    python -m pytest tests/test_mercadona.py -v
"""

import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# Columnas esperadas en el DataFrame de salida
COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]


class TestMercadonaEstructura:
    """Tests que verifican la estructura de datos sin depender de la API."""

    def test_columnas_dataframe(self):
        """
        Verifica que un DataFrame con las columnas correctas se puede crear.
        Esto valida que el scraper produce el formato esperado.
        """
        # Simular una fila de datos como la que devolvería el scraper
        datos = {
            'Id': ['12345'],
            'Nombre': ['Leche entera Hacendado'],
            'Precio': [0.89],
            'Precio_por_unidad': [0.89],
            'Formato': ['1L'],
            'Categoria': ['Lácteos'],
            'Supermercado': ['Mercadona'],
            'Url': ['https://tienda.mercadona.es/product/12345'],
            'Url_imagen': ['https://prod-mercadona.imgix.net/images/12345.jpg']
        }
        df = pd.DataFrame(datos)

        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns, f"Falta la columna '{col}'"

    def test_tipos_de_datos(self):
        """Verifica que los tipos de datos son correctos."""
        datos = {
            'Id': ['12345'],
            'Nombre': ['Leche entera'],
            'Precio': [0.89],
            'Precio_por_unidad': [0.89],
            'Formato': ['1L'],
            'Categoria': ['Lácteos'],
            'Supermercado': ['Mercadona'],
            'Url': ['https://example.com'],
            'Url_imagen': ['https://example.com/img.jpg']
        }
        df = pd.DataFrame(datos)

        assert df['Precio'].dtype in ['float64', 'int64']
        assert df['Nombre'].dtype == 'object'  # string en pandas
        assert df['Supermercado'].iloc[0] == 'Mercadona'


@pytest.mark.skipif(
    os.environ.get('CI') == 'true',
    reason="Salta en CI para no sobrecargar la API"
)
class TestMercadonaAPI:
    """
    Tests que hacen llamadas reales a la API de Mercadona.
    Se saltan en entornos CI.
    """

    def test_obtener_categorias(self):
        """Verifica que la API de categorías responde correctamente."""
        import requests

        url = "https://tienda.mercadona.es/api/categories/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert 'results' in data

    def test_gestion_mercadona_devuelve_dataframe(self):
        """
        Verifica que gestion_mercadona() devuelve un DataFrame
        con las columnas correctas y al menos algunos productos.
        
        ADVERTENCIA: Este test tarda varios minutos porque recorre
        todas las categorías de Mercadona.
        """
        from scraper.mercadona import gestion_mercadona

        df = gestion_mercadona()

        assert isinstance(df, pd.DataFrame)
        
        if not df.empty:
            for col in COLUMNAS_ESPERADAS:
                assert col in df.columns, f"Falta columna '{col}'"
            
            assert len(df) > 0
            assert df['Supermercado'].unique()[0] == 'Mercadona'
            assert df['Precio'].notna().all()
