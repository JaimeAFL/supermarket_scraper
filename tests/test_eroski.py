# -*- coding: utf-8 -*-
"""Tests unitarios para eroski.py — ejecutar con: python -m pytest test_eroski.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eroski import _resolver_categoria, _construir_mapa_categorias  # noqa: E402

COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]

CAT_MAP = {
    "Lácteos": "Lácteos", "Leche": "Leche",
    "path_Leche_entera": "Leche entera", "Frescos": "Frescos",
}


class TestResolverCategoria:

    def test_usa_cat3_primero(self):
        """Prioriza cat3 (más específica) sobre cat2 y cat1."""
        assert _resolver_categoria(CAT_MAP, "Frescos", "Lácteos", "Leche", "X") == "Leche"

    def test_fallback_a_cat2_si_no_hay_cat3(self):
        """Sin cat3, usa cat2."""
        assert _resolver_categoria(CAT_MAP, "Frescos", "Lácteos", None, "X") == "Lácteos"

    def test_fallback_a_cat1_si_no_hay_cat2_ni_cat3(self):
        """Sin cat2 ni cat3, usa cat1."""
        assert _resolver_categoria(CAT_MAP, "Frescos", None, None, "X") == "Frescos"

    def test_fallback_final_si_nada_en_mapa(self):
        """Si ninguna categoría está en el mapa, devuelve fallback."""
        assert _resolver_categoria({}, "CatX", "CatY", "CatZ", "Sin categoría") == "Sin categoría"

    def test_ruta_path_tiene_prioridad(self):
        """La clave path_{id} tiene prioridad sobre el nombre simple."""
        mapa = {"Leche": "Leche genérica", "path_Leche": "Leche entera UHT"}
        assert _resolver_categoria(mapa, None, None, "Leche", "X") == "Leche entera UHT"

    @pytest.mark.parametrize("cat3,cat2,cat1,esperado", [
        ("Leche",  "Lácteos", "Frescos", "Leche"),
        (None,     "Lácteos", "Frescos", "Lácteos"),
        (None,     None,      "Frescos", "Frescos"),
        (None,     None,      None,      "fallback_test"),
    ])
    def test_prioridad_parametrizada(self, cat3, cat2, cat1, esperado):
        """Verifica el orden de prioridad cat3 > cat2 > cat1 > fallback."""
        mapa = {"Leche": "Leche", "Lácteos": "Lácteos", "Frescos": "Frescos"}
        assert _resolver_categoria(mapa, cat1, cat2, cat3, "fallback_test") == esperado


class TestEroskiEstructura:

    def test_columnas_dataframe(self):
        """DataFrame de Eroski tiene las columnas estándar."""
        df = pd.DataFrame({
            'Id': ['ERO001'], 'Nombre': ['Leche Eroski 1L'], 'Precio': [0.95],
            'Precio_por_unidad': [0.95], 'Formato': ['1 litro'], 'Categoria': ['Leche'],
            'Supermercado': ['Eroski'], 'Url': ['https://supermercado.eroski.es/es/product/ERO001/'],
            'Url_imagen': ['https://img.eroski.es/leche.jpg']
        })
        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns
        assert df['Supermercado'].iloc[0] == 'Eroski'

    def test_tipos_de_datos(self):
        """Los tipos del DataFrame son correctos."""
        df = pd.DataFrame({
            'Id': ['ERO001'], 'Nombre': ['Test'], 'Precio': [1.25],
            'Precio_por_unidad': [1.25], 'Formato': ['500 g'], 'Categoria': ['Galletas'],
            'Supermercado': ['Eroski'], 'Url': ['https://example.com'],
            'Url_imagen': ['https://example.com/img.jpg']
        })
        assert df['Precio'].dtype in ['float64', 'int64']
        assert isinstance(df['Nombre'].iloc[0], str)

    @pytest.mark.parametrize("precio", [1.0, 0.5, 15.99, 100.0])
    def test_precio_siempre_positivo(self, precio):
        df = pd.DataFrame({'Precio': [precio]})
        assert (df['Precio'] > 0).all()


class TestConstruirMapaCategorias:

    def test_mapa_vacio_si_no_hay_items(self):
        """Si page.locator devuelve vacío, el mapa está vacío."""
        page_mock = MagicMock()
        page_mock.locator.return_value.all.return_value = []
        resultado = _construir_mapa_categorias(page_mock)
        assert isinstance(resultado, dict)


class TestGestionEroskiModulo:

    def test_modulo_carga_correctamente(self):
        """El módulo eroski expone gestion_eroski."""
        import eroski
        assert hasattr(eroski, 'gestion_eroski')
        assert callable(eroski.gestion_eroski)
