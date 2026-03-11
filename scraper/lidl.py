# -*- coding: utf-8 -*-

"""
scraper/lidl.py - Scraper para LIDL España

Arquitectura técnica
--------------------
LIDL no tiene tienda online — los productos son del catálogo físico semanal.
La web usa fragmentos Vue/Nuxt que cargan datos vía XHR, pero la API subyacente
es accesible directamente con requests (sin Playwright).

Endpoint descubierto via DevTools:
    GET https://www.lidl.es/q/api/search
        ?q={termino}
        &category=Alimentación       ← filtro de categoría padre
        &fetchsize=1000              ← máximo permitido por la API
        &locale=es_ES
        &assortment=ES
        &offset=0
        &version=2.1.0

    Accept: application/mindshift.search+json;version=2

Respuesta JSON:
    {
        "numFound": 13,
        "maxfetchsize": 1000,
        "items": [
            {
                "resultClass": "product",
                "gridbox": {
                    "data": {
                        "erpNumber":   "11138947",
                        "fullTitle":   "MILBONA Leche semidesnatada",
                        "price": {
                            "price":   1.19,
                            "packaging": {"text": "1,5 l", "price": null}
                        },
                        "brand":       {"name": "MILBONA"},
                        "keyfacts":    {"description": "<ul><li>1,5 l</li></ul>"},
                        "image":       "https://www.lidl.es/assets/gcp9...",
                        "canonicalPath": "/p/milbona-leche-semidesnatada/p11138947",
                        "wonCategoryBreadcrumbs": [[..., {"name": "Queso y productos lácteos"}, ...]],
                        "stockAvailability": {"store": true, "online": false},
                        "onlineAvailable": false
                    }
                }
            }
        ]
    }

Estrategia de cobertura
-----------------------
Como la API filtra por búsqueda de texto (q=), se usa la misma estrategia que
el scraper de Eroski: lista de términos que cubren todo el catálogo alimentario.

La API devuelve hasta 1000 resultados por llamada. Con fetchsize=1000 y
paginación por offset se cubre el catálogo completo.

Se añade &category=Alimentación para evitar resultados de electrónica/moda.

Cobertura esperada: ~500-1500 productos de alimentación, bebidas e higiene.
Tiempo estimado: ~2-3 minutos (solo requests, sin Playwright).
"""

import re
import time
import logging

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

BASE_URL     = "https://www.lidl.es"
URL_BUSQUEDA = f"{BASE_URL}/q/api/search"

HEADERS = {
    "Accept":          "application/mindshift.search+json;version=2",
    "Accept-Language": "es-ES,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Referer":         BASE_URL + "/",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-origin",
}

# Parámetros base de la API
PARAMS_BASE = {
    "locale":     "es_ES",
    "assortment": "ES",
    "fetchsize":  1000,
    "offset":     0,
    "version":    "2.1.0",
    "category":   "Alimentación",   # filtra resultados a alimentación/hogar
}

# Pausa entre peticiones (segundos)
PAUSA = 0.8

# Términos de búsqueda que cubren el catálogo de supermercado
# Estrategia igual que Eroski: términos amplios por sección
TERMINOS_BUSQUEDA = [
    # Lácteos
    "leche", "yogur", "queso", "mantequilla", "nata", "kefir",
    # Huevos
    "huevos",
    # Carnes y embutidos
    "pollo", "cerdo", "ternera", "cordero", "pavo",
    "jamon", "chorizo", "salchichon", "mortadela", "lomo", "fuet",
    "salchicha", "bacon", "morcilla",
    # Pescado y marisco
    "salmon", "atun", "merluza", "bacalao", "gambas", "mejillones",
    "sardinas", "caballa",
    # Frutas y verduras
    "manzana", "naranja", "platano", "tomate", "lechuga", "zanahoria",
    "patata", "cebolla", "pimiento", "pepino", "calabacin",
    # Panadería y bollería
    "pan", "baguette", "croissant", "magdalena", "bizcocho",
    # Cereales y desayuno
    "cereales", "avena", "muesli", "granola",
    # Galletas y snacks
    "galletas", "crackers", "tortitas", "palomitas",
    "patatas fritas", "frutos secos", "almendras", "pistachos",
    # Pasta, arroz y legumbres
    "pasta", "espaguetis", "macarrones", "arroz", "lentejas",
    "garbanzos", "alubias", "quinoa",
    # Aceites y condimentos
    "aceite oliva", "aceite girasol", "vinagre", "sal", "pimienta",
    "especias", "oregano", "pimenton",
    # Salsas y conservas
    "tomate frito", "ketchup", "mayonesa", "mostaza",
    "atun lata", "conservas", "aceitunas", "pepinillos",
    "caldo", "sopa",
    # Café e infusiones
    "cafe", "te", "infusion", "manzanilla", "cafe molido", "capsulas cafe",
    # Chocolate y dulces
    "chocolate", "cacao", "nocilla", "mermelada", "miel",
    "caramelos", "chicles",
    # Congelados
    "pizza congelada", "croquetas", "nuggets", "verduras congeladas",
    "helado", "pescado congelado",
    # Platos preparados
    "cocido", "fabada", "gazpacho", "hummus", "guacamole",
    # Bebidas
    "agua", "refresco", "cola", "zumo", "naranjada", "limonada",
    "cerveza", "vino", "cava", "sidra",
    # Droguería e higiene (incluidas en Alimentación Lidl)
    "detergente", "suavizante", "lavavajillas", "lejia",
    "papel higienico", "papel cocina", "servilletas",
    "gel ducha", "champu", "jabon manos", "desodorante",
    "pasta dientes", "colutorio",
    # Bebé
    "panales", "leche bebe", "papilla",
    # Mascotas
    "pienso perro", "pienso gato", "comida perro", "comida gato",
]


# ─── Punto de entrada ────────────────────────────────────────────────────────

def gestion_lidl() -> pd.DataFrame:
    """
    Función principal. Extrae el catálogo de LIDL España vía API REST.

    No requiere Playwright. Usa requests directos al endpoint de búsqueda
    descubierto en DevTools: /q/api/search con Accept mindshift.

    Returns:
        pd.DataFrame con columnas normalizadas del proyecto.
    """
    t0 = time.time()
    logger.info("Iniciando extracción de LIDL...")

    filas: list[dict] = []
    ids_vistos: set[str] = set()
    total_terminos = len(TERMINOS_BUSQUEDA)

    for idx, termino in enumerate(TERMINOS_BUSQUEDA, start=1):
        if idx % 10 == 0 or idx == 1:
            logger.info(
                "[%d/%d] Procesando término '%s' — %d productos acumulados",
                idx, total_terminos, termino, len(filas),
            )

        productos = _buscar_termino(termino)

        nuevos = 0
        for prod in productos:
            erp = prod.get("Id", "")
            if erp and erp not in ids_vistos:
                ids_vistos.add(erp)
                filas.append(prod)
                nuevos += 1

        if nuevos:
            logger.debug("  '%s': %d nuevos productos", termino, nuevos)

        time.sleep(PAUSA)

    if not filas:
        logger.warning("LIDL: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(filas)
    duracion = int(time.time() - t0)
    logger.info(
        "LIDL completado: %d productos únicos en %dm %ds",
        len(df), duracion // 60, duracion % 60,
    )
    return df


# ─── Búsqueda por término ─────────────────────────────────────────────────────

def _buscar_termino(termino: str) -> list[dict]:
    """
    Consulta la API de búsqueda de LIDL para un término dado.

    Maneja paginación automática si numFound > fetchsize.

    Args:
        termino: Término de búsqueda (ej: "leche", "yogur").

    Returns:
        Lista de dicts de productos mapeados al esquema del proyecto.
    """
    productos: list[dict] = []
    offset = 0
    fetchsize = int(PARAMS_BASE["fetchsize"])

    while True:
        params = {
            **PARAMS_BASE,
            "q":      termino,
            "offset": offset,
        }

        try:
            resp = requests.get(
                URL_BUSQUEDA,
                params=params,
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            datos = resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning("  Error API '%s' (offset=%d): %s", termino, offset, e)
            break
        except ValueError as e:
            logger.warning("  JSON inválido '%s': %s", termino, e)
            break

        items = datos.get("items", [])
        num_found = datos.get("numFound", 0)

        for item in items:
            if item.get("resultClass") != "product":
                continue
            data = item.get("gridbox", {}).get("data", {})
            if not data:
                continue
            fila = _mapear_producto(data)
            if fila:
                productos.append(fila)

        offset += fetchsize

        # Continuar paginando solo si hay más resultados
        if offset >= num_found or not items:
            break

        time.sleep(PAUSA)

    return productos


# ─── Mapeo de campos ──────────────────────────────────────────────────────────

def _mapear_producto(data: dict) -> dict | None:
    """
    Transforma un dict gridbox.data de la API de LIDL al esquema del proyecto.

    Estructura confirmada via DevTools (leche Milbona como ejemplo):
        erpNumber:      "11138947"
        fullTitle:      "MILBONA Leche semidesnatada"
        price.price:    1.19
        price.packaging.text:   "1,5 l"
        price.packaging.price:  null  (precio por unidad, cuando existe)
        brand.name:     "MILBONA"
        keyfacts.description:   "<ul><li>1,5 l</li></ul>"
        image:          "https://www.lidl.es/assets/gcp9..."
        canonicalPath:  "/p/milbona-leche-semidesnatada/p11138947"
        wonCategoryBreadcrumbs[0][1].name: "Queso y productos lácteos"

    Args:
        data: Dict con los datos del producto (gridbox.data).

    Returns:
        Dict con el esquema normalizado, o None si faltan campos esenciales.
    """
    # ── Campos obligatorios ──────────────────────────────────────────────────
    erp    = str(data.get("erpNumber", "")).strip()
    nombre = (data.get("fullTitle") or data.get("name") or "").strip()

    precio_raw = data.get("price", {}).get("price")
    if not erp or not nombre or precio_raw is None:
        return None

    try:
        precio = float(precio_raw)
    except (TypeError, ValueError):
        return None

    if precio <= 0:
        return None

    # ── Formato / packaging ──────────────────────────────────────────────────
    # Fuente 1: price.packaging.text  →  "1,5 l", "500 g", "6 x 1 l"
    precio_obj  = data.get("price", {})
    packaging   = precio_obj.get("packaging", {}) or {}
    formato = (packaging.get("text") or "").strip()

    # Fuente 2: keyfacts.description  →  "<ul><li>1,5 l</li></ul>"
    if not formato:
        desc_html = data.get("keyfacts", {}).get("description", "") or ""
        m = re.search(r"<li>([^<]+)</li>", desc_html)
        if m:
            formato = m.group(1).strip()

    # Normalizar separador decimal: "1,5 l" → "1.5 l"
    formato = formato.replace(",", ".")

    # ── Precio por unidad ────────────────────────────────────────────────────
    # packaging.price es el precio por kg/l cuando está disponible en la API
    # En la mayoría de casos es null — normalizer.py lo calculará
    precio_unitario: float | None = None
    pkg_price = packaging.get("price")
    if pkg_price is not None:
        try:
            precio_unitario = float(pkg_price)
        except (TypeError, ValueError):
            pass

    # ── Marca ─────────────────────────────────────────────────────────────────
    marca = (data.get("brand", {}) or {}).get("name", "") or ""

    # ── Categoría ────────────────────────────────────────────────────────────
    # wonCategoryBreadcrumbs[0][1].name  →  "Queso y productos lácteos"
    categoria = ""
    breadcrumbs = data.get("wonCategoryBreadcrumbs", []) or []
    if breadcrumbs and isinstance(breadcrumbs[0], list) and len(breadcrumbs[0]) > 1:
        cat_bc = breadcrumbs[0][1].get("name", "") if isinstance(breadcrumbs[0][1], dict) else ""
        if cat_bc:
            categoria = cat_bc
    # Fallback: campo category directo
    if not categoria:
        categoria = data.get("category", "") or ""

    # ── URLs ──────────────────────────────────────────────────────────────────
    canonical = data.get("canonicalPath") or data.get("canonicalUrl") or ""
    if canonical and not canonical.startswith("http"):
        url = BASE_URL + canonical
    else:
        url = canonical or f"{BASE_URL}/p/producto/p{erp}"

    url_imagen = data.get("image", "") or ""
    if isinstance(url_imagen, list) and url_imagen:
        url_imagen = url_imagen[0].get("url", "") if isinstance(url_imagen[0], dict) else ""

    return {
        "Id":                erp,
        "Nombre":            nombre,
        "Precio":            precio,
        "Precio_por_unidad": precio_unitario,   # normalizer.py lo calculará si es None
        "Formato":           formato,
        "Categoria":         categoria,
        "Supermercado":      "Lidl",
        "Url":               url,
        "Url_imagen":        url_imagen,
        "Marca":             marca,
    }
