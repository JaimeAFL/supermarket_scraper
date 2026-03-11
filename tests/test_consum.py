# -*- coding: utf-8 -*-
"""Tests unitarios para consum.py — ejecutar con: python -m pytest test_consum.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from consum import _mapear_producto, gestion_consum  # noqa: E402

COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]

PRODUCTO_VALIDO = {
    "id": 4667, "code": "1669",
    "productData": {
        "name": "Rabanito Bolsa",
        "brand": {"id": "EL DULZE", "name": "EL DULZE"},
        "url": "https://tienda.consum.es/es/p/rabanito-bolsa/1669",
        "imageURL": "https://cdn-consum.aktiosdigitalservices.com/img/300x300/1669.jpg",
        "format": "250 g", "description": "Rabanito Bolsa 250 Gr",
    },
    "priceData": {
        "prices": [{"id": "PRICE", "value": {"centAmount": 1.15, "centUnitAmount": 4.6}}],
        "unitPriceUnitType": "1 Kg"
    },
    "categories": [{"id": 2214, "name": "Zanahorias y otras raíces", "type": 0}],
}

PRODUCTO_CON_OFERTA = {
    "id": 9999, "code": "9999",
    "productData": {
        "name": "Manzana Fuji", "brand": {"name": ""},
        "url": "https://tienda.consum.es/es/p/manzana-fuji/9999",
        "imageURL": "https://cdn-consum.aktiosdigitalservices.com/img/9999.jpg",
        "format": "1 Kg", "description": "Manzana Fuji 1 Kg",
    },
    "priceData": {
        "prices": [
            {"id": "PRICE",       "value": {"centAmount": 0.60, "centUnitAmount": 2.39}},
            {"id": "OFFER_PRICE", "value": {"centAmount": 0.54, "centUnitAmount": 2.15}},
        ],
        "unitPriceUnitType": "1 Kg"
    },
    "categories": [{"id": 100, "name": "Manzana, pera y uva", "type": 0}],
}


class TestMapearProductoConsum:

    def test_producto_valido_mapeado(self):
        """Producto completo se mapea con todos los campos correctos."""
        r = _mapear_producto(PRODUCTO_VALIDO)
        assert r is not None
        assert r['Id'] == '1669'
        assert r['Nombre'] == 'Rabanito Bolsa'
        assert r['Precio'] == pytest.approx(1.15)
        assert r['Precio_por_unidad'] == pytest.approx(4.6)
        assert r['Categoria'] == 'Zanahorias y otras raíces'
        assert r['Supermercado'] == 'Consum'

    def test_columnas_presentes(self):
        """El resultado contiene todas las columnas estándar."""
        r = _mapear_producto(PRODUCTO_VALIDO)
        for col in COLUMNAS_ESPERADAS:
            assert col in r, f"Falta columna '{col}'"

    def test_precio_oferta_tiene_prioridad(self):
        """OFFER_PRICE tiene prioridad sobre PRICE."""
        r = _mapear_producto(PRODUCTO_CON_OFERTA)
        assert r is not None
        assert r['Precio'] == pytest.approx(0.54)
        assert r['Precio_por_unidad'] == pytest.approx(2.15)

    def test_sin_code_usa_id(self):
        """Si no hay 'code', usa 'id' como identificador."""
        prod = {**PRODUCTO_VALIDO, "code": ""}
        r = _mapear_producto(prod)
        assert r is not None
        assert r['Id'] == '4667'

    def test_sin_nombre_devuelve_none(self):
        """Producto sin nombre → None."""
        prod = {**PRODUCTO_VALIDO,
                "productData": {**PRODUCTO_VALIDO["productData"], "name": ""}}
        assert _mapear_producto(prod) is None

    def test_sin_precio_devuelve_none(self):
        """Producto sin precios → None."""
        prod = {**PRODUCTO_VALIDO, "priceData": {"prices": []}}
        assert _mapear_producto(prod) is None

    def test_precio_cero_devuelve_none(self):
        """Precio cero → None."""
        prod = {**PRODUCTO_VALIDO, "priceData": {
            "prices": [{"id": "PRICE", "value": {"centAmount": 0, "centUnitAmount": 0}}]
        }}
        assert _mapear_producto(prod) is None

    def test_categoria_type_1_ignorada(self):
        """Las categorías type=1 (promocionales) se ignoran; se usa la type=0."""
        prod = {
            "id": 8001, "code": "8001",
            "productData": {
                "name": "Leche Test", "brand": {"name": "MARCA"},
                "url": "https://tienda.consum.es/es/p/leche/8001",
                "imageURL": "https://img.jpg", "format": "1 L",
                "description": "Leche Test 1 L",
            },
            "priceData": {
                "prices": [{"id": "PRICE", "value": {"centAmount": 1.0, "centUnitAmount": 1.0}}],
                "unitPriceUnitType": "1 L"
            },
            "categories": [
                {"id": 1, "name": "Ofertas en frescos", "type": 1},
                {"id": 2214, "name": "Zanahorias y otras raíces", "type": 0},
            ]
        }
        r = _mapear_producto(prod)
        assert r['Categoria'] == 'Zanahorias y otras raíces'

    def test_marca_invalida_se_limpia(self):
        """Marcas como '-', '---', '0' se convierten a cadena vacía."""
        prod_base = {
            "id": 8002, "code": "8002",
            "productData": {
                "name": "Producto Test", "url": "https://tienda.consum.es/es/p/test/8002",
                "imageURL": "https://img.jpg", "format": "500 g",
                "description": "Producto Test 500 g",
            },
            "priceData": {
                "prices": [{"id": "PRICE", "value": {"centAmount": 1.0, "centUnitAmount": 2.0}}],
                "unitPriceUnitType": "1 Kg"
            },
            "categories": [{"id": 1, "name": "Test", "type": 0}],
        }
        for marca_invalida in ["-", "---", "0"]:
            prod = {**prod_base,
                    "productData": {**prod_base["productData"],
                                    "brand": {"name": marca_invalida}}}
            assert _mapear_producto(prod)['Marca'] == ''

    def test_formato_fallback_desde_unitpricetype(self):
        """Si format está vacío, usa unitPriceUnitType como fallback."""
        prod = {
            "id": 8003, "code": "8003",
            "productData": {
                "name": "Arroz Test", "brand": {"name": "MARCA"},
                "url": "https://tienda.consum.es/es/p/arroz/8003",
                "imageURL": "https://img.jpg", "format": "",
                "description": "Arroz Test",
            },
            "priceData": {
                "prices": [{"id": "PRICE", "value": {"centAmount": 1.50, "centUnitAmount": 1.50}}],
                "unitPriceUnitType": "1 Kg"
            },
            "categories": [{"id": 1, "name": "Arroz", "type": 0}],
        }
        assert _mapear_producto(prod)['Formato'] == '1 Kg'


class TestGestionConsum:

    @patch('consum.requests.get')
    def test_devuelve_dataframe_con_datos(self, mock_get):
        """gestion_consum() devuelve DataFrame con columnas correctas."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(return_value={
                "totalCount": 1, "hasMore": False, "products": [PRODUCTO_VALIDO]
            })
        )
        df = gestion_consum()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns
        assert df['Supermercado'].iloc[0] == 'Consum'

    @patch('consum.requests.get')
    def test_error_de_red_devuelve_df_vacio(self, mock_get):
        """Error de red → DataFrame vacío sin excepción."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Sin conexión")
        df = gestion_consum()
        assert isinstance(df, pd.DataFrame)

    @patch('consum.time.sleep')
    @patch('consum.requests.get')
    def test_paginacion_correcta(self, mock_get, mock_sleep):
        """Pagina correctamente con totalCount > LIMIT (100)."""
        prod2 = {**PRODUCTO_VALIDO, "code": "9998", "id": 9998}
        mock_get.side_effect = [
            # Primera llamada: totalCount con limit=1
            MagicMock(raise_for_status=MagicMock(return_value=None),
                      json=MagicMock(return_value={"totalCount": 150, "hasMore": True, "products": []})),
            # Página 0
            MagicMock(raise_for_status=MagicMock(return_value=None),
                      json=MagicMock(return_value={"totalCount": 150, "hasMore": True, "products": [PRODUCTO_VALIDO]})),
            # Página 1
            MagicMock(raise_for_status=MagicMock(return_value=None),
                      json=MagicMock(return_value={"totalCount": 150, "hasMore": False, "products": [prod2]})),
        ]
        df = gestion_consum()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    @patch('consum.time.sleep')
    @patch('consum.requests.get')
    def test_deduplicacion_por_id(self, mock_get, mock_sleep):
        """Productos duplicados se eliminan por Id."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(return_value=None),
            json=MagicMock(return_value={
                "totalCount": 1, "hasMore": False,
                "products": [PRODUCTO_VALIDO, PRODUCTO_VALIDO]  # duplicado
            })
        )
        df = gestion_consum()
        assert len(df) == 1


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Salta en CI")
class TestConsumAPI:

    def test_endpoint_responde(self):
        """La API real de Consum responde con datos válidos."""
        import requests
        r = requests.get(
            "https://tienda.consum.es/api/rest/V1.0/catalog/product",
            params={"limit": 1, "offset": 0}, timeout=10
        )
        assert r.status_code == 200
        datos = r.json()
        assert "totalCount" in datos
        assert datos["totalCount"] > 0
