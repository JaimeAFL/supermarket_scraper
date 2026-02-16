# -*- coding: utf-8 -*-

"""
Scraper de Carrefour.

Estrategia HÍBRIDA (rápida):
    1. Playwright abre navegador → navega al supermercado → intercepta
       cookies+headers de las peticiones API reales.
    2. Cierra Playwright (~30s).
    3. Usa requests (rápido) con esas cookies para scraping masivo.
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

REQUEST_DELAY = 0.01


def gestion_carrefour():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Carrefour...")

    # Paso 1: Sesión válida con Playwright (~30s)
    sesion = _obtener_sesion_playwright()
    if not sesion:
        logger.error("No se pudo obtener sesión de Carrefour.")
        return pd.DataFrame()

    cookies = sesion['cookies']
    headers = sesion['headers']
    logger.info(f"Sesión obtenida ({len(cookies)} chars de cookies).")

    # Paso 2: Categorías vía API
    categorias = _obtener_categorias(cookies, headers)
    if not categorias:
        logger.warning("API de categorías falló, usando fallback...")
        categorias = _categorias_fallback()

    logger.info(f"{len(categorias)} categorías encontradas.")

    # Paso 3: Scraping masivo con requests
    df_products = pd.DataFrame()

    for idx, cat in enumerate(categorias):
        cat_nombre = cat.get('name', 'Desconocida')
        logger.info(f"{idx+1}/{len(categorias)} - {cat_nombre}")

        try:
            df_cat = _obtener_productos_categoria(cat, cookies, headers)
            if not df_cat.empty:
                df_products = pd.concat([df_products, df_cat], ignore_index=True)
                logger.info(f"  → {len(df_cat)} productos")
        except Exception as e:
            logger.warning(f"  Error: {e}")

        time.sleep(REQUEST_DELAY)

    if not df_products.empty:
        df_products = df_products.drop_duplicates(subset=['Id'], keep='first')

    duracion = time.time() - tiempo_inicio
    logger.info(f"Carrefour completado: {len(df_products)} productos en {int(duracion//60)}m {int(duracion%60)}s")
    return df_products


# ─── PASO 1: SESIÓN PLAYWRIGHT ───────────────────────────────────────────────

def _obtener_sesion_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado.")
        return None

    cp = os.getenv('CODIGO_POSTAL', '28001')
    api_capturas = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                locale='es-ES',
            )
            page = ctx.new_page()

            def capturar(request):
                url = request.url
                if any(k in url for k in ['cloud-api', 'carrefour.es/api', 'search-api', 'categories-api']):
                    c = request.headers.get('cookie', '')
                    if c:
                        api_capturas.append({'cookies': c, 'headers': dict(request.headers)})

            page.on('request', capturar)

            # Navegar
            page.goto('https://www.carrefour.es/supermercado/', wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)

            # Aceptar cookies banner
            for sel in ['#onetrust-accept-btn-handler', 'button:has-text("Aceptar todas")', 'button:has-text("Aceptar")']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.click()
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    continue

            # CP
            for sel in ['input[placeholder*="postal"]', 'input[name*="postal"]', 'input[data-testid*="postal"]']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        el.fill(cp)
                        page.wait_for_timeout(1000)
                        page.keyboard.press('Enter')
                        page.wait_for_timeout(3000)
                        break
                except Exception:
                    continue

            # Forzar peticiones API navegando a una categoría
            try:
                page.goto('https://www.carrefour.es/supermercado/alimentacion/cat20002/c',
                          wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(4000)
            except Exception:
                pass

            # Scroll para más peticiones
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Obtener la mejor captura
            mejor = max(api_capturas, key=lambda x: len(x['cookies']), default=None)

            if mejor:
                sesion = {
                    'cookies': mejor['cookies'],
                    'headers': {
                        'User-Agent': mejor['headers'].get('user-agent', ''),
                        'Accept': 'application/json',
                        'Accept-Language': 'es-ES',
                        'Referer': 'https://www.carrefour.es/supermercado/',
                    },
                }
            else:
                # Fallback: cookies del contexto
                cc = ctx.cookies()
                sesion = {
                    'cookies': "; ".join(f"{c['name']}={c['value']}" for c in cc),
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'application/json',
                        'Accept-Language': 'es-ES',
                        'Referer': 'https://www.carrefour.es/supermercado/',
                    },
                }

            browser.close()
            return sesion if sesion.get('cookies') else None

    except Exception as e:
        logger.error(f"Error Playwright: {e}")
        return None


# ─── PASO 2: CATEGORÍAS ──────────────────────────────────────────────────────

def _obtener_categorias(cookies, headers):
    h = {**headers, 'Cookie': cookies}
    for url in [
        'https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu/',
        'https://www.carrefour.es/cloud-api/categories-api/v1/categories/',
    ]:
        try:
            resp = req_lib.get(url, headers=h, timeout=15)
            if resp.status_code == 200:
                cats = _parsear_arbol(resp.json())
                if cats:
                    return cats
        except Exception:
            continue
    return []


def _parsear_arbol(data, res=None):
    if res is None:
        res = []
    if isinstance(data, list):
        for item in data:
            _parsear_arbol(item, res)
    elif isinstance(data, dict):
        url = data.get('url') or data.get('link') or ''
        nombre = data.get('name') or data.get('label') or ''
        cat_id = data.get('id') or ''
        if nombre and url and '/supermercado/' in str(url):
            res.append({'id': str(cat_id), 'name': str(nombre), 'url': str(url)})
        for k in ['children', 'subcategories', 'categories', 'items', 'sections']:
            if k in data and data[k]:
                _parsear_arbol(data[k], res)
    return res


def _categorias_fallback():
    b = 'https://www.carrefour.es/supermercado'
    return [
        {'id': 'cat20002', 'name': 'Alimentación', 'url': f'{b}/alimentacion/cat20002/c'},
        {'id': 'cat20090', 'name': 'Bebidas', 'url': f'{b}/bebidas/cat20090/c'},
        {'id': 'cat20017', 'name': 'Frescos', 'url': f'{b}/frescos/cat20017/c'},
        {'id': 'cat20057', 'name': 'Congelados', 'url': f'{b}/congelados/cat20057/c'},
        {'id': 'cat20003', 'name': 'Lácteos', 'url': f'{b}/lacteos/cat20003/c'},
        {'id': 'cat20113', 'name': 'Panadería', 'url': f'{b}/panaderia-y-bolleria/cat20113/c'},
        {'id': 'cat110', 'name': 'Limpieza y hogar', 'url': f'{b}/limpieza-y-hogar/cat110/c'},
        {'id': 'cat120', 'name': 'Higiene y belleza', 'url': f'{b}/higiene-y-belleza/cat120/c'},
        {'id': 'cat20310', 'name': 'Bebé', 'url': f'{b}/bebe/cat20310/c'},
        {'id': 'cat20340', 'name': 'Mascotas', 'url': f'{b}/mascotas/cat20340/c'},
    ]


# ─── PASO 3: PRODUCTOS POR CATEGORÍA ─────────────────────────────────────────

def _obtener_productos_categoria(cat, cookies, headers):
    h = {**headers, 'Cookie': cookies}
    cat_url = cat.get('url', '')

    cat_match = re.search(r'(cat\d+)', cat_url)
    cat_id = cat_match.group(1) if cat_match else cat.get('id', '')
    if not cat_id:
        return pd.DataFrame()

    productos = []
    offset = 0
    page_size = 24

    for _ in range(40):  # Máximo 40 páginas = 960 productos/categoría
        api_urls = [
            f'https://www.carrefour.es/cloud-api/plp-food-search-api/v2/search?offset={offset}&limit={page_size}&sort=relevance&categories={cat_id}',
            f'https://www.carrefour.es/cloud-api/search-api/v2/search?offset={offset}&limit={page_size}&sort=relevance&categories={cat_id}',
        ]

        data = None
        for api_url in api_urls:
            try:
                resp = req_lib.get(api_url, headers=h, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
            except Exception:
                continue

        if not data:
            break

        items = _extraer_items(data)
        if not items:
            break

        for item in items:
            prod = _parsear_producto(item, cat.get('name', ''))
            if prod:
                productos.append(prod)

        total = data.get('total', data.get('totalCount', data.get('totalResults', 0)))
        offset += page_size
        if offset >= total or len(items) < page_size:
            break

        time.sleep(REQUEST_DELAY)

    return pd.DataFrame(productos) if productos else pd.DataFrame()


def _extraer_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ['results', 'products', 'items', 'content', 'productCards', 'hits']:
            v = data.get(k)
            if isinstance(v, list) and v:
                return v
        for k in ['data', 'response']:
            v = data.get(k)
            if isinstance(v, dict):
                for sk in ['results', 'products', 'items']:
                    sv = v.get(sk)
                    if isinstance(sv, list) and sv:
                        return sv
    return None


def _parsear_producto(item, cat_nombre):
    if not isinstance(item, dict):
        return None

    nombre = item.get('display_name') or item.get('name') or item.get('title') or ''
    if not nombre:
        return None

    pid = item.get('id') or item.get('product_id') or item.get('productId') or item.get('sku') or hashlib.md5(nombre.encode()).hexdigest()[:12]

    precio = None
    for k in ['price', 'unit_price', 'unitPrice', 'currentPrice', 'active_price', 'salePrice']:
        v = item.get(k)
        if v is not None:
            try:
                precio = float(str(v).replace(',', '.').replace('€', '').strip())
                break
            except (ValueError, TypeError):
                continue

    if precio is None:
        for ok in ['price_instructions', 'priceInstructions', 'prices', 'priceInfo']:
            obj = item.get(ok)
            if isinstance(obj, dict):
                for sk in ['unit_price', 'unitPrice', 'price', 'current']:
                    v = obj.get(sk)
                    if v is not None:
                        try:
                            precio = float(str(v).replace(',', '.').replace('€', '').strip())
                            break
                        except (ValueError, TypeError):
                            continue
                if precio:
                    break

    if precio is None:
        return None

    precio_u = precio
    for k in ['price_per_unit', 'pricePerUnit', 'bulk_price']:
        v = item.get(k)
        if v is not None:
            try:
                precio_u = float(re.sub(r'[€/kgl\s]', '', str(v).replace(',', '.')))
                break
            except (ValueError, TypeError):
                continue

    fmt = item.get('size_format') or item.get('format') or item.get('packSize') or item.get('weight') or ''
    url_p = item.get('url') or item.get('link') or item.get('pdpUrl') or ''
    if url_p and url_p.startswith('/'):
        url_p = f"https://www.carrefour.es{url_p}"

    img = item.get('image') or item.get('thumbnail') or item.get('imageUrl') or ''
    if isinstance(img, dict):
        img = img.get('url') or img.get('src') or ''
    if isinstance(img, list) and img:
        img = img[0] if isinstance(img[0], str) else img[0].get('url', '')

    return {
        'Id': str(pid), 'Nombre': nombre, 'Precio': precio,
        'Precio_por_unidad': precio_u, 'Formato': str(fmt),
        'Categoria': cat_nombre, 'Supermercado': 'Carrefour',
        'Url': url_p, 'Url_imagen': str(img),
    }
