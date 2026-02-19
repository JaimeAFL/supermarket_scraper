"""
scraper/carrefour.py - Scraper para Carrefour
PROBLEMA ORIGINAL: El dataLayer siempre devolvía los MISMOS ~54 productos fijos
(promoted/featured) sin importar el término de búsqueda → 0 nuevos tras el primero.

SOLUCIÓN: Interceptar las respuestas de la API de Empathy.co directamente
desde el contexto del navegador Playwright. La API devuelve JSON con todos
los productos de la búsqueda real, bypaseando el bloqueo Cloudflare porque
la request la hace el propio navegador con las cookies/headers correctos.
"""

import logging
import time
import json
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.carrefour.es"

# Términos de búsqueda amplios para máxima cobertura
TERMINOS_BUSQUEDA = [
    "leche", "yogur", "queso", "mantequilla", "nata", "natillas", "flan", "postre",
    "huevos", "fruta", "verdura", "patatas", "tomate", "cebolla", "zanahoria",
    "lechuga", "manzana", "naranja", "platano", "pera", "limon",
    "carne", "pollo", "cerdo", "ternera", "cordero", "jamon", "chorizo",
    "salchichon", "pavo", "fuet", "mortadela", "salchicha", "bacon",
    "pescado", "salmon", "atun", "merluza", "gambas", "marisco", "mejillones",
    "pan", "cereales", "galletas", "bolleria", "tostadas", "croissant",
    "pasta", "arroz", "legumbres", "lentejas", "garbanzos", "alubias",
    "aceite", "vinagre", "sal", "azucar", "harina", "especias", "pimienta",
    "conserva", "tomate frito", "salsa", "mayonesa", "ketchup", "mostaza",
    "caldo", "sopa", "crema verduras",
    "cafe", "te", "infusion", "cacao", "chocolate", "colacao",
    "miel", "mermelada", "nocilla", "mantequilla cacahuete",
    "patatas fritas", "frutos secos", "aceitunas", "snacks", "palomitas",
    "pizza", "helado", "croquetas", "nuggets", "lasagna", "canelones",
    "agua", "refresco", "coca cola", "fanta", "zumo", "cerveza", "vino",
    "sidra", "cava",
    "detergente", "suavizante", "lejia", "lavavajillas", "fregasuelos",
    "papel higienico", "papel cocina", "bolsas basura",
    "gel ducha", "champu", "jabon", "desodorante", "pasta dientes",
    "crema facial", "colonia", "maquillaje", "afeitado",
    "panales", "toallitas bebe", "leche bebe",
    "comida perro", "comida gato", "arena gato",
]

# Categorías del menú de supermercado (URL slug → nombre)
CATEGORIAS_MENU = [
    ("/supermercado/frescos/c/sup01", "Frescos"),
    ("/supermercado/lacteos-y-huevos/c/sup02", "Lácteos y Huevos"),
    ("/supermercado/congelados/c/sup03", "Congelados"),
    ("/supermercado/alimentacion/c/sup04", "Alimentación"),
    ("/supermercado/bebidas/c/sup05", "Bebidas"),
    ("/supermercado/drogueria-y-limpieza/c/sup06", "Droguería"),
    ("/supermercado/perfumeria-e-higiene/c/sup07", "Perfumería"),
    ("/supermercado/bebe/c/sup08", "Bebé"),
    ("/supermercado/mascotas/c/sup09", "Mascotas"),
    ("/supermercado/parafarmacia/c/sup10", "Parafarmacia"),
]


def _aceptar_cookies(page):
    """Acepta el banner de cookies si aparece."""
    try:
        btn = page.locator(
            "#onetrust-accept-btn-handler, "
            "button[title='Aceptar todas las cookies'], "
            "button[class*='accept-all']"
        ).first
        if btn.is_visible(timeout=4000):
            btn.click()
            logger.debug("Banner de cookies aceptado.")
            time.sleep(1.5)
    except Exception:
        pass


def _setup_intercepcion(page, resultados_api):
    """
    Configura interceptación de red para capturar respuestas de Empathy.co
    y de la API interna de Carrefour. Esta es la clave de la solución:
    el navegador hace la request con todos los headers/cookies correctos
    y nosotros capturamos el JSON de respuesta.
    """
    def on_response(response):
        url = response.url
        status = response.status

        # Empathy.co es el motor de búsqueda de Carrefour
        if status != 200:
            return

        es_empathy = "empathy.co" in url and ("search" in url or "query" in url)
        es_carrefour_api = ("carrefour.es/api" in url and
                           ("product" in url or "search" in url or "catalog" in url))

        if es_empathy or es_carrefour_api:
            try:
                data = response.json()
                resultados_api.append({"url": url, "data": data})
                logger.debug(f"Interceptada respuesta API: {url[:80]}...")
            except Exception:
                pass

    page.on("response", on_response)


def _parsear_respuesta_empathy(data):
    """
    Parsea la respuesta JSON de la API de Empathy.co.
    Estructura típica: data.catalog.content[].docs[] o data.results[]
    """
    productos = []

    # Intentar diferentes estructuras de respuesta de Empathy
    docs = []

    if isinstance(data, dict):
        # Estructura principal de Empathy
        catalog = data.get("catalog") or data.get("data") or data
        if isinstance(catalog, dict):
            content = catalog.get("content") or []
            for seccion in content:
                if isinstance(seccion, dict):
                    docs.extend(seccion.get("docs") or [])

            # Alternativa directa
            if not docs:
                docs = catalog.get("docs") or catalog.get("results") or []

        # Estructura simplificada
        if not docs:
            docs = data.get("docs") or data.get("results") or data.get("products") or []

    for doc in docs:
        if not isinstance(doc, dict):
            continue

        try:
            # Precio - Empathy suele tener "price" o "eb_price"
            precio = None
            for campo_precio in ["price", "eb_price", "salePrice", "currentPrice",
                                 "price_es", "priceValue", "originalPrice"]:
                val = doc.get(campo_precio)
                if val is not None:
                    try:
                        if isinstance(val, str):
                            val = re.sub(r"[^\d.,]", "", val).replace(",", ".")
                        precio = float(val)
                        if precio > 0:
                            break
                    except (ValueError, TypeError):
                        continue

            if not precio or precio <= 0:
                continue

            # ID
            id_producto = str(
                doc.get("id") or doc.get("productId") or
                doc.get("eb_sku") or doc.get("sku") or
                doc.get("code") or ""
            )
            if not id_producto:
                continue

            # Nombre
            nombre = (doc.get("name") or doc.get("title") or
                     doc.get("eb_name") or "").strip()
            if not nombre:
                continue

            # Categoría
            categoria = ""
            cats = doc.get("categories") or doc.get("eb_category") or []
            if isinstance(cats, list) and cats:
                categoria = str(cats[-1]) if cats else ""
            elif isinstance(cats, str):
                categoria = cats

            # Precio unitario
            precio_unidad = str(doc.get("pricePerUnit") or doc.get("unitPrice") or
                               doc.get("eb_pricePerUnit") or "")

            # Imagen
            imagen = ""
            imgs = doc.get("image") or doc.get("images") or doc.get("eb_image") or []
            if isinstance(imgs, list) and imgs:
                imagen = imgs[0] if isinstance(imgs[0], str) else imgs[0].get("url", "")
            elif isinstance(imgs, str):
                imagen = imgs

            # URL del producto
            url_prod = doc.get("url") or doc.get("eb_url") or ""
            if url_prod and not url_prod.startswith("http"):
                url_prod = BASE_URL + url_prod

            productos.append({
                "Id": id_producto,
                "Nombre": nombre,
                "Precio": precio,
                "Precio_unidad": precio_unidad,
                "Categoria": categoria,
                "Supermercado": "Carrefour",
                "URL": url_prod,
                "URL_imagen": imagen,
            })

        except Exception:
            continue

    return productos


def _buscar_termino_con_intercepcion(page, termino, resultados_globales):
    """
    Navega a la página de búsqueda e intercepta la respuesta de la API.
    Retorna lista de productos nuevos.
    """
    resultados_api = []

    # Activar interceptación ANTES de navegar
    page.on("response", lambda r: _capturar_respuesta(r, resultados_api))

    url_busqueda = f"{BASE_URL}/search?query={termino.replace(' ', '+')}&scope=supermarket"

    try:
        page.goto(url_busqueda, wait_until="networkidle", timeout=35000)
        # Esperar adicional para JS asíncrono
        time.sleep(2)

        # Scroll para disparar carga de más productos
        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(1)

    except PlaywrightTimeoutError:
        logger.debug(f"Timeout buscando '{termino}', procesando lo interceptado...")
    except Exception as e:
        logger.debug(f"Error buscando '{termino}': {e}")
    finally:
        page.remove_listener("response", lambda r: _capturar_respuesta(r, resultados_api))

    # Parsear respuestas interceptadas
    nuevos = []
    for item in resultados_api:
        prods = _parsear_respuesta_empathy(item["data"])
        for p in prods:
            if p["Id"] not in resultados_globales:
                resultados_globales.add(p["Id"])
                p["Categoria"] = p["Categoria"] or termino.capitalize()
                nuevos.append(p)

    # Si la intercepción no funcionó, usar fallback DOM
    if not nuevos:
        nuevos_dom = _fallback_dom(page, termino, resultados_globales)
        nuevos.extend(nuevos_dom)

    return nuevos


def _capturar_respuesta(response, lista):
    """Handler de interceptación de red."""
    url = response.url
    if response.status != 200:
        return
    if ("empathy.co" in url or "carrefour.es/api" in url) and (
            "search" in url or "query" in url or "product" in url):
        try:
            data = response.json()
            lista.append({"url": url, "data": data})
        except Exception:
            pass


def _fallback_dom(page, termino, resultados_globales):
    """
    Fallback: extrae productos del DOM cuando la intercepción falla.
    Usa atributos data-* y el window.dataLayer como último recurso,
    pero ahora busca en los items específicos de la búsqueda actual,
    no en los datos globales de la página.
    """
    nuevos = []
    try:
        # Intentar extraer desde el estado interno de React/Vue si existe
        datos = page.evaluate("""
            () => {
                // Buscar en el store de Vuex o estado de React
                const results = [];
                
                // Método 1: Atributos data en tarjetas de producto
                const tarjetas = document.querySelectorAll(
                    '[data-product-id], [data-pid], [data-ean], ' +
                    'article[class*="product"], div[class*="ProductCard"]'
                );
                
                tarjetas.forEach(el => {
                    const pid = el.dataset.productId || el.dataset.pid || 
                                el.dataset.ean || el.dataset.id || '';
                    const nameEl = el.querySelector(
                        '[class*="title"], [class*="name"], h2, h3, [class*="ProductCard__name"]'
                    );
                    const priceEl = el.querySelector(
                        '[class*="price--sale"], [class*="ProductCard__price"], ' +
                        '[class*="current-price"], [itemprop="price"]'
                    );
                    const imgEl = el.querySelector('img[src*="carrefour"], img[data-src*="carrefour"]');
                    
                    if (pid && nameEl && priceEl) {
                        results.push({
                            id: pid,
                            name: nameEl.innerText.trim(),
                            price: priceEl.getAttribute('content') || priceEl.innerText.trim(),
                            img: imgEl ? (imgEl.src || imgEl.dataset.src || '') : '',
                            url: el.querySelector('a') ? el.querySelector('a').href : ''
                        });
                    }
                });
                
                // Método 2: JSON-LD de la página
                if (results.length === 0) {
                    document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                        try {
                            const d = JSON.parse(s.textContent);
                            if (d['@type'] === 'ItemList' && d.itemListElement) {
                                d.itemListElement.forEach(item => {
                                    if (item.item && item.item.offers) {
                                        results.push({
                                            id: item.item.sku || item.item['@id'] || '',
                                            name: item.item.name || '',
                                            price: item.item.offers.price || 0,
                                            img: item.item.image || '',
                                            url: item.item.url || ''
                                        });
                                    }
                                });
                            }
                        } catch(e) {}
                    });
                }
                
                return results;
            }
        """)

        for item in datos:
            try:
                if not item["id"] or item["id"] in resultados_globales:
                    continue

                precio_str = re.sub(r"[^\d.,]", "", str(item["price"])).replace(",", ".")
                if not precio_str:
                    continue

                precio = float(precio_str)
                if precio <= 0:
                    continue

                resultados_globales.add(item["id"])
                nuevos.append({
                    "Id": str(item["id"]),
                    "Nombre": item["name"],
                    "Precio": precio,
                    "Precio_unidad": "",
                    "Categoria": termino.capitalize(),
                    "Supermercado": "Carrefour",
                    "URL": item.get("url", ""),
                    "URL_imagen": item.get("img", ""),
                })
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error en fallback DOM '{termino}': {e}")

    return nuevos


def _navegar_categoria(page, url_cat, nombre_cat, resultados_globales):
    """
    Navega una categoría completa con paginación, interceptando las respuestas API.
    """
    nuevos_total = []
    pagina = 1
    max_paginas = 15

    while pagina <= max_paginas:
        resultados_api = []
        listener = lambda r: _capturar_respuesta(r, resultados_api)
        page.on("response", listener)

        try:
            if pagina == 1:
                url = f"{BASE_URL}{url_cat}"
            else:
                sep = "&" if "?" in url_cat else "?"
                url = f"{BASE_URL}{url_cat}{sep}start={(pagina - 1) * 24}"

            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1.5)

        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error en categoría {url_cat} pág {pagina}: {e}")
        finally:
            page.remove_listener("response", listener)

        nuevos_pagina = []
        for item in resultados_api:
            prods = _parsear_respuesta_empathy(item["data"])
            for p in prods:
                if p["Id"] not in resultados_globales:
                    resultados_globales.add(p["Id"])
                    p["Categoria"] = nombre_cat
                    nuevos_pagina.append(p)

        nuevos_total.extend(nuevos_pagina)

        if len(nuevos_pagina) < 3:
            # Sin productos nuevos → fin de categoría
            break

        pagina += 1

    return nuevos_total


def gestion_carrefour():
    """
    Scraper principal de Carrefour con interceptación de red Playwright.
    """
    import pandas as pd
    inicio = time.time()
    logger.info("Iniciando extracción de Carrefour...")

    todos_productos = []
    ids_vistos = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-ES",
            extra_http_headers={
                "Accept-Language": "es-ES,es;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
            }
        )

        page = context.new_page()

        # Enmascarar automatización
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        # Visita inicial - aceptar cookies y establecer sesión
        logger.info("Estableciendo sesión en carrefour.es...")
        try:
            page.goto(f"{BASE_URL}/supermercado/", wait_until="domcontentloaded", timeout=20000)
            _aceptar_cookies(page)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Error en visita inicial: {e}")

        # FASE 1: Búsqueda por términos (volumen principal)
        logger.info(f"Fase 1: búsqueda por {len(TERMINOS_BUSQUEDA)} términos...")
        for i, termino in enumerate(TERMINOS_BUSQUEDA):
            antes = len(todos_productos)
            nuevos = _buscar_termino_con_intercepcion(page, termino, ids_vistos)
            todos_productos.extend(nuevos)

            if nuevos:
                logger.info(f"  '{termino}' → {len(nuevos)} nuevos (total: {len(todos_productos)})")
            else:
                logger.debug(f"  '{termino}' → 0 nuevos")

            # Pausa para no saturar
            time.sleep(0.5)

        logger.info(f"Fase 1 completada: {len(todos_productos)} productos")

        # FASE 2: Navegación por categorías del menú (complemento)
        logger.info(f"Fase 2: navegando {len(CATEGORIAS_MENU)} categorías del menú...")
        for url_cat, nombre_cat in CATEGORIAS_MENU:
            antes = len(todos_productos)
            nuevos = _navegar_categoria(page, url_cat, nombre_cat, ids_vistos)
            todos_productos.extend(nuevos)

            if nuevos:
                logger.info(f"  Cat '{nombre_cat}': {len(nuevos)} nuevos (total: {len(todos_productos)})")

        browser.close()

    duracion = int(time.time() - inicio)
    logger.info(f"Carrefour completado: {len(todos_productos)} productos en {duracion // 60}m {duracion % 60}s")

    if not todos_productos:
        return pd.DataFrame()

    df = pd.DataFrame(todos_productos)
    df = df[df["Precio"] > 0]
    df = df.drop_duplicates(subset=["Id"])
    return df
