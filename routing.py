"""routing.py - Geolocalización y cálculo de rutas con APIs gratuitas.

APIs utilizadas (todas gratuitas, sin API key):
- Nominatim (OpenStreetMap): geocodificación de direcciones
- Overpass API (OpenStreetMap): búsqueda de supermercados cercanos
- OSRM demo server: cálculo de rutas y optimización de paradas

Restricciones de uso responsable:
- Nominatim: máximo 1 petición/segundo, incluir User-Agent con email
- Overpass: no abusar (cachear resultados cuando sea posible)
- OSRM demo: solo para proyectos pequeños / demo
"""

import math
import requests
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────

# User-Agent obligatorio para Nominatim (poner email del desarrollador)
_USER_AGENT = "SupermarketPriceTracker/1.0 (contacto@ejemplo.com)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OSRM_URL = "https://router.project-osrm.org"

# Nombres de supermercados tal como aparecen en OpenStreetMap
# Clave = nombre en nuestra BD, Valor = posibles nombres en OSM
NOMBRES_OSM = {
    "Mercadona":  ["Mercadona"],
    "Carrefour":  ["Carrefour", "Carrefour Express", "Carrefour Market"],
    "Dia":        ["Dia", "Dia %", "DIA"],
    "Alcampo":    ["Alcampo", "Alcampo Supermercado"],
    "Eroski":     ["Eroski", "Eroski City", "Eroski Center"],
    "Consum":     ["Consum", "Consum Bàsic"],
    "Condis":     ["Condis", "Condis Express"],
}


# ── Geocodificación (Nominatim) ───────────────────────────────────

def geocodificar(direccion: str, pais: str = "es") -> Optional[dict]:
    """Convierte una dirección o código postal en coordenadas.

    Args:
        direccion: Dirección completa o código postal.
        pais: Código ISO del país (default: "es" para España).

    Returns:
        dict con claves "lat", "lon", "display_name" o None si no se encontró.
    """
    try:
        resp = requests.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": direccion,
                "format": "json",
                "limit": 1,
                "countrycodes": pais,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json()
        if not resultados:
            return None
        r = resultados[0]
        return {
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "display_name": r.get("display_name", ""),
        }
    except Exception as e:
        logger.error("geocodificar: %s", e)
        return None
    finally:
        time.sleep(1)  # Respetar límite de 1 req/seg


# ── Búsqueda de supermercados cercanos (Overpass) ──────────────────

def _distancia_haversine(lat1, lon1, lat2, lon2):
    """Distancia Haversine aproximada en metros."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def buscar_supermercados_cercanos(
    lat: float, lon: float,
    supermercados: list[str],
    radio_metros: int = 5000,
) -> dict[str, list[dict]]:
    """Busca tiendas físicas de los supermercados indicados cerca de un punto.

    Args:
        lat, lon: Coordenadas del usuario.
        supermercados: Lista de nombres de supermercados (e.g. ["Mercadona", "Dia"]).
        radio_metros: Radio de búsqueda en metros (default: 5000 = 5 km).

    Returns:
        dict donde la clave es el nombre del supermercado y el valor es una lista
        de tiendas, cada una con "lat", "lon", "nombre", "direccion".
        Solo devuelve la tienda más cercana por supermercado.
    """
    # Construir query Overpass con todas las marcas a la vez
    filtros = []
    for super_nombre in supermercados:
        nombres_osm = NOMBRES_OSM.get(super_nombre, [super_nombre])
        for nombre_osm in nombres_osm:
            filtros.append(
                f'node["shop"="supermarket"]["name"="{nombre_osm}"]'
                f'(around:{radio_metros},{lat},{lon});'
            )
            # Algunos supermercados están mapeados como way, no como node
            filtros.append(
                f'way["shop"="supermarket"]["name"="{nombre_osm}"]'
                f'(around:{radio_metros},{lat},{lon});'
            )

    query = f"""
    [out:json][timeout:25];
    (
        {"".join(filtros)}
    );
    out center;
    """

    try:
        resp = requests.post(
            _OVERPASS_URL,
            data={"data": query},
            timeout=30,
        )
        resp.raise_for_status()
        datos = resp.json()
    except Exception as e:
        logger.error("buscar_supermercados_cercanos: %s", e)
        return {s: [] for s in supermercados}

    # Agrupar resultados por supermercado y quedarse con el más cercano
    resultados = {s: [] for s in supermercados}

    for elemento in datos.get("elements", []):
        # Obtener coordenadas (center para ways, directo para nodes)
        e_lat = elemento.get("lat") or elemento.get("center", {}).get("lat")
        e_lon = elemento.get("lon") or elemento.get("center", {}).get("lon")
        if not e_lat or not e_lon:
            continue

        nombre_osm = elemento.get("tags", {}).get("name", "")
        direccion_parts = []
        tags = elemento.get("tags", {})
        for tag in ["addr:street", "addr:housenumber", "addr:city"]:
            if tags.get(tag):
                direccion_parts.append(tags[tag])
        direccion = ", ".join(direccion_parts) if direccion_parts else ""

        # Identificar a qué supermercado pertenece
        for super_nombre in supermercados:
            nombres_osm_validos = NOMBRES_OSM.get(super_nombre, [super_nombre])
            if any(nombre_osm.lower().startswith(n.lower().replace("%", ""))
                   for n in nombres_osm_validos):
                dist = _distancia_haversine(lat, lon, e_lat, e_lon)
                resultados[super_nombre].append({
                    "lat": e_lat,
                    "lon": e_lon,
                    "nombre": nombre_osm,
                    "direccion": direccion,
                    "distancia_m": round(dist),
                })
                break

    # Ordenar por distancia y quedarse con la más cercana de cada super
    for super_nombre in supermercados:
        tiendas = sorted(resultados[super_nombre],
                         key=lambda x: x["distancia_m"])
        resultados[super_nombre] = tiendas[:1]  # Solo la más cercana

    return resultados


# ── Ruta óptima (OSRM) ────────────────────────────────────────────

def calcular_ruta_optima(
    origen: dict,
    paradas: list[dict],
    modo: str = "driving",
) -> Optional[dict]:
    """Calcula la ruta óptima pasando por todas las paradas.

    Usa OSRM /trip que resuelve el Travelling Salesman Problem.

    Args:
        origen: dict con "lat" y "lon" del punto de partida (casa del usuario).
        paradas: lista de dicts con "lat", "lon", "nombre", "supermercado".
        modo: "driving" (default), "walking", "cycling".

    Returns:
        dict con:
        - "paradas_ordenadas": lista de paradas en el orden óptimo
        - "distancia_total_km": distancia total del recorrido
        - "duracion_total_min": duración estimada en minutos
        - "geometria": lista de [lon, lat] para pintar la ruta en Folium
        - "tramos": lista de dicts con distancia y duración por tramo
        O None si no se pudo calcular.
    """
    if not paradas:
        return None

    # Construir coordenadas: origen + paradas
    # OSRM espera lon,lat (no lat,lon)
    coords = f"{origen['lon']},{origen['lat']}"
    for p in paradas:
        coords += f";{p['lon']},{p['lat']}"

    profile = {"driving": "car", "walking": "foot",
               "cycling": "bike"}.get(modo, "car")

    try:
        resp = requests.get(
            f"{_OSRM_URL}/trip/v1/{profile}/{coords}",
            params={
                "source": "first",          # El origen es el primer punto
                "destination": "last",       # Volver al origen
                "roundtrip": "true",
                "geometries": "geojson",     # Para Folium
                "overview": "full",
                "steps": "true",
            },
            timeout=15,
        )
        resp.raise_for_status()
        datos = resp.json()
    except Exception as e:
        logger.error("calcular_ruta_optima: %s", e)
        return None

    if datos.get("code") != "Ok" or not datos.get("trips"):
        logger.warning("OSRM no devolvió ruta válida: %s", datos.get("code"))
        return None

    trip = datos["trips"][0]
    waypoints = datos.get("waypoints", [])

    # Reconstruir orden óptimo de paradas
    # waypoints[0] es el origen, el resto son las paradas
    # Cada waypoint tiene "waypoint_index" que indica su posición en el trip
    paradas_con_orden = []
    for i, wp in enumerate(waypoints):
        if i == 0:
            continue  # Saltar origen
        parada_original = paradas[i - 1]
        paradas_con_orden.append({
            **parada_original,
            "orden_trip": wp.get("waypoint_index", i),
        })
    paradas_con_orden.sort(key=lambda x: x["orden_trip"])

    # Extraer geometría para Folium
    geometria = trip.get("geometry", {}).get("coordinates", [])

    # Extraer tramos
    tramos = []
    for leg in trip.get("legs", []):
        tramos.append({
            "distancia_km": round(leg["distance"] / 1000, 1),
            "duracion_min": round(leg["duration"] / 60, 1),
        })

    return {
        "paradas_ordenadas": paradas_con_orden,
        "distancia_total_km": round(trip["distance"] / 1000, 1),
        "duracion_total_min": round(trip["duration"] / 60, 1),
        "geometria": geometria,  # Lista de [lon, lat]
        "tramos": tramos,
    }
