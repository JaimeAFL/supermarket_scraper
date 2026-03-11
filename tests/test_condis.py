# -*- coding: utf-8 -*-
"""Tests unitarios para condis.py — ejecutar con: python -m pytest test_condis.py -v"""

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from condis import (  # noqa: E402
    _extraer_formato_de_nombre,
    _normalizar_unidad,
    _mapear_producto,
    _obtener_categorias,
    gestion_condis,
)

COLUMNAS_ESPERADAS = [
    'Id', 'Nombre', 'Precio', 'Precio_por_unidad',
    'Formato', 'Categoria', 'Supermercado', 'Url', 'Url_imagen'
]

PRODUCTO_VALIDO = {
    "id": "704048", "externalId": "704048",
    "description": "LECHE CONDIS SEMIDESNATADA 1 L",
    "brand": "CONDIS",
    "price": {"current": 0.91, "regular": 0.91},
    "pum": "0,91€/Litro",
    "category": ["Bebidas", "Leche", "Leche semidesnatada"],
    "parentCategory": "c07__cat00210003",
    "images": ["/images/catalog/large/704048.jpg"],
    "url": "/leche-condis-semidesnatada-1-l/p/704048/es_ES",
    "on_sale": False, "netWeight": 1, "product_type": "product",
}

PRODUCTO_EN_OFERTA = {
    **PRODUCTO_VALIDO, "id": "111111",
    "description": "LECHE ASTURIANA ENTERA 1 L",
    "price": {"current": 0.99, "regular": 1.15},
    "pum": "0,99€/Litro",
}


class TestExtraerFormatoDenombre:

    def test_formato_litros(self):
        assert _extraer_formato_de_nombre("LECHE CONDIS SEMIDESNATADA 1 L") == "1 L"

    def test_formato_mililitros(self):
        assert _extraer_formato_de_nombre("ZUMO DE NARANJA 200 ML") == "200 ml"

    def test_formato_gramos(self):
        assert _extraer_formato_de_nombre("YOGUR NATURAL 125 G") == "125 g"

    def test_formato_kilogramos(self):
        assert _extraer_formato_de_nombre("LENTEJAS BOLSA 1 KG") == "1 kg"

    def test_sin_formato_devuelve_cadena_vacia(self):
        assert _extraer_formato_de_nombre("PRODUCTO SIN TAMAÑO") == ""

    @pytest.mark.parametrize("nombre,esperado_contiene", [
        ("ACEITE DE OLIVA 750 ML", "ml"),
        ("PASTA ESPAGUETI 500 G",  "g"),
        ("LECHE ENTERA 1 L",       "L"),
        ("HARINA DE TRIGO 1 KG",   "kg"),
    ])
    def test_varios_formatos(self, nombre, esperado_contiene):
        assert esperado_contiene in _extraer_formato_de_nombre(nombre)


class TestNormalizarUnidad:

    @pytest.mark.parametrize("entrada,esperado", [
        ("L",        "L"),   ("LITRO",   "L"),   ("LITROS",  "L"),
        ("ML",       "ml"),  ("CL",      "cl"),
        ("G",        "g"),   ("GR",      "g"),   ("GRAMOS",  "g"),
        ("KG",       "kg"),  ("KILO",    "kg"),  ("KILOS",   "kg"),
        ("UNIDAD",   "ud"),  ("UNIDADES","ud"),  ("UDS",     "ud"),
    ])
    def test_normalizacion(self, entrada, esperado):
        assert _normalizar_unidad(entrada) == esperado


class TestMapearProductoCondis:

    def test_producto_valido(self):
        """Producto completo se mapea correctamente."""
        r = _mapear_producto(PRODUCTO_VALIDO)
        assert r is not None
        assert r['Id'] == '704048'
        assert r['Precio'] == pytest.approx(0.91)
        assert r['Supermercado'] == 'Condis'
        assert r['Categoria'] == 'Leche semidesnatada'

    def test_columnas_presentes(self):
        """El resultado contiene todas las columnas estándar."""
        r = _mapear_producto(PRODUCTO_VALIDO)
        for col in COLUMNAS_ESPERADAS:
            assert col in r, f"Falta columna '{col}'"

    def test_precio_oferta_usado(self):
        """Con oferta activa se usa price.current (precio rebajado)."""
        r = _mapear_producto(PRODUCTO_EN_OFERTA)
        assert r is not None
        assert r['Precio'] == pytest.approx(0.99)

    def test_sin_id_devuelve_none(self):
        prod = {**PRODUCTO_VALIDO, "id": "", "externalId": ""}
        assert _mapear_producto(prod) is None

    def test_sin_nombre_devuelve_none(self):
        prod = {**PRODUCTO_VALIDO, "description": ""}
        assert _mapear_producto(prod) is None

    def test_precio_cero_devuelve_none(self):
        prod = {**PRODUCTO_VALIDO, "price": {"current": 0, "regular": 0}}
        assert _mapear_producto(prod) is None

    def test_categoria_toma_ultimo_elemento(self):
        """La categoría más específica es el último elemento de la lista."""
        prod = {**PRODUCTO_VALIDO, "category": ["Alimentación", "Lácteos", "Leche entera"]}
        assert _mapear_producto(prod)['Categoria'] == 'Leche entera'

    def test_url_absoluta(self):
        assert _mapear_producto(PRODUCTO_VALIDO)['Url'].startswith('https://')

    def test_url_imagen_absoluta(self):
        assert _mapear_producto(PRODUCTO_VALIDO)['Url_imagen'].startswith('https://')

    def test_nombre_convertido_a_titulo(self):
        assert _mapear_producto(PRODUCTO_VALIDO)['Nombre'] == 'Leche Condis Semidesnatada 1 L'

    def test_precio_unitario_extraido_de_pum(self):
        assert _mapear_producto(PRODUCTO_VALIDO)['Precio_por_unidad'] == pytest.approx(0.91)


class TestObtenerCategorias:

    @patch('condis.requests.get')
    def test_extrae_categoryids_del_html(self, mock_get):
        """Extrae correctamente los categoryIds del HTML."""
        html = '<script>{"categoryId":"c07__cat00210003","other":"c01__cat00020001"}</script>'
        mock_get.return_value = MagicMock(
            status_code=200, text=html,
            raise_for_status=MagicMock(return_value=None)
        )
        resultado = _obtener_categorias()
        assert isinstance(resultado, list)
        assert 'c07__cat00210003' in resultado

    @patch('condis.requests.get')
    def test_error_de_red_devuelve_lista_vacia(self, mock_get):
        """Error de red → lista vacía."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Sin conexión")
        assert _obtener_categorias() == []


class TestGestionCondis:

    @patch('condis.time.sleep')
    @patch('condis.requests.get')
    def test_devuelve_dataframe_con_datos(self, mock_get, mock_sleep):
        """gestion_condis() devuelve DataFrame con columnas correctas."""
        html_con_cats = '<script>{"cat":"c07__cat00210003"}</script>'
        mock_get.side_effect = [
            MagicMock(status_code=200, text=html_con_cats,
                      raise_for_status=MagicMock(return_value=None)),
            MagicMock(raise_for_status=MagicMock(return_value=None),
                      json=MagicMock(return_value={
                          "catalog": {
                              "numFound": 1,
                              "content": [PRODUCTO_VALIDO],
                              "pagination": {"total": 1, "start": 0, "rows": 100}
                          }
                      })),
        ]
        df = gestion_condis()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        for col in COLUMNAS_ESPERADAS:
            assert col in df.columns
        assert df['Supermercado'].iloc[0] == 'Condis'

    @patch('condis.requests.get')
    def test_sin_categorias_devuelve_df_vacio(self, mock_get):
        """Sin categorías disponibles, devuelve DataFrame vacío."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Sin conexión")
        assert isinstance(gestion_condis(), pd.DataFrame)


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Salta en CI")
class TestCondisAPI:

    def test_endpoint_empathy_responde(self):
        """La API real de Empathy para Condis responde con datos válidos."""
        import requests
        r = requests.get(
            "https://api.empathy.co/search/v1/query/condis/browse",
            params={"lang": "es", "rows": 1, "store": "718",
                    "browseField": "parentCategory", "browseValue": "c07__cat00210003"},
            headers={"User-Agent": "Mozilla/5.0",
                     "Referer": "https://compraonline.condis.es/"},
            timeout=10
        )
        assert r.status_code == 200
        assert "catalog" in r.json()
