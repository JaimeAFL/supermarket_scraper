# -*- coding: utf-8 -*-

"""
scraper/condis.py - Scraper para Condis

Condis usa el motor de búsqueda Empathy (api.empathy.co) como backend
del catálogo de su tienda online. La API es accesible directamente
con requests (sin Playwright, sin autenticación).

Endpoint de búsqueda
--------------------
    GET https://api.empathy.co/search/v1/query/condis/search
        ?query={término}
        &lang=es
        &rows=100
        &start={offset}
        &store=718

Endpoint de browse por categoría (estrategia elegida)
------------------------------------------------------
    GET https://api.empathy.co/search/v1/query/condis/browse
        ?lang=es
        &rows=100
        &start={offset}
        &store=718
        &browseField=parentCategory
        &browseValue={categoryId}      ← ej: "c09__cat00140001"

Los categoryIds se extraen del HTML de la página principal de la tienda.
Son de la forma c{N}__cat{XXXXXXXX} y hay ~93 en el HTML.

Respuesta JSON
--------------
    {
        "catalog": {
            "numFound": 259,
            "pagination": {"total": 259, "start": 0, "rows": 100},
            "content": [
                {
                    "id":          "704048",
                    "description": "LECHE CONDIS SEMIDESNATADA 1 L",
                    "brand":       "CONDIS",
                    "price": {
                        "current":    0.91,
                        "regular":    1.10,
                        "discounted": 0.91
                    },
                    "pum":         "0,91€/Litro",
                    "category":    ["Bebidas", "Leche", "Leche semidesnatada"],
                    "family":      "Leche",
                    "section":     "Bebidas",
                    "images":      ["/images/catalog/large/704048.jpg"],
                    "url":         "/leche-condis-semidesnatada-1-l/p/704048/es_ES",
                    "on_sale":     false,
                    "on_promotion": false,
                    "netWeight":   1
                }
            ]
        }
    }

Precio activo: price.current (ya aplica descuentos). Si price.current <
price.regular hay oferta activa.

Precio unitario: campo pum — texto como "0,91€/Litro", "2,40€/kg".
Se limpia y extrae el valor numérico.

Cobertura estimada: ~5.800 productos únicos (~7.300 brutos con solapamiento
entre categorías).
Tiempo estimado: ~4-6 minutos (93 categorías × paginación).
"""

import re
import time
import logging

import requests
import pandas as pd

logger = logging.getLogger(__name__)

BASE_WEB     = "https://compraonline.condis.es"
BASE_IMG     = "https://www.condis.es"
EMPATHY_BASE = "https://api.empathy.co/search/v1/query/condis"
STORE_ID     = "718"
ROWS         = 100
PAUSA        = 0.3   # segundos entre peticiones

HEADERS = {
    "Accept":          "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_WEB + "/",
    "Origin":  BASE_WEB,
}


def gestion_condis() -> pd.DataFrame:
    """
    Extrae el catálogo completo de Condis vía API de Empathy.

    1. Obtiene los categoryIds de la página principal de la tienda.
    2. Para cada categoría, pagina el endpoint browse hasta agotarla.
    3. Deduplica por id de producto.

    Returns:
        pd.DataFrame con columnas normalizadas del proyecto.
    """
    t0 = time.time()
    logger.info("Iniciando extracción de Condis...")

    cat_ids = _obtener_categorias()
    if not cat_ids:
        logger.error("Condis: no se pudieron obtener las categorías.")
        return pd.DataFrame()

    logger.info("Categorías encontradas: %d", len(cat_ids))

    ids_vistos: set[str] = set()
    filas: list[dict] = []

    for i, cat_id in enumerate(cat_ids, 1):
        productos_cat = _extraer_categoria(cat_id)
        nuevos = 0
        for prod in productos_cat:
            pid = prod.get("Id", "")
            if pid and pid not in ids_vistos:
                ids_vistos.add(pid)
                filas.append(prod)
                nuevos += 1

        if i % 10 == 0 or nuevos > 0:
            logger.info(
                "[%d/%d] %s → %d nuevos | total acumulado: %d",
                i, len(cat_ids), cat_id, nuevos, len(filas),
            )

    if not filas:
        logger.warning("Condis: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(filas)
    duracion = int(time.time() - t0)
    logger.info(
        "Condis completado: %d productos únicos en %dm %ds",
        len(df), duracion // 60, duracion % 60,
    )
    return df


def _obtener_categorias() -> list[str]:
    """
    Extrae los categoryIds de la página principal de la tienda Condis.

    Los IDs tienen el formato c{N}__cat{XXXXXXXX} y están embebidos en
    los scripts y datos de Next.js del HTML.

    Returns:
        Lista de categoryIds únicos ordenados.
    """
    try:
        r = requests.get(
            BASE_WEB + "/",
            headers={**HEADERS, "Accept": "text/html"},
            timeout=20,
        )
        r.raise_for_status()
        ids = sorted(set(re.findall(r'c\d+__cat\d+', r.text)))
        return ids
    except requests.exceptions.RequestException as e:
        logger.error("Error obteniendo categorías de Condis: %s", e)
        return []


def _extraer_categoria(cat_id: str) -> list[dict]:
    """
    Extrae todos los productos de una categoría paginando el endpoint browse.

    Args:
        cat_id: ID de categoría (ej: "c09__cat00140001").

    Returns:
        Lista de dicts de productos mapeados al esquema del proyecto.
    """
    productos: list[dict] = []
    start = 0

    while True:
        params = {
            "lang":         "es",
            "rows":         ROWS,
            "start":        start,
            "store":        STORE_ID,
            "browseField":  "parentCategory",
            "browseValue":  cat_id,
        }

        try:
            resp = requests.get(
                f"{EMPATHY_BASE}/browse",
                params=params,
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            datos = resp.json()
        except requests.exceptions.RequestException as e:
            logger.warning("Error en categoría %s (start=%d): %s", cat_id, start, e)
            break
        except ValueError as e:
            logger.warning("JSON inválido en categoría %s: %s", cat_id, e)
            break

        catalog = datos.get("catalog") or {}
        num_found = catalog.get("numFound", 0)
        items = catalog.get("content") or []

        for item in items:
            fila = _mapear_producto(item)
            if fila:
                productos.append(fila)

        start += ROWS
        if start >= num_found or not items:
            break

        time.sleep(PAUSA)

    return productos


def _extraer_formato_de_nombre(nombre: str) -> str:
    """
    Extrae el formato (tamaño) del nombre del producto.

    Condis incluye el tamaño en el nombre: "LECHE ASTURIANA 1 L",
    "YOGUR NATURAL 500 G", "AGUA MINERAL 6X1,5 L".

    Args:
        nombre: Nombre del producto en mayúsculas.

    Returns:
        Formato normalizado como "1 L", "500 ml", "6x1.5 L", o "" si no se encuentra.
    """
    UNIDADES = r"(ML|CL|L|GR?|KG|MG|LITROS?|UNIDADES?|UDS?|KILOS?|GRAMOS?|PACK\s*\d*)"
    CANTIDAD  = r"(\d+(?:[,.]\d+)?)"

    # Formato pack: "6X1,5 L" o "6 X 1.5L"
    m_pack = re.search(
        rf"{CANTIDAD}\s*[Xx]\s*{CANTIDAD}\s*{UNIDADES}", nombre, re.I
    )
    if m_pack:
        n     = m_pack.group(1)
        cant  = m_pack.group(2).replace(",", ".")
        unid  = _normalizar_unidad(m_pack.group(3))
        return f"{n}x{cant} {unid}"

    # Formato simple: "1 L", "500 G", "228 ML"
    m = re.search(rf"{CANTIDAD}\s*{UNIDADES}\b", nombre, re.I)
    if m:
        cant = m.group(1).replace(",", ".")
        unid = _normalizar_unidad(m.group(2))
        return f"{cant} {unid}"

    return ""


def _normalizar_unidad(unidad: str) -> str:
    """Normaliza una cadena de unidad a formato estándar del proyecto."""
    u = unidad.strip().upper()
    mapa = {
        "LITRO": "L", "LITROS": "L", "L": "L",
        "CL": "cl", "ML": "ml",
        "KG": "kg", "KILO": "kg", "KILOS": "kg",
        "G": "g", "GR": "g", "GRAMO": "g", "GRAMOS": "g", "MG": "g",
        "UNIDAD": "ud", "UNIDADES": "ud", "UD": "ud", "UDS": "ud",
    }
    for k, v in mapa.items():
        if u.startswith(k):
            return v
    return unidad.lower()


def _mapear_producto(item: dict) -> dict | None:
    """
    Transforma un producto de la API de Empathy al esquema del proyecto.

    Args:
        item: Dict del producto tal como viene de catalog.content.

    Returns:
        Dict normalizado o None si faltan campos esenciales.
    """
    # ── ID ────────────────────────────────────────────────────────────────────
    pid = str(item.get("id") or item.get("externalId") or "").strip()
    if not pid:
        return None

    # ── Nombre ────────────────────────────────────────────────────────────────
    nombre = (item.get("description") or "").strip()
    if not nombre:
        return None
    # Condis devuelve nombres en mayúsculas — convertir a título
    nombre = nombre.title()

    # ── Precio ────────────────────────────────────────────────────────────────
    precio_info = item.get("price") or {}
    precio = precio_info.get("current") or precio_info.get("regular")
    if not precio:
        return None
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        return None
    if precio <= 0:
        return None

    # ── Precio unitario (pum) ─────────────────────────────────────────────────
    # pum es texto: "0,91€/Litro", "2,40€/kg", "1,20€/Unidad"
    precio_unitario: float | None = None
    pum_raw = (item.get("pum") or "").strip()
    if pum_raw:
        # Extraer valor numérico: "0,91€/Litro" → 0.91
        m = re.match(r"^([\d,\.]+)", pum_raw.replace(",", "."))
        if m:
            try:
                precio_unitario = float(m.group(1))
            except ValueError:
                pass

    # ── Formato ───────────────────────────────────────────────────────────────
    # El nombre del producto incluye el tamaño: "LECHE ASTURIANA 1 L", "YOGUR 500 G"
    # Es más fiable que combinar netWeight con la unidad del pum (que puede ser €/Litro
    # para un producto en ml, expresando solo el precio unitario, no el tamaño).
    formato = _extraer_formato_de_nombre(nombre.upper())

    # ── Marca ─────────────────────────────────────────────────────────────────
    marca = (item.get("brand") or "").strip().title()

    # ── Categoría ─────────────────────────────────────────────────────────────
    # category es lista: ["Bebidas", "Leche", "Leche semidesnatada"]
    # Tomar el elemento más específico (último)
    categorias = item.get("category") or []
    if isinstance(categorias, list) and categorias:
        categoria = categorias[-1]
    elif isinstance(categorias, str):
        categoria = categorias
    else:
        categoria = (item.get("family") or item.get("section") or "")

    # ── URLs ──────────────────────────────────────────────────────────────────
    url_rel = (item.get("url") or "").strip()
    url = BASE_WEB + url_rel if url_rel.startswith("/") else url_rel or f"{BASE_WEB}/p/{pid}"

    imagenes = item.get("images") or []
    if imagenes:
        img_rel = imagenes[0] if isinstance(imagenes[0], str) else ""
        # Las imágenes son rutas relativas: "/images/catalog/large/704048.jpg"
        url_imagen = BASE_WEB + img_rel if img_rel.startswith("/") else img_rel
    else:
        url_imagen = ""

    return {
        "Id":                pid,
        "Nombre":            nombre,
        "Precio":            precio,
        "Precio_por_unidad": precio_unitario,
        "Formato":           formato,
        "Categoria":         categoria,
        "Supermercado":      "Condis",
        "Url":               url,
        "Url_imagen":        url_imagen,
        "Marca":             marca,
    }
