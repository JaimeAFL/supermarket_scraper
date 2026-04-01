"""api/routers/rutas.py - Endpoints de geocodificación y rutas óptimas."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import verify_api_key
from api.schemas import (
    GeocodificarRequest,
    GeocodificarResponse,
    SupermercadosCercanosRequest,
    SupermercadosCercanosResponse,
    TiendaCercana,
    RutaOptimaRequest,
    RutaOptimaResponse,
    ParadaOrdenada,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rutas", tags=["rutas"])
limiter = Limiter(key_func=get_remote_address)


def _import_routing():
    """Importa routing.py de forma lazy (sus dependencias son pesadas)."""
    try:
        import routing
        return routing
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Módulo de rutas no disponible: {e}",
        )


@router.post("/geocodificar", response_model=GeocodificarResponse)
@limiter.limit("20/minute")
def geocodificar(
    request: Request,
    body: GeocodificarRequest,
    _auth=Depends(verify_api_key),
):
    """Convierte una dirección o código postal en coordenadas (lat/lon)."""
    routing = _import_routing()
    resultado = routing.geocodificar(body.direccion, pais=body.pais)
    if not resultado:
        raise HTTPException(
            status_code=404,
            detail=f"No se pudo geocodificar la dirección: '{body.direccion}'",
        )
    return GeocodificarResponse(
        lat=resultado["lat"],
        lon=resultado["lon"],
        display_name=resultado["display_name"],
    )


@router.post("/supermercados-cercanos", response_model=SupermercadosCercanosResponse)
@limiter.limit("20/minute")
def supermercados_cercanos(
    request: Request,
    body: SupermercadosCercanosRequest,
    _auth=Depends(verify_api_key),
):
    """Busca tiendas físicas cercanas a unas coordenadas vía OpenStreetMap."""
    routing = _import_routing()
    resultado = routing.buscar_supermercados_cercanos(
        body.lat, body.lon, body.supermercados, body.radio_metros,
    )
    if not resultado:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron supermercados cercanos.",
        )

    tiendas: dict[str, list[TiendaCercana]] = {}
    for supermercado, lista in resultado.items():
        tiendas[supermercado] = [
            TiendaCercana(
                lat=t["lat"],
                lon=t["lon"],
                nombre=t.get("nombre", supermercado),
                direccion=t.get("direccion"),
                distancia_m=t.get("distancia_m", 0),
            )
            for t in lista
        ]
    return SupermercadosCercanosResponse(tiendas=tiendas)


@router.post("/optimizar", response_model=RutaOptimaResponse)
@limiter.limit("10/minute")
def optimizar_ruta(
    request: Request,
    body: RutaOptimaRequest,
    _auth=Depends(verify_api_key),
):
    """Calcula la ruta óptima entre tiendas (geocoding + búsqueda + TSP).

    Flujo completo:
    1. Geocodifica la dirección del usuario
    2. Busca la tienda más cercana de cada supermercado solicitado
    3. Calcula la ruta óptima (TSP) con OSRM
    """
    routing = _import_routing()

    # 1. Geocodificar dirección
    origen = routing.geocodificar(body.direccion)
    if not origen:
        raise HTTPException(
            status_code=404,
            detail=f"No se pudo geocodificar: '{body.direccion}'",
        )

    # 2. Buscar tiendas cercanas
    tiendas = routing.buscar_supermercados_cercanos(
        origen["lat"], origen["lon"], body.supermercados, body.radio_metros,
    )
    if not tiendas:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron supermercados cercanos.",
        )

    # 3. Seleccionar la tienda más cercana de cada supermercado
    paradas = []
    for supermercado, lista in tiendas.items():
        if lista:
            mejor = lista[0]  # ya ordenada por distancia
            paradas.append({
                "lat": mejor["lat"],
                "lon": mejor["lon"],
                "nombre": mejor.get("nombre", supermercado),
                "supermercado": supermercado,
                "distancia_m": mejor.get("distancia_m", 0),
            })

    if not paradas:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron tiendas para calcular ruta.",
        )

    # 4. Calcular ruta óptima
    ruta = routing.calcular_ruta_optima(
        origen={"lat": origen["lat"], "lon": origen["lon"]},
        paradas=paradas,
        modo=body.modo,
    )

    if not ruta:
        # Devolver paradas sin optimización si OSRM falla
        return RutaOptimaResponse(
            origen=GeocodificarResponse(
                lat=origen["lat"], lon=origen["lon"],
                display_name=origen["display_name"],
            ),
            paradas_ordenadas=[
                ParadaOrdenada(
                    supermercado=p["supermercado"],
                    nombre=p["nombre"],
                    lat=p["lat"],
                    lon=p["lon"],
                    distancia_m=p["distancia_m"],
                )
                for p in paradas
            ],
            distancia_total_km=0,
            duracion_total_min=0,
        )

    paradas_ordenadas = [
        ParadaOrdenada(
            supermercado=p.get("supermercado", ""),
            nombre=p.get("nombre", ""),
            lat=p["lat"],
            lon=p["lon"],
            distancia_m=p.get("distancia_m", 0),
        )
        for p in ruta.get("paradas_ordenadas", paradas)
    ]

    return RutaOptimaResponse(
        origen=GeocodificarResponse(
            lat=origen["lat"], lon=origen["lon"],
            display_name=origen["display_name"],
        ),
        paradas_ordenadas=paradas_ordenadas,
        distancia_total_km=ruta.get("distancia_total_km", 0),
        duracion_total_min=ruta.get("duracion_total_min", 0),
        geometria=ruta.get("geometria"),
    )
