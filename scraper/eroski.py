# -*- coding: utf-8 -*-

"""
Scraper de Eroski (supermercado.eroski.es).

Estrategia COMBINADA:
    Fase 1 – Mapeo de categorías:
        Navega a la home y extrae TODOS los links del mega-menú.
        Cada URL /es/supermercado/{id}-{slug}/ da un mapeo:
            id_numérico → "nombre legible"
        Esto se usa para traducir los IDs de GA4 a nombres reales.

    Fase 2 – Extracción por búsqueda:
        Navega a /es/search/results/?q=TERMINO
        Hace scroll para cargar lazy/infinite scroll.
        Extrae productos del DOM + datos GA4 (precio, marca, categorías).

    Fase 3 – Categorización:
        GA4 da item_category / item_category2 / item_category3 como IDs.
        Se cruzan con el mapeo de Fase 1 para obtener:
        "Frescos > Frutas > Naranjas y otros cítricos"
"""

import os
import re
import time
import logging
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://supermercado.eroski.es"

# Términos de búsqueda que cubren todo el supermercado
TERMINOS_BUSQUEDA = [
    "leche", "yogur", "queso", "huevos", "mantequilla", "nata",
    "frutas", "verduras", "ensalada", "patatas",
    "carne", "pollo", "cerdo", "ternera", "cordero",
    "pescado", "marisco", "salmon", "atun", "merluza",
    "jamon", "embutido", "chorizo", "salchichon",
    "pan", "cereales", "galletas", "bolleria",
    "pasta", "arroz", "legumbres", "lentejas",
    "aceite", "vinagre", "sal", "harina",
    "conservas", "tomate", "salsa", "caldo",
    "cafe", "te", "infusion", "cacao",
    "chocolate", "miel", "mermelada", "azucar",
    "patatas fritas", "frutos secos", "snacks",
    "congelados", "pizza", "helados", "croquetas",
    "agua", "refresco", "zumo", "cerveza", "vino",
    "detergente", "suavizante", "lejia", "lavavajillas",
    "papel higienico", "gel ducha", "champu", "jabon",
    "desodorante", "pasta dientes", "crema facial",
    "panales", "comida perro", "comida gato",
]


def gestion_eroski():
    """Función principal."""
    t0 = time.time()
    logger.info("Iniciando extracción de Eroski...")

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

            # ── Setup ─────────────────────────────────────────
            logger.info("Navegando a supermercado.eroski.es...")
            page.goto(
                "%s/es/supermercado/" % BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(4000)
            _aceptar_cookies(page)

            # ── Fase 1: Mapeo de categorías ───────────────────
            cat_map = _construir_mapa_categorias(page)
            logger.info(
                "Mapa de categorías: %d IDs mapeados.", len(cat_map)
            )

            # ── Fase 2: Búsqueda por términos ────────────────
            for termino in TERMINOS_BUSQUEDA:
                logger.info("Buscando: '%s'", termino)
                try:
                    productos = _buscar_productos(
                        page, termino, cat_map
                    )
                    nuevos = 0
                    for prod in productos:
                        if prod["Id"] not in ids_vistos:
                            ids_vistos.add(prod["Id"])
                            todos.append(prod)
                            nuevos += 1
                    logger.info(
                        "  → %d encontrados, %d nuevos (total: %d)",
                        len(productos), nuevos, len(ids_vistos),
                    )
                except Exception as e:
                    logger.warning(
                        "  Error buscando '%s': %s",
                        termino, str(e)[:80],
                    )

            browser.close()

    except Exception as e:
        logger.error("Error Playwright Eroski: %s", e)
        return pd.DataFrame()

    if not todos:
        logger.warning("Eroski: 0 productos extraídos.")
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    dur = time.time() - t0
    logger.info(
        "Eroski completado: %d productos en %dm %ds",
        len(df), int(dur // 60), int(dur % 60),
    )
    return df


# ══════════════════════════════════════════════════════════════
#  Fase 1: Mapa de categorías
# ══════════════════════════════════════════════════════════════

def _construir_mapa_categorias(page):
    """Extrae TODOS los links /es/supermercado/ del mega-menú
    y construye {id_numérico: nombre_legible}."""

    try:
        raw = page.evaluate("""
            () => {
                const links = document.querySelectorAll(
                    'a[href*="/es/supermercado/"]'
                );
                const urls = new Set();
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    if (href.includes('productdetail')) continue;
                    if (href.includes('login')) continue;
                    if (href.includes(':')) continue;
                    urls.add(href);
                }
                return [...urls];
            }
        """)
    except Exception:
        raw = []

    cat_map = {}

    for url in raw:
        # Extraer cada segmento {id}-{slug}
        segments = re.findall(r'/(\d+)-([^/]+)', url)
        for num_id, slug in segments:
            if num_id not in cat_map:
                name = slug.replace('-', ' ').strip().capitalize()
                cat_map[num_id] = name

    # Construir también rutas completas para cada hoja
    # (se almacenan con el ID de la hoja como clave especial)
    for url in raw:
        segments = re.findall(r'/(\d+)-([^/]+)', url)
        if len(segments) >= 2:
            # Construir ruta: "Padre > Hijo" o "Abuelo > Padre > Hijo"
            names = [
                s[1].replace('-', ' ').strip().capitalize()
                for s in segments
            ]
            path = " > ".join(names)
            leaf_id = segments[-1][0]
            cat_map["path_%s" % leaf_id] = path

    if not cat_map:
        logger.warning("No se pudo construir mapa de categorías.")

    return cat_map


def _resolver_categoria(cat_map, cat1, cat2, cat3, fallback):
    """Resuelve la categoría más específica usando el mapa.
    Prioridad: cat3 (más específica) > cat2 > cat1.
    Busca primero la ruta completa (path_ID), luego el nombre simple.
    """
    for cat_id in [cat3, cat2, cat1]:
        if not cat_id:
            continue
        # Intentar ruta completa
        path_key = "path_%s" % cat_id
        if path_key in cat_map:
            return cat_map[path_key]
        # Nombre simple
        if cat_id in cat_map:
            return cat_map[cat_id]

    return fallback


# ══════════════════════════════════════════════════════════════
#  Fase 2: Búsqueda y extracción
# ══════════════════════════════════════════════════════════════

def _aceptar_cookies(page):
    for sel in [
        "#onetrust-accept-btn-handler",
        'button:has-text("Aceptar")',
        'button:has-text("Aceptar todas las cookies")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(2000)
                return
        except Exception:
            continue


def _buscar_productos(page, termino, cat_map):
    """Navega a búsqueda, hace scroll, extrae productos del DOM."""
    url = "%s/es/search/results/?q=%s&suggestionsFilter=false" % (
        BASE_URL, termino,
    )

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return []
    page.wait_for_timeout(3000)

    # Scroll para cargar lazy / infinite scroll
    prev_count = 0
    stable = 0
    for _ in range(50):
        count = page.evaluate(
            "document.querySelectorAll('.product-item-lineal').length"
        )
        if count == prev_count:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        prev_count = count
        page.evaluate("window.scrollBy(0, 2000)")
        page.wait_for_timeout(800)

    # Extraer productos del DOM + GA4
    try:
        raw_list = page.evaluate("""
            () => {
                const prods = [];
                const items = document.querySelectorAll(
                    '.product-item-lineal:not(.criteoItem)'
                );

                for (const item of items) {
                    try {
                        const pDiv = item.querySelector('.product-item');
                        if (!pDiv) continue;

                        // ID y URL
                        const link = pDiv.querySelector(
                            'a[href*="/productdetail/"]'
                        );
                        if (!link) continue;
                        const href = link.getAttribute('href') || '';
                        const idMatch = href.match(/productdetail\\/(\d+)/);
                        if (!idMatch) continue;
                        const id = idMatch[1];

                        // Nombre
                        let name = '';
                        const descLink = pDiv.querySelector(
                            '.product-description a'
                        );
                        if (descLink) {
                            name = descLink.getAttribute('title') ||
                                   descLink.textContent.trim();
                        }
                        if (!name) {
                            const dt = pDiv.querySelector(
                                '.description-text'
                            );
                            if (dt) name = dt.textContent.trim();
                        }

                        // GA4 data del innerHTML
                        const html = pDiv.innerHTML;
                        let price = 0;
                        let brand = '';
                        let cat1 = '', cat2 = '', cat3 = '';

                        const pm = html.match(
                            /&quot;price&quot;:(\\d+\\.?\\d*)/
                        );
                        if (pm) price = parseFloat(pm[1]);

                        // Precio visible como fallback
                        if (!price) {
                            const pe = pDiv.querySelector(
                                '.price-offer-price, [class*="price"]'
                            );
                            if (pe) {
                                const pt = pe.textContent.trim();
                                const pmv = pt.match(/(\\d+),(\\d{2})/);
                                if (pmv) price = parseFloat(
                                    pmv[1] + '.' + pmv[2]
                                );
                            }
                        }

                        const bm = html.match(
                            /&quot;item_brand&quot;:&quot;([^&]*)&quot;/
                        );
                        if (bm) brand = bm[1];

                        const c1 = html.match(
                            /&quot;item_category&quot;:&quot;([^&]*)&quot;/
                        );
                        if (c1) cat1 = c1[1];

                        const c2 = html.match(
                            /&quot;item_category2&quot;:&quot;([^&]*)&quot;/
                        );
                        if (c2) cat2 = c2[1];

                        const c3 = html.match(
                            /&quot;item_category3&quot;:&quot;([^&]*)&quot;/
                        );
                        if (c3) cat3 = c3[1];

                        // Precio por unidad
                        let unitPrice = price;
                        const ue = pDiv.querySelector(
                            '.price-offer-description'
                        );
                        if (ue) {
                            const um = ue.textContent.match(
                                /(\\d+),(\\d{2})/
                            );
                            if (um) unitPrice = parseFloat(
                                um[1] + '.' + um[2]
                            );
                        }

                        // Imagen
                        let imgSrc = '';
                        const img = pDiv.querySelector(
                            '.product-image img'
                        );
                        if (img) imgSrc = img.getAttribute('src') ||
                                          img.getAttribute('data-src') || '';

                        // Formato
                        let formato = '';
                        const fm = name.match(
                            /(\\d+\\s*x\\s*\\d+\\s*(?:ml|l|g|kg|cl|ud)\\.?)/i
                        );
                        if (fm) formato = fm[1];
                        else {
                            const fm2 = name.match(
                                /(\\d+(?:[.,]\\d+)?\\s*(?:litros?|l|ml|cl|kg|g|gr)\\.?)/i
                            );
                            if (fm2) formato = fm2[1];
                        }

                        if (name && price > 0) {
                            prods.push({
                                id, name, price, unitPrice,
                                brand, cat1, cat2, cat3,
                                imgSrc, formato, href
                            });
                        }
                    } catch(e) {}
                }
                return prods;
            }
        """)
    except Exception:
        return []

    if not raw_list:
        return []

    productos = []
    seen = set()
    for raw in raw_list:
        pid = raw.get("id", "")
        if not pid or pid in seen:
            continue
        seen.add(pid)

        nombre = raw.get("name", "")
        precio = raw.get("price", 0)
        if not nombre or precio <= 0:
            continue

        # Resolver categoría real
        categoria = _resolver_categoria(
            cat_map,
            raw.get("cat1", ""),
            raw.get("cat2", ""),
            raw.get("cat3", ""),
            fallback=termino.capitalize(),
        )

        href = raw.get("href", "")
        if href and not href.startswith("http"):
            href = "%s%s" % (BASE_URL, href)

        productos.append({
            "Id": str(pid),
            "Nombre": nombre,
            "Precio": precio,
            "Precio_por_unidad": raw.get("unitPrice", precio),
            "Formato": raw.get("formato", ""),
            "Categoria": categoria,
            "Supermercado": "Eroski",
            "Url": href or "%s/es/productdetail/%s/" % (BASE_URL, pid),
            "Url_imagen": raw.get("imgSrc", ""),
            "Marca": raw.get("brand", ""),
        })

    return productos
