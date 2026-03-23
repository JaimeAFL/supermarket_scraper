"""
scraper/carrefour.py - Scraper para Carrefour

Usa la API Empathy/search-api confirmada por inspección de red (marzo 2026).
No requiere Playwright ni COOKIE_CARREFOUR — llamadas HTTP directas con requests.

Endpoint: GET /search-api/query/v1/search
Paginación: parámetros start (offset) y rows (tamaño de página = 24)
"""

import os
import logging
import time
import random
import string

import requests
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_URL = "https://www.carrefour.es"
_API_URL  = f"{BASE_URL}/search-api/query/v1/search"

# Parámetros fijos confirmados por inspección de red (marzo 2026)
_PARAMS_FIJOS = {
    "internal":                            "true",
    "instance":                            "x-carrefour",
    "env":                                 BASE_URL,
    "scope":                               "desktop",
    "lang":                                "es",
    "session":                             "empathy",
    "citrusCatalog":                       "food",
    "catalog":                             "food",
    "baseUrlCitrus":                       BASE_URL,
    "enabled":                             "true",
    "hasConsent":                          "true",
    "siteKey":                             "wFOzqveg",
    "grid_def_search_sponsor_product":     "3,5,11,13,19",
    "grid_def_search_butterfly_banner":    "7-8,15-16",
    "grid_def_search_sponsor_product_tablet":  "2,4,11,13,19",
    "grid_def_search_butterfly_banner_tablet":  "6,12",
    "grid_def_search_sponsor_product_mobile":   "2,4,11,13,19",
    "grid_def_search_butterfly_banner_mobile":  "6,12",
    "grid_def_search_luckycart_banner":    "22",
    "empathypoc":                          "false",
    "origin":                              "url:external",
}

_ROWS       = 24   # productos por página (valor real de la API)
_MAX_PAGINAS = 5   # máximo de páginas por término (= hasta 120 productos)

# Cabeceras que imitan Chrome 134 para evitar bloqueos
_HEADERS = {
    "Accept":             "application/json, text/plain, */*",
    "Accept-Encoding":    "gzip, deflate, br",
    "Accept-Language":    "es-ES,es;q=0.9",
    "Origin":             BASE_URL,
    "Referer":            f"{BASE_URL}/",
    "Sec-Ch-Ua":          '"Chromium";v="134", "Google Chrome";v="134", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile":   "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest":     "empty",
    "Sec-Fetch-Mode":     "cors",
    "Sec-Fetch-Site":     "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
}

TERMINOS_BUSQUEDA = [
    "leche", "yogur", "queso", "mantequilla", "nata", "natillas", "flan",
    "huevos", "fruta", "verdura", "patatas", "tomate", "cebolla", "zanahoria",
    "lechuga", "manzana", "naranja", "platano", "pera",
    "carne", "pollo", "cerdo", "ternera", "cordero", "jamon", "chorizo",
    "salchichon", "pavo", "fuet", "mortadela", "salchicha", "bacon",
    "pescado", "salmon", "atun", "merluza", "gambas", "marisco", "mejillones",
    "pan", "cereales", "galletas", "bolleria", "tostadas",
    "pasta", "arroz", "legumbres", "lentejas", "garbanzos", "alubias",
    "aceite", "vinagre", "sal", "azucar", "harina", "especias",
    "conserva", "tomate frito", "salsa", "mayonesa", "ketchup",
    "caldo", "sopa",
    "cafe", "te", "infusion", "cacao", "chocolate",
    "miel", "mermelada", "nocilla",
    "patatas fritas", "frutos secos", "aceitunas", "snacks",
    "pizza", "helado", "croquetas", "nuggets",
    "agua", "refresco", "coca cola", "zumo", "cerveza", "vino",
    "detergente", "suavizante", "lejia", "lavavajillas",
    "papel higienico", "papel cocina", "bolsas basura",
    "gel ducha", "champu", "jabon", "desodorante", "pasta dientes",
    "crema facial", "colonia",
    "panales", "toallitas bebe",
    "comida perro", "comida gato",
]


def _generar_shopper_id():
    """Genera un ID de comprador anónimo aleatorio (28 chars alfanuméricos)."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=28))


def _parsear_docs(docs, categoria_fallback=""):
    """Extrae productos de content.docs[] — estructura confirmada por inspección."""
    productos = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        try:
            precio = doc.get("active_price")
            if precio is None or float(precio) <= 0:
                continue

            product_id = str(doc.get("product_id") or "").strip()
            if not product_id:
                continue

            nombre = str(doc.get("display_name") or "").strip()
            if not nombre:
                continue

            url_prod = str(doc.get("url") or "").strip()
            if url_prod and not url_prod.startswith("http"):
                url_prod = BASE_URL + url_prod

            productos.append({
                "Id":            product_id,
                "Nombre":        nombre,
                "Precio":        float(precio),
                "Precio_unidad": str(doc.get("price_per_unit_text") or "").strip(),
                "Categoria":     str(doc.get("section") or categoria_fallback),
                "Supermercado":  "Carrefour",
                "URL":           url_prod,
                "URL_imagen":    str(doc.get("image_path") or "").strip(),
            })
        except Exception:
            continue
    return productos


def _buscar_termino(session, termino, store, shopper_id, ids_vistos):
    """Llama a la API paginando con start/rows hasta agotar resultados o _MAX_PAGINAS."""
    nuevos = []
    for pagina in range(_MAX_PAGINAS):
        params = {
            **_PARAMS_FIJOS,
            "store":     store,
            "shopperId": shopper_id,
            "query":     termino,
            "start":     pagina * _ROWS,
            "rows":      _ROWS,
        }
        try:
            resp = session.get(_API_URL, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(
                    f"Carrefour '{termino}' pág {pagina + 1}: "
                    f"HTTP {resp.status_code}"
                )
                break
            data = resp.json()
        except Exception as exc:
            logger.warning(f"Carrefour '{termino}' pág {pagina + 1}: {exc}")
            break

        content = data.get("content")
        docs = (content.get("docs") or []) if isinstance(content, dict) else []

        if not docs:
            break

        for p in _parsear_docs(docs, termino.capitalize()):
            if p["Id"] not in ids_vistos:
                ids_vistos.add(p["Id"])
                nuevos.append(p)

        # Si la página vino incompleta no hay más resultados
        if len(docs) < _ROWS:
            break

        time.sleep(0.3)  # pausa cortés entre páginas

    return nuevos


def gestion_carrefour():
    """Punto de entrada principal. Devuelve DataFrame con todos los productos."""
    load_dotenv()
    inicio = time.time()
    logger.info("Iniciando extracción de Carrefour (API directa, sin Playwright)...")

    # store: ID de tienda Carrefour según código postal.
    # 005290 corresponde a Madrid (CP 28001).
    # Configurable como secreto CARREFOUR_STORE_ID en el Codespace.
    store     = os.getenv("CARREFOUR_STORE_ID", "005290")
    shopper_id = _generar_shopper_id()

    session = requests.Session()
    session.headers.update(_HEADERS)

    # Visitar la home primero para obtener cookies de sesión
    try:
        r = session.get(BASE_URL, timeout=15)
        logger.info(f"Sesión inicializada (home: HTTP {r.status_code})")
    except Exception as exc:
        logger.warning(f"No se pudo inicializar sesión: {exc}")
    time.sleep(1.5)

    todos     = []
    ids_vistos = set()

    for termino in TERMINOS_BUSQUEDA:
        nuevos = _buscar_termino(session, termino, store, shopper_id, ids_vistos)
        todos.extend(nuevos)
        if nuevos:
            logger.info(
                f"  '{termino}' → {len(nuevos)} nuevos "
                f"(total acumulado: {len(todos)})"
            )
        time.sleep(0.4)  # pausa entre términos

    duracion = time.time() - inicio
    logger.info(
        f"Carrefour completado: {len(todos)} productos "
        f"en {duracion / 60:.1f} min"
    )

    return pd.DataFrame(todos) if todos else pd.DataFrame()
