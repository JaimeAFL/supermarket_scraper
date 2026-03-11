# -*- coding: utf-8 -*-
"""Tests unitarios para alcampo.py — ejecutar con: python -m pytest test_alcampo.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alcampo import _categorias_fallback  # noqa: E402

COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]


class TestCategoriasFallback:

    def test_devuelve_lista_no_vacia(self):
        """El fallback tiene categorías predefinidas."""
        resultado = _categorias_fallback()
        assert isinstance(resultado, list)
        assert len(resultado) > 0

    def test_formato_de_cada_categoria(self):
        """Cada categoría es una tupla (retailer_id, nombre)."""
        for item in _categorias_fallback():
            assert isinstance(item, tuple)
            assert len(item) == 2
            retailer_id, nombre = item
            assert isinstance(retailer_id, str) and retailer_id
            assert isinstance(nombre, str) and nombre

    def test_contiene_categorias_esenciales(self):
        """El fallback incluye categorías alimentarias básicas."""
        nombres = [nombre for _, nombre in _categorias_fallback()]
        for esencial in ['Frutas', 'Leche', 'Aceite']:
            assert any(esencial in n for n in nombres), f"Falta categoría '{esencial}'"


class TestMapeoProductoAlcampo:
    """Verifica la lógica de transformación de raw → dict normalizado
    replicando el bucle interno de _extraer_categoria_browser."""

    def _mapear(self, raw: dict, cat_nombre: str = "Lácteos"):
        pid = raw.get("id", "")
        nombre = raw.get("name", "")
        if not pid or not nombre:
            return None
        try:
            precio = float(raw.get("price", 0))
        except (ValueError, TypeError):
            return None
        if precio <= 0:
            return None
        try:
            precio_u = float(raw.get("unitPrice", precio))
        except (ValueError, TypeError):
            precio_u = precio
        cat_real = raw.get("category", "") or cat_nombre
        return {
            "Id": str(pid), "Nombre": nombre, "Precio": precio,
            "Precio_por_unidad": precio_u, "Formato": raw.get("size", ""),
            "Categoria": cat_real, "Supermercado": "Alcampo",
            "Url": f"https://compraonline.alcampo.es/products/{pid}",
            "Url_imagen": raw.get("image", ""), "Marca": raw.get("brand", ""),
        }

    def test_producto_valido(self):
        raw = {"id": "ALC001", "name": "Leche Entera 1L", "price": 0.89,
               "unitPrice": 0.89, "brand": "ALCAMPO", "size": "1L",
               "image": "https://img.alcampo.es/leche.jpg", "category": "Leche"}
        resultado = self._mapear(raw)
        assert resultado is not None
        assert resultado['Id'] == 'ALC001'
        assert resultado['Precio'] == 0.89
        assert resultado['Supermercado'] == 'Alcampo'
        for col in COLUMNAS_ESPERADAS:
            assert col in resultado

    def test_sin_id_descartado(self):
        assert self._mapear({"name": "Leche", "price": 0.89}) is None

    def test_sin_nombre_descartado(self):
        assert self._mapear({"id": "001", "price": 0.89}) is None

    def test_precio_cero_descartado(self):
        assert self._mapear({"id": "001", "name": "Test", "price": 0}) is None

    def test_precio_negativo_descartado(self):
        assert self._mapear({"id": "001", "name": "Test", "price": -1.5}) is None

    def test_categoria_fallback_desde_parametro(self):
        """Sin category en raw, usa el nombre de categoría del parámetro."""
        raw = {"id": "001", "name": "Producto", "price": 1.0, "category": ""}
        assert self._mapear(raw, cat_nombre="Frutas")['Categoria'] == 'Frutas'

    @pytest.mark.parametrize("precio_str,esperado", [
        ("1.50", 1.50), ("0.99", 0.99), (2.30, 2.30),
    ])
    def test_precio_varios_formatos(self, precio_str, esperado):
        raw = {"id": "001", "name": "Test", "price": precio_str}
        resultado = self._mapear(raw)
        assert resultado is not None
        assert resultado['Precio'] == pytest.approx(esperado)


class TestGestionAlcampoSinPlaywright:

    def test_modulo_carga_correctamente(self):
        """El módulo alcampo expone gestion_alcampo."""
        import alcampo
        assert hasattr(alcampo, 'gestion_alcampo')
        assert callable(alcampo.gestion_alcampo)
