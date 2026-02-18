# -*- coding: utf-8 -*-

"""
Scraper de Carrefour (carrefour.es/supermercado).

Estrategia COMBINADA:
    Fase 1 – Mapeo de categorías:
        Navega a /supermercado/ y extrae links del mega-menú.
        Cada link tiene catXXXXX y nombre legible.
        dataLayer push tiene p_category_level_1/2/3.
        Esto mapea IDs de categoría a nombres reales.

    Fase 2 – Extracción por búsqueda:
        Navega a /supermercado/?query=TERMINO
        Espera a que la SPA (Vue.js) renderice los productos.
        Extrae de dataLayer (GTM ecommerce) + DOM.
        Scroll para cargar más resultados.

    Fase 3 – Extracción por categorías:
        Navega a /supermercado/.../catXXXXX/c
        Mismo proceso de extracción.
        Complementa búsqueda con productos no encontrados.

La web es una SPA Vue.js que carga productos vía Empathy.co API.
Playwright ejecuta el JS real del navegador, por lo que la API
funciona desde el contexto de la página.
"""

import os
import re
import time
import logging
import pandas as pd

logger = logging.getLogger(__name__)

BASE = "https://www.carrefour.es"

# Términos de búsqueda para cobertura amplia
TERMINOS_BUSQUEDA = [
    "leche", "yogur", "queso", "huevos", "mantequilla",
    "nata", "natillas", "flan",
    "fruta", "verdura", "ensalada", "patatas", "tomate",
    "carne", "pollo", "cerdo", "ternera", "cordero",
    "pescado", "marisco", "salmon", "atun", "merluza", "gambas",
    "jamon", "chorizo", "salchichon", "pavo", "fuet",
    "pan", "cereales", "galletas", "bolleria", "tostadas",
    "pasta", "arroz", "legumbres", "lentejas", "garbanzos",
    "aceite", "vinagre", "sal", "harina", "especias",
    "conserva", "tomate frito", "salsa", "caldo", "sopa",
    "cafe", "te", "infusion", "cacao", "colacao",
    "chocolate", "miel", "mermelada", "azucar", "edulcorante",
    "patatas fritas", "frutos secos", "aceitunas", "snacks",
    "pizza", "helado", "croquetas", "congelados",
    "agua", "refresco", "coca cola", "zumo", "cerveza", "vino",
    "detergente", "suavizante", "lejia", "lavavajillas", "fregasuelos",
    "papel higienico", "gel ducha", "champu", "jabon",
    "desodorante", "pasta dientes", "crema",
    "panales", "comida perro", "comida gato",
]


def gestion_carrefour():
    """Función principal."""
    t0 = time.time()
    logger.info("Iniciando extracción de Carrefour...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright no instalado.")
        return pd.DataFrame()

    cp = os.getenv("CODIGO_POSTAL", "28001")
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

            # ── Setup ─────────────────────────────────────────
            logger.info("Navegando a carrefour.es/supermercado/...")
            page.goto(
                "%s/supermercado/" % BASE,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(5000)
            _aceptar_cookies(page)
            _configurar_cp(page, cp)

            # ── Fase 1: Mapeo de categorías ───────────────────
            cat_map = _construir_mapa_categorias(page)
            logger.info(
                "Mapa de categorías: %d entradas.", len(cat_map)
            )

            # ── Fase 2: Búsqueda por términos ────────────────
            for termino in TERMINOS_BUSQUEDA:
                logger.info("Buscando: '%s'", termino)
                try:
                    productos = _buscar_productos(page, termino, cat_map)
                    nuevos = 0
                    for prod in productos:
                        if prod["Id"] not in ids_vistos:
                            ids_vistos.add(prod["Id"])
                            todos.append(prod)
                            nuevos += 1
                    if nuevos > 0:
                        logger.info(
                            "  → %d encontrados, %d nuevos (total: %d)",
                            len(productos), nuevos, len(ids_vistos),
                        )
                    else:
                        logger.info(
                            "  → %d encontrados, 0 nuevos",
                            len(productos),
                        )
                except Exception as e:
                    logger.warning(
                        "  Error '%s': %s", termino, str(e)[:80]
                    )

            # ── Fase 3: Categorías complementarias ────────────
            categorias = _extraer_urls_categorias(cat_map)
            logger.info(
                "Categorías complementarias: %d", len(categorias)
            )
            for url, cat_nombre in categorias:
                try:
                    productos = _extraer_pagina(
                        page, url, cat_nombre, cat_map
                    )
                    nuevos = 0
                    for prod in productos:
                        if prod["Id"] not in ids_vistos:
                            ids_vistos.add(prod["Id"])
                            todos.append(prod)
                            nuevos += 1
                    if nuevos > 0:
                        logger.info(
                            "  Cat %s: %d nuevos", cat_nombre, nuevos
                        )
                except Exception as e:
                    logger.warning(
                        "  Error cat '%s': %s",
                        cat_nombre, str(e)[:80],
                    )

            browser.close()

    except Exception as e:
        logger.error("Error Playwright Carrefour: %s", e)
        return pd.DataFrame()

    if not todos:
        logger.warning("Carrefour: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    dur = time.time() - t0
    logger.info(
        "Carrefour completado: %d productos en %dm %ds",
        len(df), int(dur // 60), int(dur % 60),
    )
    return df


# ══════════════════════════════════════════════════════════════
#  Helpers generales
# ══════════════════════════════════════════════════════════════

def _aceptar_cookies(page):
    for sel in [
        "#onetrust-accept-btn-handler",
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(2000)
                return
        except Exception:
            continue


def _configurar_cp(page, cp):
    for sel in [
        'input[name="postal-code"]',
        'input[name="postal_code"]',
        'input[placeholder*="postal"]',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.fill(cp)
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)
                logger.info("CP %s configurado.", cp)
                return
        except Exception:
            continue


# ══════════════════════════════════════════════════════════════
#  Fase 1: Mapa de categorías
# ══════════════════════════════════════════════════════════════

def _construir_mapa_categorias(page):
    """Extrae links del mega-menú y construye mapa de catIDs → nombres."""
    try:
        links = page.evaluate("""
            () => {
                const result = [];
                const allLinks = document.querySelectorAll(
                    'a[href*="/supermercado/"]'
                );
                for (const a of allLinks) {
                    const href = a.getAttribute('href') || '';
                    const name = (a.getAttribute('title') ||
                                  a.textContent || '').trim();
                    if (name && href) result.push([href, name]);
                }
                return result;
            }
        """)
    except Exception:
        links = []

    cat_map = {}

    for href, name in links:
        # Extraer catXXXXX de la URL
        m = re.search(r'(cat\d+)/c', href)
        if m:
            cat_id = m.group(1)
            cat_map[cat_id] = name
            # También guardar URL completa
            full_url = href if href.startswith("http") else "%s%s" % (
                BASE, href
            )
            cat_map["url_%s" % cat_id] = full_url

        # p_category_level slugs (del dataLayer)
        # e.g. cat20001-la-despensa → "La Despensa"
        for seg in re.findall(r'(cat\d+)-([^/]+)', href):
            cid = seg[0]
            slug_name = seg[1].replace('-', ' ').strip().title()
            if cid not in cat_map:
                cat_map[cid] = slug_name

    return cat_map


def _extraer_urls_categorias(cat_map):
    """Construye lista de (url, nombre) desde el mapa."""
    categorias = []
    seen = set()
    for key, value in cat_map.items():
        if key.startswith("url_"):
            cat_id = key[4:]
            nombre = cat_map.get(cat_id, cat_id)
            if value not in seen:
                seen.add(value)
                categorias.append((value, nombre))
    return categorias


# ══════════════════════════════════════════════════════════════
#  Fase 2: Búsqueda
# ══════════════════════════════════════════════════════════════

def _buscar_productos(page, termino, cat_map):
    """Busca un término y extrae productos."""
    url = "%s/supermercado/?query=%s" % (BASE, termino)
    return _extraer_pagina(page, url, termino.capitalize(), cat_map)


def _extraer_pagina(page, url, fallback_cat, cat_map):
    """Navega a URL, espera SPA, scroll, extrae productos."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return []

    # Esperar a que la SPA renderice productos
    # Intentar esperar a un selector de producto
    _esperar_productos(page)

    # Scroll para cargar más resultados
    prev_count = 0
    stable = 0
    for _ in range(25):
        count = page.evaluate("""
            document.querySelectorAll(
                '.product-card-item, .product-card-list__item,' +
                '[class*="product-card"], .ebx-result'
            ).length
        """)
        if count == prev_count:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        prev_count = count
        page.evaluate("window.scrollBy(0, 1500)")
        page.wait_for_timeout(800)

    # Extraer con múltiples métodos
    productos = _extraer_datalayer(page, fallback_cat, cat_map)
    if not productos:
        productos = _extraer_dom(page, fallback_cat)

    return productos


def _esperar_productos(page):
    """Espera a que aparezcan product cards en el DOM."""
    selectores = [
        ".product-card-item",
        ".product-card-list__item",
        '[class*="product-card"]',
        ".ebx-result",
        ".product-card",
    ]
    for sel in selectores:
        try:
            page.wait_for_selector(sel, timeout=8000)
            page.wait_for_timeout(2000)
            return
        except Exception:
            continue
    # Si ningún selector aparece, esperar un poco de todas formas
    page.wait_for_timeout(5000)


# ══════════════════════════════════════════════════════════════
#  Extracción: dataLayer
# ══════════════════════════════════════════════════════════════

def _extraer_datalayer(page, fallback_cat, cat_map):
    """Extrae productos del dataLayer (GTM ecommerce events)."""
    try:
        data = page.evaluate("""
            () => {
                const dl = window.dataLayer || [];
                const products = [];
                const seen = new Set();

                for (const entry of dl) {
                    let items = null;

                    // GA4 format
                    if (entry.ecommerce && entry.ecommerce.items)
                        items = entry.ecommerce.items;
                    // Legacy UA impressions
                    else if (entry.ecommerce && entry.ecommerce.impressions)
                        items = entry.ecommerce.impressions;
                    // view_item_list format
                    else if (entry.event === 'view_item_list' &&
                             entry.ecommerce && entry.ecommerce.items)
                        items = entry.ecommerce.items;

                    if (!items) continue;

                    for (const item of items) {
                        const id = String(
                            item.item_id || item.id || ''
                        );
                        const name = item.item_name || item.name || '';
                        const price = parseFloat(item.price) || 0;

                        if (!id || !name || price <= 0) continue;
                        if (seen.has(id)) continue;
                        seen.add(id);

                        products.push({
                            id: id,
                            name: name,
                            price: price,
                            brand: item.item_brand || item.brand || '',
                            category: item.item_category ||
                                      item.category || '',
                            category2: item.item_category2 || '',
                            category3: item.item_category3 || '',
                            variant: item.item_variant ||
                                     item.variant || ''
                        });
                    }
                }
                return products;
            }
        """)
    except Exception:
        return []

    if not data:
        return []

    productos = []
    for raw in data:
        pid = str(raw.get("id", ""))
        nombre = raw.get("name", "")
        precio = raw.get("price", 0)
        if not pid or not nombre or precio <= 0:
            continue

        # Resolver categoría
        cat_raw = raw.get("category", "")
        categoria = _resolver_categoria_crf(
            cat_map, cat_raw, raw.get("category2", ""),
            raw.get("category3", ""), fallback_cat,
        )

        productos.append({
            "Id": pid,
            "Nombre": nombre,
            "Precio": precio,
            "Precio_por_unidad": precio,
            "Formato": _extraer_formato(nombre),
            "Categoria": categoria,
            "Supermercado": "Carrefour",
            "Url": "",
            "Url_imagen": "",
            "Marca": raw.get("brand", ""),
        })

    return productos


def _resolver_categoria_crf(cat_map, cat1, cat2, cat3, fallback):
    """Resuelve la categoría más específica.
    cat1/2/3 pueden ser 'catXXXXX-slug' o slug directos."""
    for cat_val in [cat3, cat2, cat1]:
        if not cat_val:
            continue
        # Buscar catXXXXX pattern
        m = re.search(r'(cat\d+)', cat_val)
        if m and m.group(1) in cat_map:
            return cat_map[m.group(1)]
        # Buscar como slug directo
        clean = cat_val.replace('-', ' ').strip()
        if clean and len(clean) > 2:
            return clean.title()
    return fallback


# ══════════════════════════════════════════════════════════════
#  Extracción: DOM
# ══════════════════════════════════════════════════════════════

def _extraer_dom(page, fallback_cat):
    """Extrae productos de los product cards renderizados."""
    try:
        data = page.evaluate("""
            () => {
                const prods = [];
                const seen = new Set();

                // Selectores amplios para product cards
                const cards = document.querySelectorAll(
                    '.product-card-item,' +
                    '.product-card-list__item,' +
                    '[class*="product-card"]:not([class*="list"]),' +
                    '.ebx-result'
                );

                for (const card of cards) {
                    try {
                        // Nombre
                        let name = '';
                        const nameEl = card.querySelector(
                            '[class*="title"] a,' +
                            '[class*="name"] a,' +
                            'a[title],' +
                            'h2 a, h3 a'
                        );
                        if (nameEl) {
                            name = nameEl.getAttribute('title') ||
                                   nameEl.textContent.trim();
                        }
                        if (!name) {
                            const any = card.querySelector(
                                '[class*="title"], [class*="name"], h2, h3'
                            );
                            if (any) name = any.textContent.trim();
                        }

                        // URL y ID
                        const link = card.querySelector(
                            'a[href*="/p"], a[href*="product"]'
                        );
                        const href = link ?
                            (link.getAttribute('href') || '') : '';
                        let id = '';
                        const mR = href.match(/R-(\\d+)/);
                        if (mR) id = mR[1];
                        else {
                            const mNum = href.match(/(\\d{6,})/);
                            if (mNum) id = mNum[1];
                        }

                        // Precio
                        let priceText = '';
                        const priceEl = card.querySelector(
                            '[class*="price"]:not([class*="per-unit"]),' +
                            '[class*="Price"]:not([class*="PerUnit"])'
                        );
                        if (priceEl) priceText = priceEl.textContent.trim();

                        // Imagen
                        const img = card.querySelector('img');
                        const imgSrc = img ?
                            (img.src || img.getAttribute('data-src') || '')
                            : '';

                        if (name && priceText.match(/\\d/) && id &&
                            !seen.has(id)) {
                            seen.add(id);
                            prods.push({
                                name, priceText, id,
                                href: href || '', imgSrc
                            });
                        }
                    } catch(e) {}
                }
                return prods;
            }
        """)
    except Exception:
        return []

    productos = []
    for raw in data:
        precio = _parse_precio(raw.get("priceText", ""))
        if precio is None or precio <= 0:
            continue
        pid = raw.get("id", "")
        nombre = raw.get("name", "")
        if not pid or not nombre:
            continue

        href = raw.get("href", "")
        if href and not href.startswith("http"):
            href = "%s%s" % (BASE, href)

        productos.append({
            "Id": pid,
            "Nombre": nombre,
            "Precio": precio,
            "Precio_por_unidad": precio,
            "Formato": _extraer_formato(nombre),
            "Categoria": fallback_cat,
            "Supermercado": "Carrefour",
            "Url": href,
            "Url_imagen": raw.get("imgSrc", ""),
            "Marca": _extraer_marca(nombre),
        })

    return productos


# ══════════════════════════════════════════════════════════════
#  Utilidades
# ══════════════════════════════════════════════════════════════

def _parse_precio(text):
    if not text:
        return None
    m = re.search(r"(\d+)[,.](\d{1,2})", text)
    if m:
        try:
            return float("%s.%s" % (m.group(1), m.group(2)))
        except (ValueError, TypeError):
            pass
    return None


def _extraer_formato(nombre):
    for pat in [
        r'(\d+\s*x\s*\d+\s*(?:ml|l|g|kg|cl|ud)\.?)',
        r'(\d+(?:[.,]\d+)?\s*(?:litros?|l|ml|cl)\.?)',
        r'(\d+(?:[.,]\d+)?\s*(?:kg|g|gr)\.?)',
        r'(pack\s*\d+)',
    ]:
        m = re.search(pat, nombre, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extraer_marca(nombre):
    m = re.match(
        r'^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\']+?)(?:\s+[a-záéíóúñ])', nombre
    )
    return m.group(1).strip() if m else ""
