# -*- coding: utf-8 -*-

"""
Scraper de Eroski (supermercado.eroski.es).

Estrategia HÍBRIDA:
    1. Playwright navega, captura cookies + descubre endpoints API.
    2. Si descubre API → usa requests para scraping rápido.
    3. Si no → extrae del DOM con Playwright optimizado.
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

BASE_URL = "https://supermercado.eroski.es"
REQUEST_DELAY = 0.01


def gestion_eroski():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Eroski...")

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

            # Capturar API
            api_descubierta = {}
            sesion_cookies = {}

            def capturar_request(request):
                c = request.headers.get('cookie', '')
                if c and len(c) > len(sesion_cookies.get('best', '')):
                    sesion_cookies['best'] = c
                    sesion_cookies['headers'] = dict(request.headers)

            def capturar_response(response):
                url = response.url
                ct = response.headers.get('content-type', '')
                if response.status == 200 and 'json' in ct:
                    if any(k in url.lower() for k in ['product', 'search', 'catalog', 'plp', 'listing']):
                        try:
                            data = response.json()
                            if _tiene_productos(data):
                                api_descubierta['products_url'] = url
                                api_descubierta['products_data'] = data
                        except Exception:
                            pass
                    if any(k in url.lower() for k in ['categor', 'menu', 'navigation', 'taxonomy']):
                        try:
                            data = response.json()
                            api_descubierta['categories_data'] = data
                        except Exception:
                            pass

            page.on('request', capturar_request)
            page.on('response', capturar_response)

            # ── Navegar ──────────────────────────────────
            logger.info("Navegando a supermercado.eroski.es...")
            page.goto(f"{BASE_URL}/", wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)

            # Aceptar cookies
            for sel in ['#onetrust-accept-btn-handler', '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                        'button:has-text("Aceptar todas")', 'button:has-text("Aceptar")']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.click()
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    continue

            # Scroll en home para cargar menú
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Obtener categorías del DOM
            categorias = _extraer_categorias_dom(page)

            # Si API descubrió categorías, usarlas
            if not categorias and api_descubierta.get('categories_data'):
                categorias = _parsear_categorias_api(api_descubierta['categories_data'])

            logger.info(f"{len(categorias)} categorías encontradas.")

            if not categorias:
                logger.error("No se encontraron categorías de Eroski.")
                browser.close()
                return pd.DataFrame()

            # ── Si tenemos API, usar requests ─────────────
            cookies = sesion_cookies.get('best', '')

            if api_descubierta.get('products_url') and cookies:
                logger.info("API descubierta, cambiando a modo requests...")
                headers_cap = sesion_cookies.get('headers', {})
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
                # ── DOM rápido ────────────────────────────
                logger.info("No se descubrió API, usando extracción DOM...")
                for idx, cat in enumerate(categorias):
                    cat_nombre = cat.get('name', 'Desconocida')
                    cat_url = cat.get('url', '')
                    if not cat_url:
                        continue
                    if cat_url.startswith('/'):
                        cat_url = f"{BASE_URL}{cat_url}"

                    logger.info(f"{idx+1}/{len(categorias)} - {cat_nombre}")

                    try:
                        prods = _scrape_dom_rapido(page, cat_url, cat_nombre)
                        todos_los_productos.extend(prods)
                        logger.info(f"  → {len(prods)} productos")
                    except Exception as e:
                        logger.warning(f"  Error: {e}")

                    page.wait_for_timeout(1000)

                browser.close()

    except Exception as e:
        logger.error(f"Error general Eroski: {e}")
        return pd.DataFrame()

    if not todos_los_productos:
        logger.warning("Eroski: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos_los_productos)
    df = df.drop_duplicates(subset=['Id'], keep='first')

    duracion = time.time() - tiempo_inicio
    logger.info(f"Eroski completado: {len(df)} productos en {int(duracion//60)}m {int(duracion%60)}s")
    return df


# ─── CATEGORÍAS ───────────────────────────────────────────────────────────────

def _extraer_categorias_dom(page):
    """Extrae categorías de producto del DOM."""
    try:
        links = page.evaluate('''() => {
            const results = [];
            const seen = new Set();
            const allLinks = document.querySelectorAll('a[href]');

            const excluir = ['inicio','home','carrito','cuenta','ayuda','contacto',
                'pedido','login','registro','reserva','entrega','recogida',
                'preguntas','ver artículos','ver todos','escríbenos','lista',
                'favoritos','newsletter','política','legal','privacidad',
                'tienda','online','mis datos','mis pedidos','ofertas','receta',
                'blog','prensa','empleo','empresa','tarjeta','club'];

            for (const a of allLinks) {
                const href = a.getAttribute('href');
                const text = a.textContent.trim();

                if (!href || !text || text.length < 3 || text.length > 80) continue;
                if (seen.has(href)) continue;

                const lower = text.toLowerCase();
                if (excluir.some(e => lower.includes(e))) continue;

                // Solo categorías de supermercado
                if (href.includes('/es/supermercado/') ||
                    href.includes('/es/alimentacion') ||
                    href.includes('/es/bebidas') ||
                    href.includes('/es/frescos') ||
                    href.includes('/es/congelados') ||
                    href.includes('/es/limpieza') ||
                    href.includes('/es/higiene') ||
                    href.includes('/es/mascotas') ||
                    href.includes('/es/lacteos') ||
                    href.includes('/es/charcuteria') ||
                    href.includes('/es/carniceria') ||
                    href.includes('/es/pescaderia') ||
                    href.includes('/es/fruteria') ||
                    href.includes('/es/panaderia') ||
                    href.includes('/es/drogueria') ||
                    href.includes('/es/conservas') ||
                    href.includes('/categor') ||
                    href.includes('/c/')) {
                    seen.add(href);
                    results.push({name: text, url: href});
                }
            }
            return results;
        }''')
        return links or []
    except Exception as e:
        logger.warning(f"Error categorías DOM: {e}")
        return []


def _parsear_categorias_api(data):
    """Parsea categorías desde JSON de API."""
    resultado = []
    _parsear_recursivo(data, resultado)
    return resultado


def _parsear_recursivo(data, resultado):
    if isinstance(data, dict):
        url = data.get('url') or data.get('link') or data.get('href', '')
        nombre = data.get('name') or data.get('label') or data.get('title', '')
        if url and nombre:
            resultado.append({'name': str(nombre), 'url': str(url)})
        for v in data.values():
            if isinstance(v, (list, dict)):
                _parsear_recursivo(v, resultado)
    elif isinstance(data, list):
        for item in data:
            _parsear_recursivo(item, resultado)


# ─── SCRAPING CON REQUESTS ───────────────────────────────────────────────────

def _scrape_con_requests(categorias, headers, api_info):
    productos = []
    for idx, cat in enumerate(categorias):
        cat_nombre = cat.get('name', '')
        cat_url = cat.get('url', '')
        logger.info(f"{idx+1}/{len(categorias)} - {cat_nombre}")

        try:
            full_url = cat_url if cat_url.startswith('http') else f"{BASE_URL}{cat_url}"
            resp = req_lib.get(full_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    prods = _extraer_productos_json(data, cat_nombre)
                    productos.extend(prods)
                    logger.info(f"  → {len(prods)} productos")
                except ValueError:
                    pass
        except Exception as e:
            logger.warning(f"  Error: {e}")

        time.sleep(REQUEST_DELAY)

    return productos


# ─── SCRAPING DOM RÁPIDO ─────────────────────────────────────────────────────

def _scrape_dom_rapido(page, url, cat_nombre):
    productos = []

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        page.wait_for_timeout(2000)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

        items = page.evaluate('''() => {
            const results = [];
            const selectors = [
                '[data-testid*="product"]',
                '[class*="product-card"]',
                '[class*="productCard"]',
                'article[class*="product"]',
                '[class*="product-tile"]',
                '[class*="product-item"]',
                '.e-product',
                'li[class*="product"]',
            ];

            let els = [];
            for (const sel of selectors) {
                els = document.querySelectorAll(sel);
                if (els.length > 0) break;
            }

            for (const el of els) {
                const nameEl = el.querySelector('h2, h3, [class*="title"], [class*="name"]');
                const name = nameEl ? nameEl.textContent.trim() : '';

                const priceEl = el.querySelector('[class*="price"]');
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
                'Categoria': cat_nombre, 'Supermercado': 'Eroski',
                'Url': url_p, 'Url_imagen': item['image'],
            })

    except Exception as e:
        logger.warning(f"Error DOM: {e}")

    return productos


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def _tiene_productos(data):
    if isinstance(data, dict):
        for k in ['results', 'products', 'items', 'content', 'hits']:
            v = data.get(k)
            if isinstance(v, list) and len(v) > 2:
                return True
    return False


def _extraer_productos_json(data, cat_nombre):
    productos = []
    items = None

    if isinstance(data, dict):
        for k in ['results', 'products', 'items', 'content', 'hits', 'data']:
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
            'Categoria': cat_nombre, 'Supermercado': 'Eroski',
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
