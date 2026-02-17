# -*- coding: utf-8 -*-

"""
Scraper de Carrefour.

Estrategia HÍBRIDA (rápida):
    1. Playwright abre navegador → obtiene cookies de sesión
       (session_id, cf_clearance, salepoint).
    2. Cierra Playwright (~30s).
    3. Usa la API Empathy.co con requests:
       /search-api/query/v1/search?query=...&catalog=food&store=XXXXX
    4. Itera por términos de búsqueda, paginando resultados.

Estructura JSON de la API:
    {
      "content": {
        "docs": [
          {
            "active_price": 0.88,
            "display_name": "Leche semidesnatada Carrefour brik 1 l.",
            "product_id": "521007071",
            "brand": "CARREFOUR",
            "ean13": "8431876011937",
            "image_path": "https://static.carrefour.es/hd_350x_/...",
            "price_per_unit_text": "0,88 €/l",
            "measure_unit": "l",
            "url": "/supermercado/leche-semidesnatada-.../R-521007071/p",
            "average_weight": 1000,
            "list_price": 0.88,
          }
        ]
      },
      "numFound": 734
    }
"""

import os
import re
import time
import logging
import requests as req_lib
import pandas as pd

logger = logging.getLogger(__name__)

REQUEST_DELAY = 0.01

# API de búsqueda Empathy.co
SEARCH_API = "https://www.carrefour.es/search-api/query/v1/search"

# Términos de búsqueda que cubren el catálogo de supermercado
CATEGORIAS_BUSQUEDA = [
    # Frescos
    ("Frutas y verduras", "frutas verduras"),
    ("Frutas", "manzana plátano naranja"),
    ("Verduras", "tomate lechuga pepino zanahoria"),
    ("Ensaladas", "ensalada preparada"),
    ("Carnicería", "pollo ternera cerdo"),
    ("Carne picada", "carne picada hamburguesa"),
    ("Aves", "pollo pavo"),
    ("Cerdo", "lomo chuleta cerdo"),
    ("Ternera", "ternera filete"),
    ("Cordero", "cordero"),
    ("Pescadería", "merluza salmón atún"),
    ("Marisco", "gamba langostino mejillón"),
    ("Charcutería", "jamón serrano ibérico"),
    ("Embutidos", "chorizo salchichón fuet"),
    ("Quesos", "queso manchego brie"),
    # Lácteos
    ("Leche", "leche"),
    ("Yogures", "yogur"),
    ("Mantequilla y nata", "mantequilla nata"),
    ("Postres lácteos", "flan natillas"),
    ("Huevos", "huevos"),
    # Panadería
    ("Pan", "pan barra molde"),
    ("Bollería", "croissant magdalena"),
    # Despensa
    ("Cereales", "cereales desayuno"),
    ("Galletas", "galletas"),
    ("Pasta", "pasta espagueti macarrones"),
    ("Arroz", "arroz"),
    ("Legumbres", "legumbres lentejas garbanzos"),
    ("Aceite", "aceite oliva girasol"),
    ("Vinagre", "vinagre"),
    ("Conservas", "conservas atún sardinas"),
    ("Conservas vegetales", "tomate frito pimiento"),
    ("Salsas", "salsa mayonesa ketchup"),
    ("Condimentos", "especias pimienta orégano"),
    ("Sopas y caldos", "caldo sopa"),
    ("Harinas", "harina levadura"),
    # Desayuno y merienda
    ("Café", "café cápsulas"),
    ("Infusiones", "infusión té manzanilla"),
    ("Cacao", "cacao colacao"),
    ("Chocolate", "chocolate tableta"),
    ("Mermelada", "mermelada miel"),
    # Dulces y snacks
    ("Dulces", "dulces caramelos"),
    ("Snacks", "patatas fritas snacks"),
    ("Frutos secos", "frutos secos almendras nueces"),
    # Congelados
    ("Congelados", "congelados"),
    ("Helados", "helado"),
    ("Pizza congelada", "pizza congelada"),
    ("Verduras congeladas", "verduras congeladas"),
    ("Pescado congelado", "pescado congelado"),
    # Bebidas
    ("Agua", "agua mineral"),
    ("Refrescos", "coca cola fanta"),
    ("Zumos", "zumo"),
    ("Cerveza", "cerveza"),
    ("Vino tinto", "vino tinto"),
    ("Vino blanco", "vino blanco"),
    ("Bebidas espirituosas", "whisky ron ginebra vodka"),
    # Hogar y limpieza
    ("Detergente", "detergente lavadora"),
    ("Suavizante", "suavizante"),
    ("Lavavajillas", "lavavajillas"),
    ("Lejía y limpiadores", "lejía limpiador"),
    ("Papel higiénico", "papel higiénico"),
    ("Papel cocina", "papel cocina servilletas"),
    ("Bolsas basura", "bolsas basura"),
    # Higiene y belleza
    ("Gel y jabón", "gel ducha jabón"),
    ("Champú", "champú"),
    ("Desodorante", "desodorante"),
    ("Pasta de dientes", "pasta dientes cepillo"),
    ("Cuidado facial", "crema facial"),
    ("Compresas y tampones", "compresas tampones"),
    ("Pañuelos", "pañuelos"),
    # Bebé
    ("Pañales", "pañales"),
    ("Alimentación bebé", "potito papilla bebé"),
    # Mascotas
    ("Comida perro", "comida perro pienso"),
    ("Comida gato", "comida gato"),
]

MAX_ROWS = 48
MAX_PAGES = 20  # 48 * 20 = 960 productos máx por búsqueda


def gestion_carrefour():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Carrefour...")

    # Paso 1: Sesión con Playwright
    sesion = _obtener_sesion_playwright()
    if not sesion:
        logger.error("No se pudo obtener sesión de Carrefour.")
        return pd.DataFrame()

    cookies_str = sesion["cookies"]
    store_id = sesion["store_id"]
    logger.info("Sesión obtenida. Tienda: %s", store_id)

    # Paso 2: Búsqueda masiva con requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cookie": cookies_str,
        "Referer": "https://www.carrefour.es/supermercado/",
        "x-origin": "https://www.carrefour.es",
    }

    todos = []
    ids_vistos = set()

    for cat_nombre, query in CATEGORIAS_BUSQUEDA:
        logger.info("Buscando: %s", cat_nombre)

        try:
            productos = _buscar_productos(query, store_id, headers, cat_nombre)
            nuevos = 0
            for p in productos:
                if p["Id"] not in ids_vistos:
                    ids_vistos.add(p["Id"])
                    todos.append(p)
                    nuevos += 1
            logger.info("  → %d encontrados, %d nuevos", len(productos), nuevos)
        except Exception as e:
            logger.warning("  Error buscando '%s': %s", cat_nombre, e)

        time.sleep(REQUEST_DELAY)

    if not todos:
        logger.warning("Carrefour: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos)

    duracion = time.time() - tiempo_inicio
    logger.info(
        "Carrefour completado: %d productos en %dm %ds",
        len(df), int(duracion // 60), int(duracion % 60)
    )
    return df


# ─── SESIÓN PLAYWRIGHT ────────────────────────────────────────────────────────

def _obtener_sesion_playwright():
    """Obtiene cookies de sesión válidas con Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado.")
        return None

    cp = os.getenv("CODIGO_POSTAL", "08001")

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

            logger.info("Navegando a carrefour.es/supermercado/...")
            page.goto(
                "https://www.carrefour.es/supermercado/",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(4000)

            # Aceptar cookies banner
            for sel in [
                "#onetrust-accept-btn-handler",
                'button:has-text("Aceptar todas")',
                'button:has-text("Aceptar")',
            ]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # CP
            for sel in [
                'input[placeholder*="postal"]',
                'input[name*="postal"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.fill(cp)
                        page.wait_for_timeout(1000)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(3000)
                        logger.info("CP %s configurado.", cp)
                        break
                except Exception:
                    continue

            # Navegar a categoría para generar cookie salepoint
            try:
                page.goto(
                    "https://www.carrefour.es/supermercado/alimentacion/cat20002/c",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                page.wait_for_timeout(3000)
            except Exception:
                pass

            # Extraer cookies
            cookies_list = ctx.cookies()
            cookie_str = "; ".join(
                "%s=%s" % (c["name"], c["value"]) for c in cookies_list
            )

            # Extraer store_id del cookie salepoint
            store_id = ""
            for c in cookies_list:
                if c["name"] == "salepoint":
                    parts = c["value"].split("|")
                    if parts:
                        store_id = parts[0]
                    break

            if not store_id:
                store_id = "005290"  # Default

            browser.close()

            if not cookie_str:
                return None

            return {"cookies": cookie_str, "store_id": store_id}

    except Exception as e:
        logger.error("Error Playwright: %s", e)
        return None


# ─── BÚSQUEDA DE PRODUCTOS ────────────────────────────────────────────────────

def _buscar_productos(query, store_id, headers, cat_nombre):
    """Busca productos con la API Empathy.co, paginando."""
    productos = []
    start = 0

    for _ in range(MAX_PAGES):
        params = {
            "internal": "true",
            "query": query,
            "instance": "x-carrefour",
            "catalog": "food",
            "store": store_id,
            "lang": "es",
            "start": str(start),
            "rows": str(MAX_ROWS),
            "scope": "mobile",
        }

        try:
            resp = req_lib.get(
                SEARCH_API, params=params, headers=headers, timeout=15
            )

            if resp.status_code != 200:
                logger.warning(
                    "  API status %d para '%s'", resp.status_code, query
                )
                break

            data = resp.json()

            # Productos en content.docs
            docs = []
            content = data.get("content")
            if isinstance(content, dict):
                docs = content.get("docs", [])
            if not docs:
                break

            for doc in docs:
                prod = _parsear_doc(doc, cat_nombre)
                if prod:
                    productos.append(prod)

            # Paginación: numFound en raíz
            total = data.get("numFound", 0)
            try:
                total = int(total)
            except (ValueError, TypeError):
                total = 0

            start += MAX_ROWS
            if start >= total or len(docs) < MAX_ROWS:
                break

        except Exception as e:
            logger.warning("  Error request: %s", e)
            break

        time.sleep(REQUEST_DELAY)

    return productos


def _parsear_doc(doc, cat_nombre):
    """Parsea un documento de la API Empathy.co."""
    if not isinstance(doc, dict):
        return None

    # Nombre
    nombre = doc.get("display_name", "")
    if not nombre:
        return None

    # ID (product_id es el principal)
    pid = doc.get("product_id") or doc.get("ean13") or ""
    if not pid:
        return None

    # Precio actual
    precio = doc.get("active_price")
    if precio is None:
        precio = doc.get("app_price")
    if precio is None:
        return None
    try:
        precio = float(precio)
    except (ValueError, TypeError):
        return None

    # Precio por unidad (de price_per_unit_text: "0,88 €/l")
    precio_u = _parsear_precio_por_unidad(doc.get("price_per_unit_text", ""))
    if precio_u is None:
        precio_u = precio

    # Formato: construir desde measure_unit + average_weight
    formato = _construir_formato(doc)

    # URL
    url_p = doc.get("url", "")
    if url_p and not url_p.startswith("http"):
        url_p = "https://www.carrefour.es%s" % url_p

    # Imagen
    imagen = doc.get("image_path", "")

    # Marca
    marca = doc.get("brand", "")

    return {
        "Id": str(pid),
        "Nombre": nombre,
        "Precio": precio,
        "Precio_por_unidad": precio_u,
        "Formato": formato,
        "Categoria": cat_nombre,
        "Supermercado": "Carrefour",
        "Url": url_p,
        "Url_imagen": imagen,
        "Marca": marca,
    }


def _parsear_precio_por_unidad(texto):
    """Parsea '0,88 €/l' → 0.88"""
    if not texto:
        return None
    try:
        m = re.search(r"(\d+[.,]\d+)", texto)
        if m:
            return float(m.group(1).replace(",", "."))
    except Exception:
        pass
    return None


def _construir_formato(doc):
    """Construye string de formato: '1 l', '500 g', etc."""
    peso = doc.get("average_weight")
    unidad = doc.get("measure_unit", "")
    factor = doc.get("unit_conversion_factor")

    if factor and unidad:
        try:
            factor = float(factor)
            if unidad == "l":
                if factor >= 1:
                    return "%g l" % factor
                return "%g ml" % (factor * 1000)
            elif unidad in ("kg", "g"):
                if factor >= 1:
                    return "%g kg" % factor
                return "%g g" % (factor * 1000)
            else:
                return "%g %s" % (factor, unidad)
        except (ValueError, TypeError):
            pass

    if peso and unidad:
        try:
            peso = float(peso)
            if unidad == "l":
                if peso >= 1000:
                    return "%g l" % (peso / 1000)
                return "%g ml" % peso
            elif unidad in ("kg", "g"):
                if peso >= 1000:
                    return "%g kg" % (peso / 1000)
                return "%g g" % peso
            else:
                return "%g %s" % (peso, unidad)
        except (ValueError, TypeError):
            pass

    return ""
