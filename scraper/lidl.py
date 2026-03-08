# -*- coding: utf-8 -*-

"""
scraper/lidl.py - Scraper para LIDL

Utiliza la API REST interna de www.lidl.es. No requiere cookies ni autenticación.

Estrategia:
  1. Obtener el árbol de navegación completo desde:
       GET https://www.lidl.es/n/es-ES/mobile-navigation
     Se parsean todas las URLs del tipo /h/{slug}/h{id} para extraer
     los IDs de subcategoría hoja (las que no tienen hijos, evitando duplicados).

  2. Para cada subcategoría, consultar la API de búsqueda con fetchsize=1000:
       GET https://www.lidl.es/q/api/search?q=*&category={nombre}&fetchsize=1000
           &locale=es_ES&assortment=ES&offset=0&version=2.1.0

  3. Mapear los campos del JSON al DataFrame normalizado del proyecto.

Campos extraídos por producto (items[].gridbox.data):
  - erpNumber          → Id
  - fullTitle          → Nombre
  - price.price        → Precio
  - price.packaging.text → Formato
  - brand.name         → Marca (disponible directamente, no requiere normalizer)
  - canonicalPath      → Url  (prefijo https://www.lidl.es)
  - image              → Url_imagen
  - wonCategoryBreadcrumbs[0][1].name → Categoria

Cobertura esperada: catálogo completo (~5.000-8.000 productos).
Tiempo estimado: ~3-5 minutos (API REST sin Playwright).
"""

import re
import time
import logging

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

URL_NAVEGACION = "https://www.lidl.es/n/es-ES/mobile-navigation"
URL_BUSQUEDA   = "https://www.lidl.es/q/api/search"
BASE_URL       = "https://www.lidl.es"

HEADERS = {
    "Accept": "application/mindshift.search+json;version=2",
    "Accept-Language": "es-ES,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.lidl.es/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

PARAMS_BASE = {
    "locale":     "es_ES",
    "assortment": "ES",
    "fetchsize":  1000,
    "offset":     0,
    "version":    "2.1.0",
}

# Pausa entre peticiones (segundos)
REQUEST_DELAY = 0.5


# ─── Punto de entrada ────────────────────────────────────────────────────────

def gestion_lidl() -> pd.DataFrame:
    """
    Función principal. Orquesta la extracción del catálogo completo de LIDL.

    Returns:
        pd.DataFrame con columnas normalizadas del proyecto.
    """
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de LIDL...")

    categorias = _obtener_categorias()
    if not categorias:
        logger.error("No se han podido obtener las categorías de LIDL.")
        return pd.DataFrame()

    logger.info("Categorías únicas a scrappear: %d", len(categorias))

    df_total = _extraer_productos(categorias)

    duracion = int(time.time() - tiempo_inicio)
    logger.info(
        "LIDL completado: %d productos en %dm %ds",
        len(df_total), duracion // 60, duracion % 60
    )
    return df_total


# ─── Obtención de categorías ─────────────────────────────────────────────────

def _obtener_categorias() -> list[dict]:
    """
    Descarga el árbol de navegación y extrae las categorías hoja únicas.

    Parsea todas las líneas del tipo:
        [Nombre de categoría](/h/slug-categoria/h10XXXXXX)

    Devuelve una lista de dicts con claves:
        - nombre:  str  (nombre legible, usado como parámetro &category=)
        - id:      str  (ID numérico LIDL, ej. "10084405")
        - slug:    str  (slug de la URL, ej. "exprimidores")

    Se eliminan duplicados por ID para no scrappear la misma subcategoría
    dos veces cuando aparece en múltiples secciones del menú.
    """
    try:
        resp = requests.get(URL_NAVEGACION, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        contenido = resp.text
    except requests.exceptions.RequestException as e:
        logger.error("Error descargando árbol de navegación de LIDL: %s", e)
        return []

    # Patrón: [Nombre](/h/slug/hID)  — ignora URLs con parámetros pageId
    patron = re.compile(r'\[([^\]]+)\]\(/h/([^/]+)/h(\d+)(?:\?[^)]+)?\)')
    coincidencias = patron.findall(contenido)

    categorias_vistas = set()
    categorias = []

    for nombre, slug, cat_id in coincidencias:
        if cat_id not in categorias_vistas:
            categorias_vistas.add(cat_id)
            categorias.append({
                "nombre": nombre.strip(),
                "id":     cat_id,
                "slug":   slug,
            })

    logger.info("Total entradas en navegación: %d → únicas: %d",
                len(coincidencias), len(categorias))
    return categorias


# ─── Extracción de productos ─────────────────────────────────────────────────

def _extraer_productos(categorias: list[dict]) -> pd.DataFrame:
    """
    Itera todas las categorías y consulta la API de búsqueda para cada una.

    Args:
        categorias: Lista de dicts con claves nombre, id, slug.

    Returns:
        pd.DataFrame con todos los productos concatenados.
    """
    filas = []
    ids_producto_vistos = set()
    total = len(categorias)

    for idx, cat in enumerate(categorias, start=1):
        logger.info("[%d/%d] %s (h%s)", idx, total, cat["nombre"], cat["id"])

        productos_cat = _pedir_pagina(cat["nombre"], cat["id"])

        nuevos = 0
        for p in productos_cat:
            erp = str(p.get("erpNumber", "")).strip()
            if not erp or erp in ids_producto_vistos:
                continue
            ids_producto_vistos.add(erp)

            fila = _mapear_producto(p, cat["nombre"])
            if fila:
                filas.append(fila)
                nuevos += 1

        logger.debug("  → %d nuevos productos (total acumulado: %d)",
                     nuevos, len(filas))
        time.sleep(REQUEST_DELAY)

    return pd.DataFrame(filas) if filas else pd.DataFrame()


def _pedir_pagina(nombre_categoria: str, cat_id: str) -> list[dict]:
    """
    Realiza la petición a la API de búsqueda para una categoría.

    Usa q=* (todos los productos) con el ID de categoría como filtro.
    Si la respuesta supera fetchsize=1000 se registra un aviso pero no
    se pagina (LIDL raramente supera esa cifra por subcategoría).

    Args:
        nombre_categoria: Nombre legible de la categoría.
        cat_id:           ID numérico de la categoría (ej. "10084405").

    Returns:
        Lista de dicts de datos de producto (campo gridbox.data de cada item).
    """
    params = {
        **PARAMS_BASE,
        "q":        "*",
        "category": f"[{nombre_categoria}]",  # formato requerido por la API
        # Alternativa: filtrar por ID de categoría directamente
        # "categoryId": cat_id,
    }

    try:
        resp = requests.get(
            URL_BUSQUEDA, params=params, headers=HEADERS, timeout=20
        )
        resp.raise_for_status()
        datos = resp.json()
    except requests.exceptions.RequestException as e:
        logger.warning("  Error en categoría %s: %s", nombre_categoria, e)
        return []
    except ValueError as e:
        logger.warning("  JSON inválido en categoría %s: %s", nombre_categoria, e)
        return []

    items = datos.get("items", [])
    num_encontrados = datos.get("numFound", 0)

    if num_encontrados > PARAMS_BASE["fetchsize"]:
        logger.warning(
            "  Categoría '%s' tiene %d productos pero solo se obtuvieron %d. "
            "Considera paginar con &offset=.",
            nombre_categoria, num_encontrados, len(items)
        )

    # Extraer el dict de datos del producto desde la estructura anidada
    productos = []
    for item in items:
        if item.get("resultClass") != "product":
            continue
        gridbox = item.get("gridbox", {})
        data = gridbox.get("data", {})
        if data:
            productos.append(data)

    return productos


# ─── Mapeo de campos ─────────────────────────────────────────────────────────

def _mapear_producto(data: dict, categoria_scrapeada: str) -> dict | None:
    """
    Transforma un dict de datos de producto LIDL al esquema del proyecto.

    Esquema de salida:
        Id, Nombre, Precio, Precio_por_unidad, Formato,
        Categoria, Supermercado, Url, Url_imagen

    Args:
        data:                 Dict con los datos del producto (gridbox.data).
        categoria_scrapeada:  Nombre de la categoría usada en la petición.

    Returns:
        Dict con el esquema normalizado, o None si faltan campos esenciales.
    """
    # ── Campos obligatorios ──
    erp    = str(data.get("erpNumber", "")).strip()
    nombre = data.get("fullTitle", "").strip()
    precio_raw = data.get("price", {}).get("price")

    if not erp or not nombre or precio_raw is None:
        return None

    try:
        precio = float(precio_raw)
    except (TypeError, ValueError):
        return None

    # ── Formato / packaging ──
    formato = (
        data.get("price", {})
            .get("packaging", {})
            .get("text", "")
        or ""
    ).strip()

    # Si el formato viene vacío, intentar extraerlo de keyfacts.description
    # que contiene HTML tipo "<ul><li>1,5 l</li></ul>"
    if not formato:
        desc_html = data.get("keyfacts", {}).get("description", "")
        match = re.search(r'<li>([^<]+)</li>', desc_html)
        if match:
            formato = match.group(1).strip()

    # ── Categoría ──
    # Preferimos la categoría del árbol de breadcrumbs del producto
    # si está disponible; si no, usamos la categoría de la petición.
    categoria = categoria_scrapeada
    breadcrumbs = data.get("wonCategoryBreadcrumbs", [])
    if breadcrumbs and len(breadcrumbs[0]) > 1:
        categoria = breadcrumbs[0][1].get("name", categoria_scrapeada)

    # ── URL del producto ──
    canonical = data.get("canonicalPath", "")
    url = (BASE_URL + canonical) if canonical else ""

    # ── URL de imagen ──
    url_imagen = data.get("image", "")

    return {
        "Id":               erp,
        "Nombre":           nombre,
        "Precio":           precio,
        "Precio_por_unidad": None,   # Se calcula en normalizer.py
        "Formato":          formato,
        "Categoria":        categoria,
        "Supermercado":     "Lidl",
        "Url":              url,
        "Url_imagen":       url_imagen,
    }
