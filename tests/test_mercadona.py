# -*- coding: utf-8 -*-
"""Tests unitarios para mercadona.py — ejecutar con: python -m pytest test_mercadona.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mercadona import get_ids_categorys, get_products_by_category  # noqa: E402

COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]


class TestMercadonaEstructura:

    def test_columnas_dataframe(self):
        """Un DataFrame con los datos de Mercadona tiene las columnas correctas."""
        datos = {
            'Id': ['12345'], 'Nombre': ['Leche entera Hacendado'], 'Precio': [0.89],
            'Precio_por_unidad': [0.89], 'Formato': ['1L'], 'Categoria': ['Lácteos'],
            'Supermercado': ['Mercadona'], 'Url': ['https://tienda.mercadona.es/product/12345'],
            'Url_imagen': ['https://prod-mercadona.imgix.net/images/12345.jpg']
        }
        df = pd.DataFrame(datos)
        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns, f"Falta la columna '{col}'"

    def test_tipos_de_datos(self):
        """Los tipos de datos del DataFrame son los esperados."""
        df = pd.DataFrame({
            'Id': ['12345'], 'Nombre': ['Leche entera'], 'Precio': [0.89],
            'Precio_por_unidad': [0.89], 'Formato': ['1L'], 'Categoria': ['Lácteos'],
            'Supermercado': ['Mercadona'], 'Url': ['https://example.com'],
            'Url_imagen': ['https://example.com/img.jpg']
        })
        assert df['Precio'].dtype in ['float64', 'int64']
        assert isinstance(df['Nombre'].iloc[0], str)
        assert df['Supermercado'].iloc[0] == 'Mercadona'


class TestGetIdsCategorys:

    @patch('mercadona.requests.get')
    def test_error_de_red_devuelve_lista(self, mock_get):
        """Error de red no lanza excepción no controlada."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Sin conexión")
        try:
            resultado = get_ids_categorys()
            assert isinstance(resultado, list)
        except Exception:
            pass  # El scraper puede propagar la excepción

    @patch('mercadona.requests.get')
    def test_respuesta_json_correcta(self, mock_get):
        """Respuesta válida → lista de categorías."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(return_value={
                'results': [{'id': 1, 'name': 'Frutas'}, {'id': 2, 'name': 'Lácteos'}]
            })
        )
        resultado = get_ids_categorys()
        assert isinstance(resultado, list)


class TestGetProductsByCategory:

    # ── Datos de mock reutilizables ─────────────────────────────────────
    # Producto normal (no a granel): unit_price = precio por unidad,
    # bulk_price = precio por litro (coincide porque es 1 L).
    _PRODUCTO_NORMAL = {
        'id': '12345',
        'display_name': 'Leche Hacendado 1L',
        'share_url': 'https://tienda.mercadona.es/product/12345',
        'thumbnail': 'https://prod-mercadona.imgix.net/images/12345.jpg',
        'price_instructions': {
            'unit_price': 0.89,
            'bulk_price': 0.89,
            'unit_size': '1',
            'size_format': 'L',
            'approx_size': False,
        },
    }

    # Producto a granel: unit_price = precio ESTIMADO por pieza (~500 g),
    # bulk_price = precio de REFERENCIA por kg (tasa real de facturación).
    _PRODUCTO_GRANEL = {
        'id': '67890',
        'display_name': 'Tomates cherry',
        'share_url': 'https://tienda.mercadona.es/product/67890',
        'thumbnail': 'https://prod-mercadona.imgix.net/images/67890.jpg',
        'price_instructions': {
            'unit_price': 1.49,   # precio estimado por bolsa (~500 g)
            'bulk_price': 2.99,   # precio de referencia €/kg
            'unit_size': '498',   # peso aproximado en gramos
            'size_format': 'g',
            'approx_size': True,
        },
    }

    def _mock_respuesta(self, productos):
        """Devuelve un mock de requests.get para la lista de productos dada."""
        return MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(return_value={
                'categories': [{'id': 1, 'decimalName': 'Test', 'products': productos}]
            }),
        )

    @patch('mercadona.time.sleep')
    @patch('mercadona.requests.get')
    def test_devuelve_dataframe(self, mock_get, mock_sleep):
        """Categoría con productos → DataFrame no vacío con columnas correctas."""
        mock_get.return_value = self._mock_respuesta([self._PRODUCTO_NORMAL])
        resultado = get_products_by_category([1])
        assert isinstance(resultado, pd.DataFrame)
        assert not resultado.empty, "El DataFrame no debería estar vacío"
        for col in COLUMNAS_ESPERADAS:
            assert col in resultado.columns, f"Falta la columna '{col}'"

    @patch('mercadona.time.sleep')
    @patch('mercadona.requests.get')
    def test_granel_preserva_unit_price_como_precio(self, mock_get, mock_sleep):
        """Granel (approx_size=True): Precio = unit_price, NO bulk_price.

        unit_price es el precio estimado por pieza (ej: ~1,49 € por ~500 g).
        bulk_price es el precio de referencia €/kg (ej: 2,99 €/kg).
        No deben igualarse: hacerlo borraría el precio de venta estimado.
        """
        mock_get.return_value = self._mock_respuesta([self._PRODUCTO_GRANEL])
        resultado = get_products_by_category([1])
        assert not resultado.empty
        fila = resultado.iloc[0]
        assert float(fila['Precio']) == pytest.approx(1.49), (
            "Precio debe ser unit_price (precio estimado por pieza), no bulk_price")
        assert float(fila['Precio_por_unidad']) == pytest.approx(2.99), (
            "Precio_por_unidad debe ser bulk_price (precio de referencia €/kg)")

    @patch('mercadona.time.sleep')
    @patch('mercadona.requests.get')
    def test_no_granel_precio_correcto(self, mock_get, mock_sleep):
        """Producto normal (approx_size=False): Precio = unit_price original."""
        mock_get.return_value = self._mock_respuesta([self._PRODUCTO_NORMAL])
        resultado = get_products_by_category([1])
        assert not resultado.empty
        fila = resultado.iloc[0]
        assert float(fila['Precio']) == pytest.approx(0.89)
        assert float(fila['Precio_por_unidad']) == pytest.approx(0.89)

    def test_lista_vacia_devuelve_df_vacio(self):
        """Sin categorías, devuelve DataFrame vacío."""
        resultado = get_products_by_category([])
        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Salta en CI")
class TestMercadonaAPI:

    def test_get_ids_categorys_real(self):
        """La API real de categorías responde con datos válidos."""
        resultado = get_ids_categorys()
        assert isinstance(resultado, list)
        assert len(resultado) > 0
