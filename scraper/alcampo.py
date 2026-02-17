# -*- coding: utf-8 -*-

"""
Scraper de Alcampo (compraonline.alcampo.es).

Estrategia HÍBRIDA (SSR):
    1. Playwright abre navegador → obtiene cookies + árbol de categorías
       desde window.__PRELOADED_STATE__.
    2. Cierra Playwright (~30s).
    3. Con requests, descarga el HTML de cada categoría hoja.
    4. Extrae __PRELOADED_STATE__ del HTML con regex.
    5. Parsea productos de data.products.productEntities.

Estructura de producto (plataforma Ocado):
    {
      "retailerProductId": "50864",
      "name": "RAM Leche entera de vaca 1 l.",
      "brand": "RAM",
      "price": {
        "current": {"amount": "1.10", "currency": "EUR"},
        "unit": {"current": {"amount": "1.10"}, "label": "fop.price.per.litre"}
      },
      "image": {"src": "https://...300x300.jpg"},
      "size": {"value": "1000ml"},
      "categoryPath": ["...", "Leche"],
      "available": true
    }
"""

import json
import os
import re
import time
import logging
import requests as req_lib
import pandas as pd

logger = logging.getLogger(__name__)

REQUEST_DELAY = 0.5
BASE_URL = "https://www.compraonline.alcampo.es"

# Categorías hoja de alimentación/hogar (retailerId, nombre)
# Extraídas del árbol de categorías de __PRELOADED_STATE__
CATEGORIAS_HOJA = [
    # Frescos
    ("OC1701", "Frutas"),
    ("OC1702", "Verduras y hortalizas"),
    ("OC13", "Carne"),
    ("OC14", "Pescados, mariscos y moluscos"),
    ("OC184", "Ahumados, surimis, anchoas"),
    ("OC15", "Charcutería"),
    ("OC151001", "Jamones y paletas"),
    ("OCQuesos", "Quesos"),
    ("OC1281", "Panadería"),
    ("OC1282", "Pastelería"),
    # Leche, Huevos, Lácteos
    ("OC1603", "Leche"),
    ("OC1612", "Productos proteicos"),
    ("OC160316", "Leche condensada, polvo y evaporada"),
    ("OC160403", "Zumos con leche"),
]


def gestion_alcampo():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Alcampo...")

    # Paso 1: Sesión con Playwright + categorías
    sesion = _obtener_sesion_playwright()
    if not sesion:
        logger.error("No se pudo obtener sesión de Alcampo.")
        return pd.DataFrame()

    cookies_str = sesion["cookies"]
    categorias = sesion.get("categorias", [])

    if not categorias:
        categorias = CATEGORIAS_HOJA
        logger.info("Usando %d categorías hardcoded.", len(categorias))
    else:
        logger.info("Descubiertas %d categorías hoja.", len(categorias))

    # Paso 2: Extraer productos de cada categoría
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cookie": cookies_str,
    }

    todos = []
    ids_vistos = set()

    for retailer_id, cat_nombre in categorias:
        logger.info("Categoría: %s (%s)", cat_nombre, retailer_id)

        try:
            productos = _extraer_categoria(retailer_id, cat_nombre, headers)
            nuevos = 0
            for p in productos:
                if p["Id"] not in ids_vistos:
                    ids_vistos.add(p["Id"])
                    todos.append(p)
                    nuevos += 1
            logger.info("  → %d encontrados, %d nuevos", len(productos), nuevos)
        except Exception as e:
            logger.warning("  Error en categoría '%s': %s", cat_nombre, e)

        time.sleep(REQUEST_DELAY)

    if not todos:
        logger.warning("Alcampo: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos)

    duracion = time.time() - tiempo_inicio
    logger.info(
        "Alcampo completado: %d productos en %dm %ds",
        len(df), int(duracion // 60), int(duracion % 60)
    )
    return df


# ─── SESIÓN PLAYWRIGHT ────────────────────────────────────────────────────────

def _obtener_sesion_playwright():
    """Obtiene cookies y categorías con Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado.")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
            )
            page = ctx.new_page()

            logger.info("Navegando a compraonline.alcampo.es...")
            page.goto(
                "%s/" % BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(5000)

            # Aceptar cookies banner
            for sel in [
                "#onetrust-accept-btn-handler",
                'button:has-text("Aceptar")',
                'button:has-text("Aceptar todas")',
            ]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # Configurar CP si hay selector
            cp = os.getenv("CODIGO_POSTAL", "28001")
            try:
                el = page.locator('input[placeholder*="postal"]').first
                if el.is_visible(timeout=2000):
                    el.fill(cp)
                    page.wait_for_timeout(1000)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            # Navegar a categoría para cargar estado completo
            page.goto(
                "%s/categories/~/%s" % (BASE_URL, "OC1603"),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(4000)

            # Extraer categorías del estado
            categorias = []
            try:
                cats_json = page.evaluate("""
                    () => {
                        let s = window.__PRELOADED_STATE__ ||
                                window.__INITIAL_STATE__ ||
                                window.__data;
                        if (!s || !s.data || !s.data.categories) return null;
                        return s.data.categories.categories;
                    }
                """)
                if cats_json:
                    categorias = _extraer_hojas(cats_json)
            except Exception as e:
                logger.warning("No se pudieron extraer categorías: %s", e)

            # Extraer cookies
            cookies_list = ctx.cookies()
            cookie_str = "; ".join(
                "%s=%s" % (c["name"], c["value"]) for c in cookies_list
            )

            browser.close()

            if not cookie_str:
                return None

            return {"cookies": cookie_str, "categorias": categorias}

    except Exception as e:
        logger.error("Error Playwright Alcampo: %s", e)
        return None


def _extraer_hojas(cats_dict):
    """Extrae categorías hoja (sin children) del diccionario."""
    hojas = []
    excluir = {
        "Folletos y Promociones", "Carnaval",
        "Renueva la decoración de tu hogar",
        "Súper Ofertas Frescos", "Promociones Club Alcampo",
        "Folleto Alimentación Canarias",
        "Folleto Hogar y Tecnología",
        "Folleto de Alimentación (excepto Canarias)",
    }

    for _cat_id, cat_data in cats_dict.items():
        nombre = cat_data.get("name", "")
        retailer_id = cat_data.get("retailerId", "")
        children = cat_data.get("children", [])

        if nombre in excluir:
            continue
        if not children and retailer_id:
            hojas.append((retailer_id, nombre))

    logger.info("Categorías hoja encontradas: %d", len(hojas))
    return hojas


# ─── EXTRACCIÓN DE PRODUCTOS ──────────────────────────────────────────────────

def _extraer_categoria(retailer_id, cat_nombre, headers):
    """Descarga HTML de categoría y extrae productos del estado SSR."""
    url = "%s/categories/~/%s" % (BASE_URL, retailer_id)

    try:
        resp = req_lib.get(url, headers=headers, timeout=20)

        if resp.status_code != 200:
            logger.warning("  Status %d para %s", resp.status_code, retailer_id)
            return []

        html = resp.text
        state = _extraer_state_html(html)
        if not state:
            logger.warning("  No se pudo extraer estado de %s", retailer_id)
            return []

        entities = (
            state.get("data", {})
            .get("products", {})
            .get("productEntities", {})
        )
        if not entities:
            return []

        productos = []
        for _prod_id, prod in entities.items():
            parsed = _parsear_producto(prod, cat_nombre)
            if parsed:
                productos.append(parsed)

        return productos

    except Exception as e:
        logger.warning("  Error HTTP: %s", e)
        return []


def _extraer_state_html(html):
    """Extrae el JSON de __PRELOADED_STATE__ del HTML."""
    patterns = [
        r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\})\s*;\s*</script>',
        r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\})\s*</script>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Intentar encontrar el cierre correcto del JSON
                try:
                    depth = 0
                    end = 0
                    for i, ch in enumerate(json_str):
                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    if end > 0:
                        return json.loads(json_str[:end])
                except Exception:
                    pass

    # Fallback: buscar en todo el HTML con patrón más flexible
    match = re.search(
        r'__PRELOADED_STATE__\s*=\s*(\{.*?"productEntities"\s*:\s*\{.*?\})',
        html, re.DOTALL
    )
    if match:
        # Esto no dará JSON válido, pero intentamos
        pass

    return None


def _parsear_producto(prod, cat_nombre):
    """Parsea un producto del estado SSR de Alcampo."""
    if not isinstance(prod, dict):
        return None

    nombre = prod.get("name", "")
    if not nombre:
        return None

    pid = prod.get("retailerProductId") or prod.get("productId", "")
    if not pid:
        return None

    # Disponibilidad
    if not prod.get("available", True):
        return None

    # Precio
    precio = None
    price_data = prod.get("price", {})
    current = price_data.get("current", {})
    amount_str = current.get("amount", "")
    if amount_str:
        try:
            precio = float(amount_str)
        except (ValueError, TypeError):
            pass
    if precio is None:
        return None

    # Precio por unidad
    precio_u = precio
    unit_data = price_data.get("unit", {})
    unit_current = unit_data.get("current", {})
    unit_amount = unit_current.get("amount", "")
    if unit_amount:
        try:
            precio_u = float(unit_amount)
        except (ValueError, TypeError):
            pass

    # Formato
    formato = ""
    size = prod.get("size", {})
    if isinstance(size, dict):
        formato = size.get("value", "")

    # Imagen
    imagen = ""
    img = prod.get("image", {})
    if isinstance(img, dict):
        imagen = img.get("src", "")

    # Marca
    marca = prod.get("brand", "")

    # Categoría real del producto
    cat_path = prod.get("categoryPath", [])
    if cat_path:
        cat_nombre = cat_path[-1]

    # URL
    url_p = "%s/products/%s" % (BASE_URL, pid)

    return {
        "Id": str(pid),
        "Nombre": nombre,
        "Precio": precio,
        "Precio_por_unidad": precio_u,
        "Formato": formato,
        "Categoria": cat_nombre,
        "Supermercado": "Alcampo",
        "Url": url_p,
        "Url_imagen": imagen,
        "Marca": marca,
    }
