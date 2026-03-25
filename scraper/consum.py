# -*- coding: utf-8 -*-

"""
scraper/consum.py - Scraper para Consum

Endpoint
--------
    GET https://tienda.consum.es/api/rest/V1.0/catalog/product
        ?offset={N}
        &limit=100          ← máximo real de la API (limit=200 devuelve igual 100)

    Sin autenticación. Sin cookies. Sin Playwright.

Respuesta JSON:
    {
        "totalCount": 9109,
        "hasMore": true,
        "products": [
            {
                "id":   4667,
                "code": "1669",
                "ean":  "8423230065137",
                "productData": {
                    "name":     "Rabanito Bolsa",
                    "brand":    {"name": "EL DULZE"},
                    "url":      "https://tienda.consum.es/es/p/rabanito-bolsa/1669",
                    "imageURL": "https://cdn-consum.../1669.jpg",
                    "format":   "250 g",
                },
                "priceData": {
                    "prices": [
                        {"id": "PRICE",       "value": {"centAmount": 1.15, "centUnitAmount": 4.60}},
                        {"id": "OFFER_PRICE", "value": {"centAmount": 0.99, "centUnitAmount": 3.96}}
                    ],
                    "unitPriceUnitType": "1 Kg",   ← unidad del precio unitario
                },
                "categories": [{"id": 2214, "name": "Zanahorias y otras raíces"}]
            }
        ]
    }

Notas:
- centAmount      → precio en euros (ya es float, no centavos pese al nombre)
- centUnitAmount  → precio por kg/L en euros
- OFFER_PRICE existe solo cuando hay promoción activa; se usa si está presente
- unitPriceUnitType puede ser "1 Kg", "1 L", "1 ud", "" (vacío = sin precio unitario)
- 9.109 productos, 92 páginas × ~1s = ~2 min

Cobertura: ~9.100 productos de supermercado online.
Tiempo estimado: ~2 minutos.
"""

import time
import logging

import requests
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL  = "https://tienda.consum.es"
URL_API   = f"{BASE_URL}/api/rest/V1.0/catalog/product"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer":         BASE_URL + "/",
}

LIMIT      = 100    # máximo real de la API
PAUSA      = 0.8    # segundos entre páginas


def gestion_consum() -> pd.DataFrame:
    """
    Extrae el catálogo completo de Consum vía API REST paginada.

    Returns:
        pd.DataFrame con columnas normalizadas del proyecto.
    """
    t0 = time.time()
    logger.info("Iniciando extracción de Consum...")

    # Obtener total de productos
    try:
        r = requests.get(URL_API, params={"offset": 0, "limit": 1},
                         headers=HEADERS, timeout=15)
        r.raise_for_status()
        total = r.json().get("totalCount", 0)
    except Exception as e:
        logger.error("No se pudo conectar con la API de Consum: %s", e)
        return pd.DataFrame()

    if not total:
        logger.error("Consum: totalCount=0, abortando.")
        return pd.DataFrame()

    paginas = (total + LIMIT - 1) // LIMIT
    logger.info("Total productos: %d → %d páginas", total, paginas)

    filas: list[dict] = []
    ids_vistos: set[str] = set()

    for pagina in range(paginas):
        offset = pagina * LIMIT

        if pagina > 0 and pagina % 20 == 0:
            logger.info(
                "Progreso: página %d/%d — %d productos acumulados",
                pagina, paginas, len(filas),
            )

        try:
            r = requests.get(
                URL_API,
                params={"offset": offset, "limit": LIMIT},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            datos = r.json()
        except requests.exceptions.RequestException as e:
            logger.warning("Error en página %d (offset=%d): %s", pagina, offset, e)
            time.sleep(2)
            continue
        except ValueError as e:
            logger.warning("JSON inválido página %d: %s", pagina, e)
            continue

        productos_pagina = datos.get("products", [])
        if not productos_pagina:
            logger.debug("Página %d vacía, terminando paginación.", pagina)
            break

        for prod_raw in productos_pagina:
            fila = _mapear_producto(prod_raw)
            if not fila:
                continue
            erp = fila["Id"]
            if erp not in ids_vistos:
                ids_vistos.add(erp)
                filas.append(fila)

        if not datos.get("hasMore", False):
            break

        time.sleep(PAUSA)

    if not filas:
        logger.warning("Consum: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(filas)
    duracion = int(time.time() - t0)
    logger.info(
        "Consum completado: %d productos únicos en %dm %ds",
        len(df), duracion // 60, duracion % 60,
    )
    return df


def _mapear_producto(prod: dict) -> dict | None:
    """
    Transforma un producto de la API de Consum al esquema del proyecto.

    Usa OFFER_PRICE si está disponible (precio de oferta activo),
    si no usa PRICE (precio regular).

    Args:
        prod: Dict de producto tal como devuelve la API.

    Returns:
        Dict con el esquema normalizado, o None si faltan campos esenciales.
    """
    # ── ID ────────────────────────────────────────────────────────────────────
    erp = str(prod.get("code") or prod.get("id") or "").strip()
    if not erp:
        return None

    # ── Datos del producto ────────────────────────────────────────────────────
    prod_data  = prod.get("productData") or {}
    price_data = prod.get("priceData") or {}

    nombre = (prod_data.get("name") or "").strip()
    if not nombre:
        return None

    # ── Precio — preferir oferta si existe ───────────────────────────────────
    precios = {p["id"]: p["value"] for p in price_data.get("prices", []) if "id" in p and "value" in p}

    valor = precios.get("OFFER_PRICE") or precios.get("PRICE")
    if not valor:
        return None

    try:
        precio = float(valor["centAmount"])
    except (KeyError, TypeError, ValueError):
        return None

    if precio <= 0:
        return None

    # ── Precio por unidad ─────────────────────────────────────────────────────
    precio_unitario: float | None = None
    try:
        precio_unitario = float(valor["centUnitAmount"])
        if precio_unitario <= 0:
            precio_unitario = None
    except (KeyError, TypeError, ValueError):
        pass

    # ── Formato ───────────────────────────────────────────────────────────────
    # productData.format  →  "250 g", "1 L", "Pieza precio aprox.", ""
    # unitPriceUnitType   →  "1 Kg", "1 L", "1 ud"
    # Se usa format si tiene contenido útil; si no, unitPriceUnitType como fallback
    formato = (prod_data.get("format") or "").strip()
    unit_type = (price_data.get("unitPriceUnitType") or "").strip()

    # unitPriceUnitType como fallback solo si format está vacío
    if not formato and unit_type and unit_type not in ("1 ud", "1 Ud"):
        formato = unit_type

    # ── Marca ─────────────────────────────────────────────────────────────────
    marca = (prod_data.get("brand") or {}).get("name") or ""
    marca = marca.strip()
    if marca in ("-", "---", "0"):
        marca = ""

    # ── Categoría ─────────────────────────────────────────────────────────────
    # categories[0] es la categoría principal (type=0)
    # type=1 son etiquetas promocionales ("Ofertas en frescos") — se ignoran
    categoria = ""
    for cat in prod.get("categories", []):
        if cat.get("type") == 0:
            categoria = cat.get("name", "")
            break

    # ── URLs ──────────────────────────────────────────────────────────────────
    url       = prod_data.get("url") or f"{BASE_URL}/es/p/{erp}"
    url_imagen = prod_data.get("imageURL") or ""

    # Si hay imágenes adicionales en media, usar la primera (mejor calidad)
    media = prod.get("media") or []
    if media and isinstance(media[0], dict):
        url_imagen = media[0].get("url") or url_imagen

    return {
        "Id":                erp,
        "Nombre":            nombre,
        "Precio":            precio,
        "Precio_por_unidad": precio_unitario,
        "Formato":           formato,
        "Categoria":         categoria,
        "Supermercado":      "Consum",
        "Url":               url,
        "Url_imagen":        url_imagen,
        "Marca":             marca,
    }
