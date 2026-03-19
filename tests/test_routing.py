# -*- coding: utf-8 -*-
"""Tests para el módulo de routing (geolocalización y rutas).

Usa mocks para evitar llamadas reales a Nominatim, Overpass y OSRM.

    python -m pytest tests/test_routing.py -v
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from routing import (
    geocodificar,
    buscar_supermercados_cercanos,
    calcular_ruta_optima,
    _distancia_haversine,
)


# ═════════════════════════════════════════════════════════════════════
# TESTS DE GEOCODIFICACIÓN (Nominatim)
# ═════════════════════════════════════════════════════════════════════

class TestGeocodificar:

    @patch("routing.requests.get")
    def test_geocodificar_direccion_valida(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"lat": "41.3874", "lon": "2.1686",
                           "display_name": "Barcelona, Cataluña, España"}],
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = geocodificar("Barcelona, España")
        assert resultado is not None
        assert abs(resultado["lat"] - 41.3874) < 0.01
        assert abs(resultado["lon"] - 2.1686) < 0.01
        assert "Barcelona" in resultado["display_name"]

    @patch("routing.requests.get")
    def test_geocodificar_codigo_postal(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"lat": "40.4168", "lon": "-3.7038",
                           "display_name": "28001, Madrid"}],
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = geocodificar("28001")
        assert resultado is not None
        assert abs(resultado["lat"] - 40.4168) < 0.01

    @patch("routing.requests.get")
    def test_geocodificar_sin_resultados(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: [],
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = geocodificar("zzzzzzzzz_lugar_inexistente")
        assert resultado is None

    @patch("routing.requests.get")
    def test_geocodificar_error_red(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")

        resultado = geocodificar("Barcelona")
        assert resultado is None

    @patch("routing.requests.get")
    def test_geocodificar_error_http(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
        mock_get.return_value = mock_resp

        resultado = geocodificar("Madrid")
        assert resultado is None


# ═════════════════════════════════════════════════════════════════════
# TESTS DE BÚSQUEDA DE SUPERMERCADOS (Overpass)
# ═════════════════════════════════════════════════════════════════════

class TestBuscarSupermercados:

    @patch("routing.requests.post")
    def test_buscar_supermercados_ok(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "elements": [
                    {
                        "type": "node",
                        "lat": 41.388,
                        "lon": 2.169,
                        "tags": {
                            "name": "Mercadona",
                            "shop": "supermarket",
                            "addr:street": "Carrer de Pau Claris",
                            "addr:housenumber": "100",
                            "addr:city": "Barcelona",
                        },
                    }
                ]
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        resultado = buscar_supermercados_cercanos(
            41.387, 2.168, ["Mercadona"])

        assert "Mercadona" in resultado
        assert len(resultado["Mercadona"]) == 1
        tienda = resultado["Mercadona"][0]
        assert tienda["lat"] == 41.388
        assert tienda["lon"] == 2.169
        assert tienda["nombre"] == "Mercadona"
        assert "Pau Claris" in tienda["direccion"]
        assert tienda["distancia_m"] > 0

    @patch("routing.requests.post")
    def test_buscar_supermercados_multiples(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "elements": [
                    {"type": "node", "lat": 41.388, "lon": 2.169,
                     "tags": {"name": "Mercadona", "shop": "supermarket"}},
                    {"type": "node", "lat": 41.386, "lon": 2.167,
                     "tags": {"name": "Dia", "shop": "supermarket"}},
                    {"type": "node", "lat": 41.390, "lon": 2.170,
                     "tags": {"name": "Mercadona", "shop": "supermarket"}},
                ]
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        resultado = buscar_supermercados_cercanos(
            41.387, 2.168, ["Mercadona", "Dia"])

        assert len(resultado["Mercadona"]) == 1  # Solo la más cercana
        assert len(resultado["Dia"]) == 1

    @patch("routing.requests.post")
    def test_buscar_supermercados_way_con_center(self, mock_post):
        """Supermercados mapeados como 'way' usan campo 'center'."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "elements": [
                    {
                        "type": "way",
                        "center": {"lat": 41.388, "lon": 2.169},
                        "tags": {"name": "Carrefour Express",
                                 "shop": "supermarket"},
                    }
                ]
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        resultado = buscar_supermercados_cercanos(
            41.387, 2.168, ["Carrefour"])

        assert len(resultado["Carrefour"]) == 1

    @patch("routing.requests.post")
    def test_buscar_supermercados_sin_resultados(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"elements": []},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        resultado = buscar_supermercados_cercanos(
            0.0, 0.0, ["Mercadona"])

        assert resultado["Mercadona"] == []

    @patch("routing.requests.post")
    def test_buscar_supermercados_error_red(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        resultado = buscar_supermercados_cercanos(
            41.387, 2.168, ["Mercadona", "Dia"])

        assert resultado["Mercadona"] == []
        assert resultado["Dia"] == []


# ═════════════════════════════════════════════════════════════════════
# TESTS DE CÁLCULO DE RUTA (OSRM)
# ═════════════════════════════════════════════════════════════════════

class TestCalcularRuta:

    @patch("routing.requests.get")
    def test_ruta_optima_ok(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "code": "Ok",
                "trips": [{
                    "distance": 5000,
                    "duration": 600,
                    "geometry": {
                        "coordinates": [
                            [2.168, 41.387],
                            [2.169, 41.388],
                            [2.170, 41.390],
                        ]
                    },
                    "legs": [
                        {"distance": 2500, "duration": 300},
                        {"distance": 2500, "duration": 300},
                    ],
                }],
                "waypoints": [
                    {"waypoint_index": 0},
                    {"waypoint_index": 1},
                ],
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168},
            [{"lat": 41.390, "lon": 2.170,
              "nombre": "Mercadona", "supermercado": "Mercadona"}],
        )

        assert resultado is not None
        assert resultado["distancia_total_km"] == 5.0
        assert resultado["duracion_total_min"] == 10.0
        assert len(resultado["geometria"]) == 3
        assert len(resultado["tramos"]) == 2
        assert resultado["tramos"][0]["distancia_km"] == 2.5

    @patch("routing.requests.get")
    def test_ruta_multiples_paradas(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "code": "Ok",
                "trips": [{
                    "distance": 12000,
                    "duration": 1200,
                    "geometry": {"coordinates": [[2.1, 41.3], [2.2, 41.4]]},
                    "legs": [
                        {"distance": 4000, "duration": 400},
                        {"distance": 4000, "duration": 400},
                        {"distance": 4000, "duration": 400},
                    ],
                }],
                "waypoints": [
                    {"waypoint_index": 0},
                    {"waypoint_index": 2},
                    {"waypoint_index": 1},
                ],
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168},
            [
                {"lat": 41.390, "lon": 2.170,
                 "nombre": "Mercadona", "supermercado": "Mercadona"},
                {"lat": 41.395, "lon": 2.175,
                 "nombre": "Dia", "supermercado": "Dia"},
            ],
        )

        assert resultado is not None
        assert resultado["distancia_total_km"] == 12.0
        assert len(resultado["paradas_ordenadas"]) == 2
        # Verificar que se reordena por waypoint_index
        assert resultado["paradas_ordenadas"][0]["supermercado"] == "Dia"

    def test_ruta_sin_paradas(self):
        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168}, [])
        assert resultado is None

    @patch("routing.requests.get")
    def test_ruta_error_osrm(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"code": "NoTrips", "trips": []},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168},
            [{"lat": 41.390, "lon": 2.170,
              "nombre": "Mercadona", "supermercado": "Mercadona"}],
        )
        assert resultado is None

    @patch("routing.requests.get")
    def test_ruta_error_red(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168},
            [{"lat": 41.390, "lon": 2.170,
              "nombre": "Mercadona", "supermercado": "Mercadona"}],
        )
        assert resultado is None

    @patch("routing.requests.get")
    def test_ruta_modo_walking(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "code": "Ok",
                "trips": [{
                    "distance": 3000,
                    "duration": 2400,
                    "geometry": {"coordinates": [[2.168, 41.387]]},
                    "legs": [{"distance": 3000, "duration": 2400}],
                }],
                "waypoints": [
                    {"waypoint_index": 0},
                    {"waypoint_index": 1},
                ],
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168},
            [{"lat": 41.390, "lon": 2.170,
              "nombre": "Dia", "supermercado": "Dia"}],
            modo="walking",
        )
        assert resultado is not None
        # Verificar que se usó el perfil correcto
        url_llamada = mock_get.call_args[0][0]
        assert "/foot/" in url_llamada


# ═════════════════════════════════════════════════════════════════════
# TESTS DE HELPERS
# ═════════════════════════════════════════════════════════════════════

class TestDistanciaHaversine:

    def test_distancia_misma_ubicacion(self):
        dist = _distancia_haversine(41.387, 2.168, 41.387, 2.168)
        assert dist == 0.0

    def test_distancia_conocida(self):
        # Barcelona a Madrid ~500 km
        dist = _distancia_haversine(41.387, 2.168, 40.416, -3.703)
        assert 480000 < dist < 520000  # Entre 480 y 520 km

    def test_distancia_corta(self):
        # Dos puntos cercanos (~100-200m)
        dist = _distancia_haversine(41.387, 2.168, 41.388, 2.169)
        assert 100 < dist < 200
