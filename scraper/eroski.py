# -*- coding: utf-8 -*-

"""
Scraper de Eroski (supermercado.eroski.es).

Estrategia HÍBRIDA:
    1. Playwright abre navegador → obtiene cookies de sesión (~30s).
    2. Cierra Playwright.
    3. Con requests, hace búsquedas por términos y parsea el HTML.
    4. Los datos de producto están embebidos en atributos GA4:
       price, item_name, item_id, item_brand.

Estructura HTML de un producto:
    <div class="product-item-lineal item-type-1 ...">
      <div class="product-item big-item">
        ... data-ga4 con JSON: {price, item_name, item_id, item_brand} ...
        <a href=".../{item_id}-{slug}/">
        <img src="https://supermercado.eroski.es//images/{item_id}.jpg">
        <span class="price-offer-description">1,19 €/litro</span>
      </div>
    </div>

URL búsqueda: /es/search/results/?q=TERM&suggestionsFilter=false&offset=N
"""

import json
import os
import re
import time
import logging
import requests as req_lib
import pandas as pd

logger = logging.getLogger(__name__)

REQUEST_DELAY = 0.01
BASE_URL = "https://supermercado.eroski.es"
SEARCH_URL = "%s/es/search/results/" % BASE_URL
PRODUCTS_PER_PAGE = 20
MAX_PAGES_PER_SEARCH = 30  # 600 productos máx por búsqueda

# Términos de búsqueda para cubrir catálogo
TERMINOS_BUSQUEDA = [
    ("Leche", "leche"),
    ("Yogur", "yogur"),
    ("Queso", "queso"),
    ("Huevos", "huevos"),
    ("Mantequilla", "mantequilla"),
    ("Nata y crema", "nata crema"),
    ("Frutas", "frutas"),
    ("Verduras", "verduras"),
    ("Carne", "carne"),
    ("Pollo", "pollo"),
    ("Cerdo", "cerdo"),
    ("Ternera", "ternera"),
    ("Pescado", "pescado"),
    ("Marisco", "marisco"),
    ("Jamón", "jamón"),
    ("Embutido", "embutido chorizo salchichón"),
    ("Pan", "pan"),
    ("Bollería", "bollería croissant"),
    ("Cereales", "cereales"),
    ("Galletas", "galletas"),
    ("Pasta", "pasta espagueti macarrón"),
    ("Arroz", "arroz"),
    ("Legumbres", "legumbres lentejas garbanzos"),
    ("Aceite", "aceite oliva girasol"),
    ("Vinagre", "vinagre"),
    ("Sal y especias", "sal pimienta especias"),
    ("Conservas", "conservas atún sardinas"),
    ("Tomate", "tomate frito triturado"),
    ("Salsas", "salsa mayonesa ketchup"),
    ("Café", "café cápsulas"),
    ("Té e infusiones", "té infusiones manzanilla"),
    ("Cacao y chocolate", "cacao chocolate"),
    ("Miel y mermelada", "miel mermelada"),
    ("Azúcar", "azúcar edulcorante"),
    ("Harina", "harina"),
    ("Snacks", "snacks patatas fritas"),
    ("Frutos secos", "frutos secos almendras nueces"),
    ("Congelados", "congelados"),
    ("Pizza", "pizza"),
    ("Helados", "helados"),
    ("Agua", "agua mineral"),
    ("Refrescos", "refresco cola"),
    ("Zumos", "zumo"),
    ("Cerveza", "cerveza"),
    ("Vino", "vino tinto blanco"),
    ("Bebidas espirituosas", "whisky ron ginebra vodka"),
    ("Detergente", "detergente lavadora"),
    ("Suavizante", "suavizante"),
    ("Lejía y limpiadores", "lejía limpiador"),
    ("Lavavajillas", "lavavajillas"),
    ("Papel higiénico", "papel higiénico"),
    ("Servilletas", "servilletas"),
    ("Gel de baño", "gel baño ducha"),
    ("Champú", "champú"),
    ("Desodorante", "desodorante"),
    ("Pasta de dientes", "pasta dientes dental"),
    ("Pañales", "pañales"),
    ("Comida mascotas", "comida perro gato mascota"),
]


def gestion_eroski():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Eroski...")

    # Paso 1: Sesión con Playwright
    cookies_str = _obtener_cookies_playwright()
    if not cookies_str:
        logger.error("No se pudieron obtener cookies de Eroski.")
        return pd.DataFrame()

    # Paso 2: Búsquedas por términos
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

    for cat_nombre, termino in TERMINOS_BUSQUEDA:
        logger.info("Buscando: '%s' (%s)", termino, cat_nombre)

        try:
            productos = _buscar_termino(termino, cat_nombre, headers)
            nuevos = 0
            for p in productos:
                if p["Id"] not in ids_vistos:
                    ids_vistos.add(p["Id"])
                    todos.append(p)
                    nuevos += 1
            logger.info("  → %d encontrados, %d nuevos (total: %d)",
                        len(productos), nuevos, len(ids_vistos))
        except Exception as e:
            logger.warning("  Error buscando '%s': %s", termino, e)

        time.sleep(REQUEST_DELAY)

    if not todos:
        logger.warning("Eroski: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos)

    duracion = time.time() - tiempo_inicio
    logger.info(
        "Eroski completado: %d productos en %dm %ds",
        len(df), int(duracion // 60), int(duracion % 60)
    )
    return df


# ─── COOKIES PLAYWRIGHT ───────────────────────────────────────────────────────

def _obtener_cookies_playwright():
    """Obtiene cookies de sesión con Playwright."""
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

            logger.info("Navegando a supermercado.eroski.es...")
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
                'button:has-text("Aceptar todas las cookies")',
                'button:has-text("Aceptar todo")',
            ]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # Configurar CP si hay popup
            cp = os.getenv("CODIGO_POSTAL", "28001")
            try:
                el = page.locator(
                    'input[placeholder*="postal"], '
                    'input[name*="postal"], '
                    'input[id*="postal"]'
                ).first
                if el.is_visible(timeout=2000):
                    el.fill(cp)
                    page.wait_for_timeout(1000)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            # Navegar a búsqueda para generar sesión completa
            page.goto(
                "%s/es/search/results/?q=leche&suggestionsFilter=false"
                % BASE_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(3000)

            # Extraer cookies
            cookies_list = ctx.cookies()
            cookie_str = "; ".join(
                "%s=%s" % (c["name"], c["value"]) for c in cookies_list
            )

            browser.close()
            return cookie_str if cookie_str else None

    except Exception as e:
        logger.error("Error Playwright Eroski: %s", e)
        return None


# ─── BÚSQUEDA Y EXTRACCIÓN ────────────────────────────────────────────────────

def _buscar_termino(termino, cat_nombre, headers):
    """Busca un término y pagina por todos los resultados."""
    productos = []
    offset = 0

    for _page in range(MAX_PAGES_PER_SEARCH):
        params = {
            "q": termino,
            "suggestionsFilter": "false",
        }
        if offset > 0:
            params["offset"] = str(offset)

        try:
            resp = req_lib.get(
                SEARCH_URL, params=params, headers=headers, timeout=20
            )
            if resp.status_code != 200:
                logger.warning("  Status %d en offset %d", resp.status_code, offset)
                break

            html = resp.text
            page_products = _extraer_productos_html(html, cat_nombre)

            if not page_products:
                break

            productos.extend(page_products)

            # Extraer total de resultados
            total = _extraer_total(html)
            offset += PRODUCTS_PER_PAGE

            if total and offset >= total:
                break
            if len(page_products) < PRODUCTS_PER_PAGE:
                break

            time.sleep(REQUEST_DELAY)

        except Exception as e:
            logger.warning("  Error en offset %d: %s", offset, e)
            break

    return productos


def _extraer_total(html):
    """Extrae el número total de resultados del HTML."""
    # Patrón: "Mostrando resultados para leche (521)"
    match = re.search(r'\((\d+)\)\s*</h2>', html)
    if match:
        return int(match.group(1))
    return None


def _extraer_productos_html(html, cat_nombre):
    """Extrae productos del HTML de resultados de búsqueda."""
    productos = []

    # Estrategia 1: Extraer datos GA4 embebidos en atributos
    # Patrón: "item_name":"...", "item_id":"...", "price":X.XX, "item_brand":"..."
    pattern_ga4 = (
        r'"price"\s*:\s*([\d.]+)\s*,'
        r'[^}]*?"item_name"\s*:\s*"([^"]+)"\s*,'
        r'[^}]*?"item_id"\s*:\s*"(\d+)"\s*,'
        r'[^}]*?"item_brand"\s*:\s*"([^"]*)"'
    )

    # El orden puede variar, intentemos patrón flexible
    # Buscar bloques que contengan item_id y price
    bloques = re.findall(
        r'\{[^{}]*?"item_id"\s*:\s*"(\d+)"[^{}]*?\}',
        html,
        re.DOTALL,
    )

    for bloque_match in bloques:
        # Encontrar el bloque completo que contiene este item_id
        item_id = bloque_match
        # Buscar el contexto completo alrededor de este item_id
        patron = (
            r'\{[^{}]*?"item_id"\s*:\s*"' + re.escape(item_id)
            + r'"[^{}]*?\}'
        )
        matches = re.finditer(patron, html, re.DOTALL)
        for m in matches:
            bloque = m.group(0)
            prod = _parsear_bloque_ga4(bloque, item_id, cat_nombre)
            if prod:
                productos.append(prod)
                break  # Solo el primer match por item_id

    # Deduplicar dentro de página (un producto puede aparecer varias veces)
    vistos = set()
    unicos = []
    for p in productos:
        if p["Id"] not in vistos:
            vistos.add(p["Id"])
            unicos.append(p)

    return unicos


def _parsear_bloque_ga4(bloque, item_id, cat_nombre):
    """Parsea un bloque GA4 JSON para extraer datos de producto."""
    # Decodificar HTML entities
    bloque = bloque.replace("&quot;", '"').replace("&amp;", "&")

    # Precio
    precio = None
    m = re.search(r'"price"\s*:\s*([\d.]+)', bloque)
    if m:
        try:
            precio = float(m.group(1))
        except (ValueError, TypeError):
            pass
    if precio is None or precio <= 0:
        return None

    # Nombre
    nombre = ""
    m = re.search(r'"item_name"\s*:\s*"([^"]+)"', bloque)
    if m:
        nombre = m.group(1)
    if not nombre:
        return None

    # Marca
    marca = ""
    m = re.search(r'"item_brand"\s*:\s*"([^"]*)"', bloque)
    if m:
        marca = m.group(1)

    # Categoría GA4
    cat_ga4 = ""
    m = re.search(r'"item_category"\s*:\s*"([^"]*)"', bloque)
    if m:
        cat_ga4 = m.group(1)
    if cat_ga4:
        cat_nombre = cat_ga4

    # Imagen y URL
    imagen = "%s//images/%s.jpg" % (BASE_URL, item_id)
    url_p = "%s/es/productdetail/%s/" % (BASE_URL, item_id)

    # Formato: intentar extraer del nombre
    formato = _extraer_formato_nombre(nombre)

    # Precio por unidad: calcular si hay formato
    precio_u = precio

    return {
        "Id": str(item_id),
        "Nombre": nombre,
        "Precio": precio,
        "Precio_por_unidad": precio_u,
        "Formato": formato,
        "Categoria": cat_nombre,
        "Supermercado": "Eroski",
        "Url": url_p,
        "Url_imagen": imagen,
        "Marca": marca,
    }


def _extraer_formato_nombre(nombre):
    """Intenta extraer el formato/tamaño del nombre del producto."""
    # Patrones comunes: "1 litro", "500 g", "6x200 ml", "pack 6"
    patrones = [
        r'(\d+\s*x\s*\d+\s*(?:ml|l|g|kg|cl|ud)\.?)',
        r'(\d+(?:[.,]\d+)?\s*(?:litros?|l|ml|cl)\.?)',
        r'(\d+(?:[.,]\d+)?\s*(?:kg|g|gr)\.?)',
        r'(pack\s*\d+)',
        r'(\d+\s*(?:unidades|uds?|ud)\.?)',
    ]
    for patron in patrones:
        m = re.search(patron, nombre, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


# ─── ALTERNATIVA: EXTRAER PRECIO/UNIDAD DEL HTML ──────────────────────────────

def _extraer_precio_unidad_html(html, item_id):
    """Intenta extraer precio por unidad del HTML para un producto."""
    # Buscar "X,XX €/litro" o "X,XX €/kg" cerca del producto
    patron = (
        r'%s.*?(\d+,\d{2})\s*€\s*/\s*(litro|kg|unidad|l|kilo)'
        % re.escape(item_id)
    )
    m = re.search(patron, html[:html.find(item_id) + 2000] if item_id in html else html,
                  re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except (ValueError, TypeError):
            pass
    return None
