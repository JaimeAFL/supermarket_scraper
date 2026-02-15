# -*- coding: utf-8 -*-

"""
Scraper de Eroski.
Usa Playwright para navegar supermercado.eroski.es y extraer
datos de productos directamente del DOM.
"""

import os
import json
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://supermercado.eroski.es"
REQUEST_DELAY = 2


def gestion_eroski():
    """
    Función principal. Usa Playwright para navegar Eroski y extraer productos.

    Returns:
        pd.DataFrame: DataFrame con productos de Eroski.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado. pip install playwright && playwright install chromium")
        return pd.DataFrame()

    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Eroski con Playwright...")

    all_products = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='es-ES',
            )
            page = context.new_page()

            # 1. Navegar a home y aceptar cookies
            page.goto(BASE_URL, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            _aceptar_cookies(page)
            page.wait_for_timeout(2000)

            # 2. Obtener categorías desde el menú de navegación
            categorias = page.evaluate("""
                () => {
                    const links = document.querySelectorAll(
                        'a[href*="/es/supermercado/"], nav a[href*="/categoria/"], ' +
                        '[class*="category"] a, [class*="Category"] a, ' +
                        '[class*="menu"] a[href*="/es/"]'
                    );
                    const cats = [];
                    const seen = new Set();
                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        const name = link.textContent.trim();
                        // Filtrar solo categorías de supermercado (alimentación, etc.)
                        if (href && name && name.length > 2 && name.length < 60 &&
                            !seen.has(href) && !href.includes('login') &&
                            !href.includes('registro') && !href.includes('carrito')) {
                            seen.add(href);
                            cats.push({url: href, nombre: name});
                        }
                    });
                    return cats;
                }
            """)

            # Si no encontramos categorías desde el menú, intentar desde la home
            if not categorias or len(categorias) < 3:
                logger.info("Buscando categorías desde la página principal...")
                categorias = _obtener_categorias_home(page)

            logger.info(f"Encontradas {len(categorias)} categorías en Eroski.")

            # 3. Navegar cada categoría y extraer productos
            for i, cat in enumerate(categorias):
                cat_url = cat['url']
                if not cat_url.startswith('http'):
                    cat_url = BASE_URL + cat_url

                logger.info(f"{i+1}/{len(categorias)} - {cat['nombre']}")

                try:
                    productos_cat = _extraer_productos_categoria(page, cat_url, cat['nombre'])
                    all_products.extend(productos_cat)
                except Exception as e:
                    logger.warning(f"Error en categoría {cat['nombre']}: {e}")

                time.sleep(REQUEST_DELAY)

            browser.close()

    except Exception as e:
        logger.error(f"Error general en Eroski: {e}")

    if all_products:
        df = pd.DataFrame(all_products)
        df = df.drop_duplicates(subset='Id', keep='first')
        duracion = time.time() - tiempo_inicio
        logger.info(f"Eroski completado: {len(df)} productos en {int(duracion//60)}m {int(duracion%60)}s")
        return df

    logger.warning("No se obtuvieron productos de Eroski.")
    return pd.DataFrame()


def _obtener_categorias_home(page):
    """Obtiene categorías navegando la home de Eroski."""
    categorias = []
    try:
        page.goto(f"{BASE_URL}/es/supermercado/", wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)

        categorias = page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href]');
                const cats = [];
                const seen = new Set();
                links.forEach(link => {
                    const href = link.getAttribute('href');
                    const name = link.textContent.trim();
                    if (href && name && name.length > 2 && name.length < 60 &&
                        !seen.has(href) &&
                        (href.includes('/supermercado/') || href.includes('/categoria/')) &&
                        !href.includes('login') && !href.includes('carrito')) {
                        seen.add(href);
                        cats.push({url: href, nombre: name});
                    }
                });
                return cats;
            }
        """)
    except Exception as e:
        logger.warning(f"Error obteniendo categorías de home: {e}")

    return categorias


def _extraer_productos_categoria(page, url, nombre_categoria):
    """
    Navega a una categoría y extrae productos del DOM.
    Gestiona paginación con scroll y botones.
    """
    productos = []

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)

        # Scroll para cargar productos lazy-loaded
        max_scrolls = 10
        for _ in range(max_scrolls):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

            # Intentar "cargar más"
            try:
                boton = page.locator('button:has-text("Ver más"), button:has-text("Cargar más"), button:has-text("Mostrar más"), a:has-text("Ver más productos")').first
                if boton.is_visible(timeout=500):
                    boton.click()
                    page.wait_for_timeout(2000)
            except Exception:
                break

        # Extraer productos
        productos_raw = page.evaluate("""
            () => {
                const items = [];
                const cards = document.querySelectorAll(
                    '[class*="product-card"], [class*="productCard"], [class*="ProductCard"], ' +
                    'article[class*="product"], div[class*="product-item"], ' +
                    '[data-testid*="product"], li[class*="product"]'
                );

                cards.forEach(card => {
                    try {
                        const nameEl = card.querySelector(
                            '[class*="product-name"], [class*="productName"], ' +
                            '[class*="ProductName"], h2, h3, [class*="title"]'
                        );
                        const name = nameEl ? nameEl.textContent.trim() : '';

                        const priceEl = card.querySelector(
                            '[class*="product-price"], [class*="productPrice"], ' +
                            '[class*="Price"], [class*="price"]:not([class*="unit"])'
                        );
                        let priceText = priceEl ? priceEl.textContent.trim() : '';
                        let price = parseFloat(priceText.replace(/[^0-9,.-]/g, '').replace(',', '.')) || 0;

                        const pxuEl = card.querySelector(
                            '[class*="price-per-unit"], [class*="pricePerUnit"], ' +
                            '[class*="unit-price"], [class*="unitPrice"]'
                        );
                        let pxu = pxuEl ? pxuEl.textContent.trim() : '';

                        const formatEl = card.querySelector(
                            '[class*="format"], [class*="weight"], [class*="size"], ' +
                            '[class*="package"]'
                        );
                        let format = formatEl ? formatEl.textContent.trim() : '';

                        const linkEl = card.querySelector('a[href]');
                        let url = linkEl ? linkEl.getAttribute('href') : '';

                        const imgEl = card.querySelector('img');
                        let img = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';

                        if (name && price > 0) {
                            items.push({
                                nombre: name,
                                precio: price,
                                precio_por_unidad: pxu,
                                formato: format,
                                url: url,
                                imagen: img
                            });
                        }
                    } catch (e) {}
                });
                return items;
            }
        """)

        for prod in productos_raw:
            prod_url = prod['url']
            if prod_url and not prod_url.startswith('http'):
                prod_url = BASE_URL + prod_url
            img_url = prod['imagen']
            if img_url and not img_url.startswith('http'):
                img_url = BASE_URL + img_url

            productos.append({
                'Id': f"eroski_{hash(prod['nombre'] + str(prod['precio'])) % 10**8}",
                'Nombre': prod['nombre'],
                'Precio': prod['precio'],
                'Precio_por_unidad': prod['precio_por_unidad'],
                'Formato': prod['formato'],
                'Categoria': nombre_categoria,
                'Supermercado': 'Eroski',
                'Url': prod_url,
                'Url_imagen': img_url,
            })

    except Exception as e:
        logger.warning(f"Error extrayendo productos de {url}: {e}")

    return productos


def _aceptar_cookies(page):
    """Intenta aceptar el banner de cookies."""
    selectores = [
        '#onetrust-accept-btn-handler',
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar todo")',
        'button:has-text("Aceptar")',
        'button:has-text("Acepto")',
        '[data-testid="cookie-accept"]',
    ]
    for selector in selectores:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=500):
                el.click()
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue
