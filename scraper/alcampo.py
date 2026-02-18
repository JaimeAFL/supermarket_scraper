# -*- coding: utf-8 -*-

"""
Scraper de Alcampo (compraonline.alcampo.es).

Estrategia: Playwright COMPLETO.
    1. Abre navegador → acepta cookies.
    2. Navega a categoría → extrae categorías hoja con page.evaluate().
    3. Para CADA categoría hoja, navega y extrae productos de
       window.__PRELOADED_STATE__.data.products.productEntities
       con page.evaluate().

SIN requests (Alcampo/Ocado bloquea requests).
Todo se hace desde el navegador real.
"""

import os
import time
import logging
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://www.compraonline.alcampo.es"


def gestion_alcampo():
    """Función principal."""
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Alcampo...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado.")
        return pd.DataFrame()

    todos = []
    ids_vistos = set()

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

            # ── Setup inicial ─────────────────────────────────
            logger.info("Navegando a compraonline.alcampo.es...")
            page.goto(
                "%s/" % BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(5000)

            # Aceptar cookies
            _aceptar_cookies(page)

            # Configurar CP si hay selector
            cp = os.getenv("CODIGO_POSTAL", "28001")
            _configurar_cp(page, cp)

            # ── Navegar a categoría raíz para descubrir hojas ──
            page.goto(
                "%s/categories/~/%s" % (BASE_URL, "OC1603"),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(4000)

            # Descubrir categorías hoja
            categorias = _descubrir_categorias(page)
            if not categorias:
                logger.warning("No se encontraron categorías. Usando fallback.")
                categorias = _categorias_fallback()

            logger.info("Total categorías a procesar: %d", len(categorias))

            # ── Extraer productos de cada categoría ───────────
            for i, (retailer_id, cat_nombre) in enumerate(categorias):
                if i > 0 and i % 50 == 0:
                    logger.info(
                        "Progreso: %d/%d categorías, %d productos",
                        i, len(categorias), len(ids_vistos)
                    )

                try:
                    productos = _extraer_categoria_browser(
                        page, retailer_id, cat_nombre
                    )
                    nuevos = 0
                    for prod in productos:
                        if prod["Id"] not in ids_vistos:
                            ids_vistos.add(prod["Id"])
                            todos.append(prod)
                            nuevos += 1

                    if nuevos > 0:
                        logger.info(
                            "  %s (%s): %d nuevos",
                            cat_nombre, retailer_id, nuevos
                        )
                except Exception as e:
                    logger.warning(
                        "  Error en '%s': %s", cat_nombre, str(e)[:80]
                    )

            browser.close()

    except Exception as e:
        logger.error("Error Playwright Alcampo: %s", e)
        return pd.DataFrame()

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


def _aceptar_cookies(page):
    """Acepta banner de cookies."""
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
                return
        except Exception:
            continue


def _configurar_cp(page, cp):
    """Configura código postal si hay popup."""
    try:
        el = page.locator('input[placeholder*="postal"]').first
        if el.is_visible(timeout=2000):
            el.fill(cp)
            page.wait_for_timeout(1000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)
    except Exception:
        pass


def _descubrir_categorias(page):
    """Extrae categorías hoja de __PRELOADED_STATE__."""
    try:
        result = page.evaluate("""
            () => {
                const s = window.__PRELOADED_STATE__ ||
                          window.__INITIAL_STATE__ ||
                          window.__data;
                if (!s || !s.data || !s.data.categories) return null;

                const cats = s.data.categories.categories;
                const hojas = [];
                const excluir = new Set([
                    'Folletos y Promociones', 'Carnaval',
                    'Renueva la decoración de tu hogar',
                    'Súper Ofertas Frescos', 'Promociones Club Alcampo',
                ]);

                for (const [id, data] of Object.entries(cats)) {
                    const name = data.name || '';
                    const rid = data.retailerId || '';
                    const children = data.children || [];

                    if (excluir.has(name)) continue;
                    if (!children.length && rid) {
                        hojas.push([rid, name]);
                    }
                }
                return hojas;
            }
        """)
        if result:
            logger.info("Categorías hoja descubiertas: %d", len(result))
            return [(r[0], r[1]) for r in result]
    except Exception as e:
        logger.warning("Error descubriendo categorías: %s", e)

    return []


def _categorias_fallback():
    """Categorías fallback si no se pueden descubrir."""
    return [
        ("OC1701", "Frutas"),
        ("OC1702", "Verduras y hortalizas"),
        ("OC13", "Carne"),
        ("OC14", "Pescados, mariscos y moluscos"),
        ("OC15", "Charcutería"),
        ("OC151001", "Jamones y paletas"),
        ("OCQuesos", "Quesos"),
        ("OC1281", "Panadería"),
        ("OC1282", "Pastelería"),
        ("OC1603", "Leche"),
        ("OC1612", "Productos proteicos"),
        ("OCLAC2", "Yogures y postres"),
        ("OCLAC3", "Queso fresco y requesón"),
        ("OCLAC4", "Mantequilla y margarina"),
        ("OCLAC5", "Nata y crema"),
        ("OCHUEVOS", "Huevos"),
        ("OCPAN1", "Pan"),
        ("OCPAN2", "Pan de molde"),
        ("OCPAN3", "Bollería"),
        ("OCCER1", "Cereales"),
        ("OCCER2", "Galletas"),
        ("OCARROZ", "Arroz"),
        ("OCPASTA", "Pasta"),
        ("OCLEG", "Legumbres"),
        ("OCACEITE", "Aceite"),
        ("OCCONS1", "Conservas"),
        ("OCSALSA", "Salsas"),
        ("OCCAFE", "Café e infusiones"),
        ("OCCHOCO", "Chocolate y cacao"),
        ("OCSNACK", "Snacks"),
        ("OCCONG1", "Congelados"),
        ("OCAGUA", "Agua"),
        ("OCREFRES", "Refrescos"),
        ("OCZUMO", "Zumos"),
        ("OCCERV", "Cerveza"),
        ("OCVINO", "Vino"),
        ("OCLIMP1", "Detergentes"),
        ("OCLIMP2", "Limpiadores"),
        ("OCHIG1", "Gel y champú"),
        ("OCHIG2", "Desodorantes"),
        ("OCPAPEL", "Papel higiénico"),
        ("OCBEBE", "Bebé"),
        ("OCMASC", "Mascotas"),
    ]


def _extraer_categoria_browser(page, retailer_id, cat_nombre):
    """Navega a categoría y extrae productos de __PRELOADED_STATE__."""
    url = "%s/categories/~/%s" % (BASE_URL, retailer_id)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        return []

    page.wait_for_timeout(2000)

    # Extraer productos con page.evaluate()
    try:
        productos_raw = page.evaluate("""
            () => {
                const s = window.__PRELOADED_STATE__ ||
                          window.__INITIAL_STATE__ ||
                          window.__data;
                if (!s || !s.data || !s.data.products) return [];

                const entities = s.data.products.productEntities || {};
                const prods = [];

                for (const [id, prod] of Object.entries(entities)) {
                    if (!prod || !prod.name) continue;
                    if (prod.available === false) continue;

                    const price = prod.price || {};
                    const current = price.current || {};
                    const amount = current.amount;
                    if (!amount) continue;

                    const unitPrice = (price.unit || {}).current || {};
                    const size = prod.size || {};
                    const image = prod.image || {};
                    const catPath = prod.categoryPath || [];

                    prods.push({
                        id: prod.retailerProductId || prod.productId || '',
                        name: prod.name,
                        price: amount,
                        unitPrice: unitPrice.amount || amount,
                        brand: prod.brand || '',
                        size: size.value || '',
                        image: image.src || '',
                        category: catPath.length > 0 ?
                            catPath[catPath.length - 1] : ''
                    });
                }
                return prods;
            }
        """)
    except Exception:
        return []

    if not productos_raw:
        return []

    productos = []
    for raw in productos_raw:
        pid = raw.get("id", "")
        nombre = raw.get("name", "")
        if not pid or not nombre:
            continue

        try:
            precio = float(raw.get("price", 0))
        except (ValueError, TypeError):
            continue
        if precio <= 0:
            continue

        try:
            precio_u = float(raw.get("unitPrice", precio))
        except (ValueError, TypeError):
            precio_u = precio

        cat_real = raw.get("category", "") or cat_nombre

        productos.append({
            "Id": str(pid),
            "Nombre": nombre,
            "Precio": precio,
            "Precio_por_unidad": precio_u,
            "Formato": raw.get("size", ""),
            "Categoria": cat_real,
            "Supermercado": "Alcampo",
            "Url": "%s/products/%s" % (BASE_URL, pid),
            "Url_imagen": raw.get("image", ""),
            "Marca": raw.get("brand", ""),
        })

    return productos
