# -*- coding: utf-8 -*-

"""
Scraper de Alcampo (compraonline.alcampo.es).

Estrategia HÍBRIDA:
    1. Playwright navega, captura cookies + descubre endpoints API.
    2. Si descubre API → usa requests para scraping rápido.
    3. Si no → extrae del DOM con Playwright optimizado (menos esperas).
"""

import os
import re
import json
import time
import hashlib
import logging
import requests as req_lib
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://www.compraonline.alcampo.es"
REQUEST_DELAY = 0.5


def gestion_alcampo():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Alcampo...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado.")
        return pd.DataFrame()

    todos_los_productos = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                locale='es-ES',
                viewport={'width': 1920, 'height': 1080},
            )
            page = ctx.new_page()

            # Capturar URLs de API y sus respuestas
            api_descubierta = {}
            sesion_cookies = {}

            def capturar_request(request):
                url = request.url
                c = request.headers.get('cookie', '')
                if c and len(c) > len(sesion_cookies.get('best', '')):
                    sesion_cookies['best'] = c
                    sesion_cookies['headers'] = dict(request.headers)

            def capturar_response(response):
                url = response.url
                ct = response.headers.get('content-type', '')
                if response.status == 200 and 'json' in ct:
                    # Buscar endpoints con productos
                    if any(k in url.lower() for k in ['product', 'search', 'catalog', 'plp', 'listing']):
                        try:
                            data = response.json()
                            if _tiene_productos(data):
                                api_descubierta['products_url'] = url
                                api_descubierta['products_data'] = data
                        except Exception:
                            pass
                    # Buscar endpoints de categorías
                    if any(k in url.lower() for k in ['categor', 'menu', 'navigation', 'taxonomy']):
                        try:
                            data = response.json()
                            api_descubierta['categories_url'] = url
                            api_descubierta['categories_data'] = data
                        except Exception:
                            pass

            page.on('request', capturar_request)
            page.on('response', capturar_response)

            # ── Navegar ──────────────────────────────────
            logger.info("Navegando a compraonline.alcampo.es...")
            page.goto(f"{BASE_URL}/", wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)

            # Aceptar cookies
            for sel in ['#onetrust-accept-btn-handler', 'button:has-text("Aceptar todas")',
                        'button:has-text("Aceptar")', 'button:has-text("Permitir")']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.click()
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    continue

            # Navegar a /categories para descubrir API
            logger.info("Navegando a /categories...")
            page.goto(f"{BASE_URL}/categories", wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(4000)

            # Obtener categorías del DOM
            categorias = _extraer_categorias_dom(page)
            logger.info("%d categorías encontradas.", {len(categorias)})

            if not categorias:
                logger.error("No se encontraron categorías de Alcampo.")
                browser.close()
                return pd.DataFrame()

            # ── Si tenemos API, usar requests (rápido) ───
            cookies = sesion_cookies.get('best', '')
            headers_cap = sesion_cookies.get('headers', {})

            if api_descubierta.get('products_url') and cookies:
                logger.info("API descubierta, cambiando a modo requests...")
                browser.close()
                h = {
                    'User-Agent': headers_cap.get('user-agent', ''),
                    'Accept': 'application/json',
                    'Accept-Language': 'es-ES',
                    'Cookie': cookies,
                    'Referer': f'{BASE_URL}/',
                }
                todos_los_productos = _scrape_con_requests(categorias, h, api_descubierta)
            else:
                # ── Sin API: DOM rápido con Playwright ────
                logger.info("No se descubrió API, usando extracción DOM...")
                for idx, cat in enumerate(categorias):
                    cat_nombre = cat.get('name', 'Desconocida')
                    cat_url = cat.get('url', '')
                    if not cat_url:
                        continue
                    if cat_url.startswith('/'):
                        cat_url = f"{BASE_URL}{cat_url}"

                    logger.info("%d/%d - %s", idx+1, len(categorias), cat_nombre)

                    try:
                        prods = _scrape_dom_rapido(page, cat_url, cat_nombre)
                        todos_los_productos.extend(prods)
                        logger.info("  → %d productos", len(prods))
                    except Exception as e:
                        logger.warning("  Error: %s", e)

                    page.wait_for_timeout(1000)

                browser.close()

    except Exception as e:
        logger.error("Error general Alcampo: %s", e)
        return pd.DataFrame()

    if not todos_los_productos:
        logger.warning("Alcampo: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos_los_productos)
    df = df.drop_duplicates(subset=['Id'], keep='first')

    duracion = time.time() - tiempo_inicio
    logger.info("Alcampo completado: %d productos en %dm %ds", len(df), int(duracion // 60), int(duracion % 60))
    return df


# ─── CATEGORÍAS ───────────────────────────────────────────────────────────────

def _extraer_categorias_dom(page):
    """Extrae categorías del DOM de /categories."""
    try:
        links = page.evaluate('''() => {
            const results = [];
            const seen = new Set();
            const allLinks = document.querySelectorAll('a[href]');

            const excluir = ['inicio','home','carrito','cuenta','ayuda','contacto',
                'pedido','login','registro','reserva','entrega','recogida',
                'preguntas','ver artículos','ver todos','escríbenos','lista',
                'favoritos','newsletter','política','legal','privacidad',
                'tienda','promocion','oferta'];

            for (const a of allLinks) {
                const href = a.getAttribute('href');
                const text = a.textContent.trim();

                if (!href || !text || text.length < 3 || text.length > 80) continue;
                if (seen.has(href)) continue;

                const lower = text.toLowerCase();
                if (excluir.some(e => lower.includes(e))) continue;

                // Solo links de categorías de productos
                if (href.includes('/categor') || href.includes('/c/') ||
                    href.includes('/alimentacion') || href.includes('/bebidas') ||
                    href.includes('/frescos') || href.includes('/congelados') ||
                    href.includes('/limpieza') || href.includes('/higiene') ||
                    href.includes('/mascotas') || href.includes('/lacteos') ||
                    href.includes('/carniceria') || href.includes('/pescaderia') ||
                    href.includes('/fruteria') || href.includes('/panaderia') ||
                    href.includes('/drogueria') || href.includes('/bazar')) {
                    seen.add(href);
                    results.push({name: text, url: href});
                }
            }
            return results;
        }''')
        return links or []
    except Exception as e:
        logger.warning("Error categorías DOM: %s", e)
        return []


# ─── SCRAPING CON REQUESTS (SI API DESCUBIERTA) ──────────────────────────────

def _scrape_con_requests(categorias, headers, api_info):
    """Scraping rápido usando requests con la API descubierta."""
    productos = []
    base_url = api_info.get('products_url', '')

    for idx, cat in enumerate(categorias):
        cat_nombre = cat.get('name', '')
        cat_url = cat.get('url', '')
        logger.info("%d/%d - %s", idx+1, len(categorias), cat_nombre)

        # Intentar construir URL de API para esta categoría
        try:
            resp = req_lib.get(
                cat_url if cat_url.startswith('http') else f"{BASE_URL}{cat_url}",
                headers=headers, timeout=15
            )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    prods = _extraer_productos_json(data, cat_nombre)
                    productos.extend(prods)
                    logger.info("  → %d productos", len(prods))
                except ValueError:
                    pass
        except Exception as e:
            logger.warning("  Error: %s", e)

        time.sleep(REQUEST_DELAY)

    return productos


# ─── SCRAPING DOM RÁPIDO ─────────────────────────────────────────────────────

def _scrape_dom_rapido(page, url, cat_nombre):
    """Extrae productos del DOM de forma rápida (menos esperas)."""
    productos = []

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        page.wait_for_timeout(2000)

        # Un solo scroll
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

        items = page.evaluate('''() => {
            const results = [];

            // Product cards con selectores amplios
            const selectors = [
                '[data-testid*="product"]',
                '[class*="product-card"]',
                '[class*="productCard"]',
                'article[class*="product"]',
                '[class*="product-tile"]',
                '[class*="product-item"]',
                'li[class*="product"]',
            ];

            let els = [];
            for (const sel of selectors) {
                els = document.querySelectorAll(sel);
                if (els.length > 0) break;
            }

            for (const el of els) {
                const nameEl = el.querySelector('h2, h3, [class*="title"], [class*="name"], [data-testid*="title"]');
                const name = nameEl ? nameEl.textContent.trim() : '';

                const priceEl = el.querySelector('[class*="price"], [data-testid*="price"]');
                const price = priceEl ? priceEl.textContent.trim() : '';

                const linkEl = el.querySelector('a[href]');
                const url = linkEl ? linkEl.getAttribute('href') : '';

                const imgEl = el.querySelector('img');
                const img = imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '';

                if (name && price) {
                    results.push({name, price, url: url || '', image: img || ''});
                }
            }
            return results;
        }''')

        for item in items:
            precio = _parsear_precio(item['price'])
            if precio is None:
                continue

            url_p = item['url']
            if url_p and url_p.startswith('/'):
                url_p = f"{BASE_URL}{url_p}"

            pid = hashlib.md5(f"{item['name']}_{precio}".encode()).hexdigest()[:12]
            productos.append({
                'Id': pid, 'Nombre': item['name'], 'Precio': precio,
                'Precio_por_unidad': precio, 'Formato': '',
                'Categoria': cat_nombre, 'Supermercado': 'Alcampo',
                'Url': url_p, 'Url_imagen': item['image'],
            })

    except Exception as e:
        logger.warning("Error DOM: %s", e)

    return productos


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def _tiene_productos(data):
    """Comprueba si un JSON parece contener productos."""
    if isinstance(data, dict):
        for k in ['results', 'products', 'items', 'content', 'hits']:
            v = data.get(k)
            if isinstance(v, list) and len(v) > 2:
                return True
    return False


def _extraer_productos_json(data, cat_nombre):
    """Extrae productos de JSON."""
    productos = []
    items = None

    if isinstance(data, dict):
        for k in ['results', 'products', 'items', 'content', 'hits', 'data', 'records']:
            v = data.get(k)
            if isinstance(v, list) and v:
                items = v
                break
    elif isinstance(data, list):
        items = data

    if not items:
        return []

    for item in items:
        if not isinstance(item, dict):
            continue
        nombre = item.get('display_name') or item.get('name') or item.get('title') or ''
        if not nombre:
            continue

        pid = item.get('id') or item.get('product_id') or item.get('sku') or hashlib.md5(nombre.encode()).hexdigest()[:12]
        precio = None
        for k in ['price', 'unit_price', 'unitPrice', 'currentPrice', 'salePrice']:
            v = item.get(k)
            if v is not None:
                try:
                    precio = float(str(v).replace(',', '.').replace('€', '').strip())
                    break
                except (ValueError, TypeError):
                    continue

        if precio is None:
            continue

        url_p = item.get('url') or item.get('link') or ''
        if url_p and url_p.startswith('/'):
            url_p = f"{BASE_URL}{url_p}"

        img = item.get('image') or item.get('thumbnail') or ''
        if isinstance(img, dict):
            img = img.get('url') or ''

        productos.append({
            'Id': str(pid), 'Nombre': nombre, 'Precio': precio,
            'Precio_por_unidad': precio, 'Formato': '',
            'Categoria': cat_nombre, 'Supermercado': 'Alcampo',
            'Url': url_p, 'Url_imagen': str(img),
        })

    return productos


def _parsear_precio(texto):
    try:
        m = re.search(r'(\d+[.,]\d{2})', texto)
        if m:
            return float(m.group(1).replace(',', '.'))
    except Exception:
        pass
    return None
