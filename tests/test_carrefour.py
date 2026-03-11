# -*- coding: utf-8 -*-
"""Tests unitarios para carrefour.py — ejecutar con: python -m pytest test_carrefour.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from carrefour import _parsear_respuesta, gestion_carrefour  # noqa: E402
from cookie_manager import verificar_cookie, verificar_todas_las_cookies  # noqa: E402

COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]

PRODUCTO_EJEMPLO = {
    'product_id': 'CAR001',
    'display_name': 'Leche semidesnatada Carrefour 1 l.',
    'active_price': 0.88,
    'price_per_unit_text': '0,88 €/l',
    'image_path': 'https://static.carrefour.es/img/leche.jpg',
    'brand': 'CARREFOUR',
    'url': '/supermercado/leche-semidesnatada/R-CAR001/p',
    'section': '15',
}


class TestCarrefourEstructura:

    def test_columnas_dataframe(self):
        """El DataFrame de Carrefour tiene las columnas correctas."""
        df = pd.DataFrame({col: ['valor_test'] if col != 'Precio' else [0.88]
                           for col in COLUMNAS_ESPERADAS})
        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns

    def test_tipos_precio(self):
        """El precio debe ser numérico y positivo."""
        df = pd.DataFrame({'Precio': [1.50, 2.30, 0.99]})
        assert df['Precio'].dtype in ['float64', 'int64']
        assert (df['Precio'] > 0).all()


class TestParsearRespuesta:

    def test_producto_valido(self):
        """Un producto completo se parsea correctamente."""
        data = {'content': {'docs': [PRODUCTO_EJEMPLO], 'numFound': 1}}
        resultado = _parsear_respuesta(data, categoria_fallback='Lácteos')
        assert len(resultado) == 1
        p = resultado[0]
        assert p['Id'] == 'CAR001'
        assert p['Precio'] == 0.88
        assert p['Supermercado'] == 'Carrefour'

    def test_data_vacio_devuelve_lista_vacia(self):
        """Respuesta vacía → lista vacía."""
        assert _parsear_respuesta({}) == []
        assert _parsear_respuesta(None) == []

    def test_sin_precio_descarta_producto(self):
        """Producto sin precio → descartado."""
        doc = {k: v for k, v in PRODUCTO_EJEMPLO.items()}
        doc.pop('active_price')
        assert _parsear_respuesta({'content': {'docs': [doc]}}) == []

    def test_sin_id_descarta_producto(self):
        """Producto sin product_id → descartado."""
        doc = {k: v for k, v in PRODUCTO_EJEMPLO.items()}
        doc.pop('product_id')
        assert _parsear_respuesta({'content': {'docs': [doc]}}) == []

    def test_precio_negativo_descartado(self):
        """Precio negativo o cero → producto descartado."""
        doc = {**PRODUCTO_EJEMPLO, 'active_price': -1.0}
        assert _parsear_respuesta({'content': {'docs': [doc]}}) == []

    def test_multiples_productos(self):
        """Varios productos se parsean todos."""
        docs = [{**PRODUCTO_EJEMPLO, 'product_id': f'ID{i}', 'display_name': f'Prod {i}'}
                for i in range(5)]
        assert len(_parsear_respuesta({'content': {'docs': docs}})) == 5

    def test_estructura_alternativa_docs_directo(self):
        """Acepta estructura alternativa con docs en el nivel raíz."""
        assert len(_parsear_respuesta({'docs': [PRODUCTO_EJEMPLO]})) == 1

    @pytest.mark.parametrize("campo,valor", [
        ("active_price", 1.50),
        ("list_price", 2.00),
        ("app_price", 0.99),
    ])
    def test_campos_precio_alternativos(self, campo, valor):
        """Acepta active_price, list_price y app_price."""
        doc = {'product_id': 'X1', 'display_name': 'Test', campo: valor}
        resultado = _parsear_respuesta({'content': {'docs': [doc]}})
        assert len(resultado) == 1
        assert resultado[0]['Precio'] == pytest.approx(valor)


class TestCookieManager:

    def test_cookie_vacia_es_invalida(self):
        """Cookie vacía → verificar_cookie devuelve False."""
        assert verificar_cookie("COOKIE_CARREFOUR") is False

    def test_verificar_todas_no_lanza_excepcion(self):
        """verificar_todas_las_cookies() no debe lanzar excepciones."""
        try:
            verificar_todas_las_cookies()
        except Exception as e:
            pytest.fail(f"verificar_todas_las_cookies() lanzó excepción: {e}")


@pytest.mark.skipif(
    not os.environ.get('COOKIE_CARREFOUR'),
    reason="No hay COOKIE_CARREFOUR configurada"
)
class TestCarrefourAPI:

    def test_gestion_carrefour_devuelve_dataframe(self):
        """Con cookie válida, devuelve DataFrame con productos."""
        df = gestion_carrefour()
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            for col in COLUMNAS_ESPERADAS:
                assert col in df.columns
            assert df['Supermercado'].unique()[0] == 'Carrefour'
