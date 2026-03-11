# -*- coding: utf-8 -*-
"""Tests unitarios para dia.py — ejecutar con: python -m pytest test_dia.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dia import gestion_dia, _procesar_nodo, _get_ids_categorys, _get_products_by_category  # noqa: E402

# Dia usa nombres de columna propios: Precio_unidad, URL, URL_imagen
COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_unidad',
    'Formato', 'Categoria', 'Supermercado', 'URL', 'URL_imagen'
]


class TestGestionDia:

    @patch.dict(os.environ, {'COOKIE_DIA': 'TU_COOKIE_DIA'})
    def test_cookie_por_defecto_devuelve_df_vacio(self):
        """Si la cookie tiene el valor por defecto, devuelve DataFrame vacío."""
        resultado = gestion_dia()
        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty

    @patch.dict(os.environ, {'COOKIE_DIA': ''})
    def test_cookie_vacia_devuelve_df_vacio(self):
        """Si la cookie está vacía, devuelve DataFrame vacío."""
        resultado = gestion_dia()
        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty


class TestProcesarNodoDia:

    def test_nodo_simple(self):
        """Procesa un nodo sin hijos."""
        nodo = {'categoria1': {'parameter': 'param1', 'path': '/ruta/categoria1'}}
        resultado = _procesar_nodo(nodo)
        assert len(resultado) >= 1
        assert resultado[0][0] == 'categoria1'

    def test_nodo_con_hijos(self):
        """Procesa un nodo con children — devuelve padre e hijo."""
        nodo = {
            'padre': {
                'parameter': 'param_padre', 'path': '/ruta/padre',
                'children': {'hijo': {'parameter': 'param_hijo', 'path': '/ruta/padre/hijo'}}
            }
        }
        resultado = _procesar_nodo(nodo)
        assert len(resultado) >= 2

    def test_nodo_vacio(self):
        """Nodo vacío devuelve lista vacía."""
        assert _procesar_nodo({}) == []


class TestGetIdsCategorysDia:

    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    @patch('dia.requests.get')
    def test_error_de_red_devuelve_lista_vacia(self, mock_get):
        """Error de red → lista vacía."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Sin conexión")
        resultado = _get_ids_categorys()
        assert resultado == []

    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    @patch('dia.requests.get')
    def test_respuesta_no_json_devuelve_lista_vacia(self, mock_get):
        """Respuesta no-JSON (cookie caducada) → lista vacía."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(side_effect=ValueError("No JSON"))
        )
        resultado = _get_ids_categorys()
        assert resultado == []


class TestGetProductsByCategoryDia:

    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    @patch('dia.time.sleep')
    @patch('dia.requests.get')
    def test_categoria_con_productos(self, mock_get, mock_sleep):
        """Extrae y mapea correctamente los productos de una categoría."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(return_value={'plp_items': [{
                'object_id': '001', 'display_name': 'Leche entera Dia',
                'prices_price': 0.89, 'prices_price_per_unit': 0.89,
                'prices_measure_unit': '1L', 'url': '/producto/leche-entera',
                'image': '/img/leche.jpg',
            }]})
        )
        resultado = _get_products_by_category(['/test/categoria'])
        assert isinstance(resultado, pd.DataFrame)
        assert not resultado.empty
        assert resultado.iloc[0]['Nombre'] == 'Leche entera Dia'
        assert resultado.iloc[0]['Supermercado'] == 'Dia'

    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    @patch('dia.time.sleep')
    @patch('dia.requests.get')
    def test_error_en_categoria_no_rompe_ejecucion(self, mock_get, mock_sleep):
        """Un error en una categoría no interrumpe las demás."""
        mock_get.side_effect = Exception("Error de red")
        resultado = _get_products_by_category(['/cat1', '/cat2'])
        assert isinstance(resultado, pd.DataFrame)

    def test_lista_vacia_devuelve_df_vacio(self):
        """Sin categorías, devuelve DataFrame vacío."""
        resultado = _get_products_by_category([])
        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty

    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    @patch('dia.time.sleep')
    @patch('dia.requests.get')
    def test_columnas_estandar(self, mock_get, mock_sleep):
        """El DataFrame tiene las columnas estándar del proyecto."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(return_value={'plp_items': [{
                'object_id': '001', 'display_name': 'Test', 'prices_price': 1.0,
                'prices_price_per_unit': 1.0, 'prices_measure_unit': 'kg',
                'url': '/test', 'image': '/test.jpg',
            }]})
        )
        resultado = _get_products_by_category(['/test'])
        for col in COLUMNAS_ESPERADAS:
            assert col in resultado.columns, f"Falta la columna '{col}'"
