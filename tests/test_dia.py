# -*- coding: utf-8 -*-

"""
Tests unitarios para scraper/dia.py

Ejecutar con:
    python -m pytest tests/test_dia.py -v

Estos tests verifican la lógica interna del scraper sin hacer
peticiones reales a la API (se mockean con unittest.mock).
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import os


class TestGestionDia(unittest.TestCase):
    """Tests para la función principal gestion_dia()."""

    @patch.dict(os.environ, {'COOKIE_DIA': 'TU_COOKIE_DIA'})
    def test_sin_cookie_configurada_devuelve_df_vacio(self):
        """Si la cookie tiene el valor por defecto, devuelve DataFrame vacío."""
        from scraper.dia import gestion_dia
        resultado = gestion_dia()
        self.assertIsInstance(resultado, pd.DataFrame)
        self.assertTrue(resultado.empty)

    @patch.dict(os.environ, {'COOKIE_DIA': ''})
    def test_cookie_vacia_devuelve_df_vacio(self):
        """Si la cookie está vacía, devuelve DataFrame vacío."""
        from scraper.dia import gestion_dia
        resultado = gestion_dia()
        self.assertIsInstance(resultado, pd.DataFrame)
        self.assertTrue(resultado.empty)


class TestGetIdsCategorysDia(unittest.TestCase):
    """Tests para get_ids_categorys() de Dia."""

    @patch('scraper.dia.requests.get')
    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    def test_error_de_red_devuelve_lista_vacia(self, mock_get):
        """Si hay un error de red, devuelve lista vacía."""
        from scraper.dia import get_ids_categorys
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Sin conexión")
        resultado = get_ids_categorys()
        self.assertEqual(resultado, [])

    @patch('scraper.dia.requests.get')
    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    def test_respuesta_no_json_devuelve_lista_vacia(self, mock_get):
        """Si la respuesta no es JSON (cookie caducada), devuelve lista vacía."""
        from scraper.dia import get_ids_categorys
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("No JSON")
        mock_get.return_value = mock_response
        resultado = get_ids_categorys()
        self.assertEqual(resultado, [])


class TestProcesarNodoDia(unittest.TestCase):
    """Tests para la función recursiva _procesar_nodo()."""

    def test_nodo_simple(self):
        """Procesa correctamente un nodo sin hijos."""
        from scraper.dia import _procesar_nodo
        nodo = {
            'categoria1': {
                'parameter': 'param1',
                'path': '/ruta/categoria1',
            }
        }
        resultado = _procesar_nodo(nodo)
        self.assertTrue(len(resultado) >= 1)
        self.assertEqual(resultado[0][0], 'categoria1')

    def test_nodo_con_hijos(self):
        """Procesa correctamente un nodo con children."""
        from scraper.dia import _procesar_nodo
        nodo = {
            'padre': {
                'parameter': 'param_padre',
                'path': '/ruta/padre',
                'children': {
                    'hijo': {
                        'parameter': 'param_hijo',
                        'path': '/ruta/padre/hijo',
                    }
                }
            }
        }
        resultado = _procesar_nodo(nodo)
        # Debe contener tanto el padre como el hijo
        self.assertTrue(len(resultado) >= 2)

    def test_nodo_vacio(self):
        """Un nodo vacío devuelve lista vacía."""
        from scraper.dia import _procesar_nodo
        resultado = _procesar_nodo({})
        self.assertEqual(resultado, [])


class TestGetProductsByCategoryDia(unittest.TestCase):
    """Tests para get_products_by_category() de Dia."""

    @patch('scraper.dia.requests.get')
    @patch('scraper.dia.time.sleep')
    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    def test_categoria_con_productos(self, mock_sleep, mock_get):
        """Extrae productos correctamente de una categoría."""
        from scraper.dia import get_products_by_category

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'plp_items': [
                {
                    'object_id': '001',
                    'display_name': 'Leche entera Dia',
                    'prices_price': 0.89,
                    'prices_price_per_unit': 0.89,
                    'prices_measure_unit': '1L',
                    'url': '/producto/leche-entera',
                    'image': '/img/leche.jpg',
                }
            ]
        }
        mock_get.return_value = mock_response

        resultado = get_products_by_category(['/test/categoria'])

        self.assertIsInstance(resultado, pd.DataFrame)
        self.assertFalse(resultado.empty)
        self.assertEqual(resultado.iloc[0]['Nombre'], 'Leche entera Dia')
        self.assertEqual(resultado.iloc[0]['Supermercado'], 'Dia')

    @patch('scraper.dia.requests.get')
    @patch('scraper.dia.time.sleep')
    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    def test_error_en_categoria_no_rompe_ejecucion(self, mock_sleep, mock_get):
        """Si una categoría falla, continúa con las siguientes."""
        from scraper.dia import get_products_by_category

        mock_get.side_effect = Exception("Error de red")

        resultado = get_products_by_category(['/cat1', '/cat2'])
        self.assertIsInstance(resultado, pd.DataFrame)
        self.assertTrue(resultado.empty)

    def test_lista_vacia_devuelve_df_vacio(self):
        """Si no hay categorías, devuelve DataFrame vacío."""
        from scraper.dia import get_products_by_category
        resultado = get_products_by_category([])
        self.assertIsInstance(resultado, pd.DataFrame)
        self.assertTrue(resultado.empty)


class TestColumnasEstandar(unittest.TestCase):
    """Verifica que el DataFrame de Dia tiene las columnas estándar."""

    @patch('scraper.dia.requests.get')
    @patch('scraper.dia.time.sleep')
    @patch.dict(os.environ, {'COOKIE_DIA': 'cookie_valida_test'})
    def test_columnas_estandar(self, mock_sleep, mock_get):
        """El DataFrame debe tener las mismas columnas que los otros scrapers."""
        from scraper.dia import get_products_by_category

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'plp_items': [
                {
                    'object_id': '001',
                    'display_name': 'Test',
                    'prices_price': 1.0,
                    'prices_price_per_unit': 1.0,
                    'prices_measure_unit': 'kg',
                    'url': '/test',
                    'image': '/test.jpg',
                }
            ]
        }
        mock_get.return_value = mock_response

        resultado = get_products_by_category(['/test'])

        columnas_esperadas = [
            'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
            'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
        ]
        for col in columnas_esperadas:
            self.assertIn(col, resultado.columns, f"Falta la columna '{col}'")


if __name__ == '__main__':
    unittest.main()
