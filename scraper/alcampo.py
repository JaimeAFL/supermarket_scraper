# -*- coding: utf-8 -*-

"""
Scraper de Alcampo.
Usa Playwright para navegar compraonline.alcampo.es y capturar
las respuestas de la API interna con datos de productos.
"""
import time
import logging
import pandas as pd


logger = logging.getLogger(__name__)

BASE_URL = "https://www.compraonline.alcampo.es"
REQUEST_DELAY = 2


def gestion_alcampo():
    """
    Función principal. Usa Playwright para navegar Alcampo y extraer productos.

    Returns:
        pd.DataFrame: DataFrame con productos de Alcampo.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado. pip install playwright && playwright install chromium")
        return pd.DataFrame()

    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Alcampo con Playwright...")

    all_products = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='es-ES',
            )
            page = context.new_page()

            # 1. Navegar a la home para aceptar cookies
            page.goto(BASE_URL, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            _aceptar_cookies(page)
            page.wait_for_timeout(2000)

            # 2. Obtener categorías principales
            page.goto(f"{BASE_URL}/categories", wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            categorias = page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href*="/categorias/"]');
                    const cats = [];
                    const seen = new Set();
                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        const name = link.textContent.trim();
                        if (href && name && !seen.has(href) && href.split('/').length >= 3) {
                            seen.add(href);
                            cats.push({url: href, nombre: name});
                        }
                    });
                    return cats;
                }
            """)

            if not categorias:
                # Intentar con otro selector
                categorias = page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a[class*="category"], a[class*="Category"], [data-testid*="category"] a');
                        const cats = [];
                        const seen = new Set();
                        links.forEach(link => {
                            const href = link.getAttribute('href');
                            const name = link.textContent.trim();
                            if (href && name && !seen.has(href)) {
                                seen.add(href);
                                cats.push({url: href, nombre: name});
                            }
                        });
                        return cats;
                    }
                """)

            logger.info(f"Encontradas {len(categorias)} categorías en Alcampo.")

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
        logger.error(f"Error general en Alcampo: {e}")

    # Construir DataFrame
    if all_products:
        df = pd.DataFrame(all_products)
        df = df.drop_duplicates(subset='Id', keep='first')
        duracion = time.time() - tiempo_inicio
        logger.info(f"Alcampo completado: {len(df)} productos en {int(duracion//60)}m {int(duracion%60)}s")
        return df

    logger.warning("No se obtuvieron productos de Alcampo.")
    return pd.DataFrame()


def _extraer_productos_categoria(page, url, nombre_categoria):
    """
    Navega a una categoría y extrae todos los productos visibles.
    Gestiona paginación haciendo scroll y clic en 'cargar más'.
    """
    productos = []

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)

        # Scroll progresivo para cargar productos lazy-loaded
        max_scrolls = 10
        for _ in range(max_scrolls):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

            # Intentar clic en "cargar más" o "ver más"
            try:
                boton = page.locator('button:has-text("Ver más"), button:has-text("Cargar más"), button:has-text("Mostrar más"), [data-testid="load-more"]').first
                if boton.is_visible(timeout=500):
                    boton.click()
                    page.wait_for_timeout(2000)
            except Exception:
                break

        # Extraer productos del DOM
        productos_raw = page.evaluate("""
            () => {
                const items = [];
                // Selectores comunes para product cards en Alcampo
                const cards = document.querySelectorAll(
                    '[data-testid="product-card"], .product-card, .productCard, ' +
                    '[class*="ProductCard"], [class*="product-card"], ' +
                    'article[class*="product"], div[class*="product-item"]'
                );

                cards.forEach(card => {
                    try {
                        // Nombre
                        const nameEl = card.querySelector(
                            '[data-testid="product-name"], [class*="product-name"], ' +
                            '[class*="productName"], [class*="ProductName"], ' +
                            'h2, h3, [class*="title"]'
                        );
                        const name = nameEl ? nameEl.textContent.trim() : '';

                        // Precio
                        const priceEl = card.querySelector(
                            '[data-testid="product-price"], [class*="product-price"], ' +
                            '[class*="productPrice"], [class*="Price"], ' +
                            '[class*="price"]'
                        );
                        let priceText = priceEl ? priceEl.textContent.trim() : '';
                        let price = parseFloat(priceText.replace(/[^0-9,.-]/g, '').replace(',', '.')) || 0;

                        // Precio por unidad
                        const pxuEl = card.querySelector(
                            '[class*="price-per-unit"], [class*="pricePerUnit"], ' +
                            '[class*="unit-price"], [class*="unitPrice"]'
                        );
                        let pxu = pxuEl ? pxuEl.textContent.trim() : '';

                        // Formato
                        const formatEl = card.querySelector(
                            '[class*="format"], [class*="weight"], [class*="size"], ' +
                            '[class*="grammage"], [class*="package"]'
                        );
                        let format = formatEl ? formatEl.textContent.trim() : '';

                        // URL
                        const linkEl = card.querySelector('a[href]');
                        let url = linkEl ? linkEl.getAttribute('href') : '';

                        // Imagen
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
                'Id': f"alcampo_{hash(prod['nombre'] + str(prod['precio'])) % 10**8}",
                'Nombre': prod['nombre'],
                'Precio': prod['precio'],
                'Precio_por_unidad': prod['precio_por_unidad'],
                'Formato': prod['formato'],
                'Categoria': nombre_categoria,
                'Supermercado': 'Alcampo',
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
