"""
scraper/dia.py - Scraper para Dia
SOLUCIÓN: Día ha reforzado su protección (error 599 incluso con cookie válida).
Se abandona el enfoque de llamadas directas a la API y se usa Playwright
para navegar las categorías e interceptar las respuestas de red.
"""

import logging
import time
import json
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dia.es"

# Categorías principales del catálogo online de Dia
# Extraídas del sitemap y navegación del sitio
CATEGORIAS_DIA = [
    ("charcuteria-y-quesos", "Charcutería y Quesos", [
        "jamon-cocido-lacon-fiambres-y-mortadela/c/L2001",
        "jamon-serrano-iberico-y-cecina/c/L2002",
        "quesos/c/L2003",
        "salchichas-y-bacon/c/L2004",
        "chopped-mortadela-y-pate/c/L2005",
        "salchichon-chorizo-y-fuet/c/L2006",
    ]),
    ("lacteos-y-huevos", "Lácteos y Huevos", [
        "leche/c/L3001",
        "yogures-y-postres-lacteos/c/L3002",
        "mantequilla-y-margarinas/c/L3003",
        "nata-para-cocinar-y-montar/c/L3004",
        "huevos/c/L3005",
        "bebidas-vegetales/c/L3006",
    ]),
    ("frescos", "Frescos", [
        "frutas-y-verduras/c/L4001",
        "carnes-y-aves/c/L4002",
        "pescados-y-mariscos/c/L4003",
        "platos-preparados/c/L4004",
        "pasta-fresca-y-pizza/c/L4005",
    ]),
    ("congelados", "Congelados", [
        "pescados-y-mariscos-congelados/c/L5001",
        "verduras-y-legumbres-congeladas/c/L5002",
        "carnes-y-aves-congeladas/c/L5003",
        "pizzas-y-platos-preparados-congelados/c/L5004",
        "helados/c/L5005",
    ]),
    ("despensa", "Despensa", [
        "aceite-y-vinagre/c/L6001",
        "arroces-y-pastas/c/L6002",
        "legumbres/c/L6003",
        "conservas-y-platos-preparados/c/L6004",
        "salsas-y-especias/c/L6005",
        "caldos-sopas-y-purés/c/L6006",
        "sal-azucar-y-harinas/c/L6007",
    ]),
    ("desayuno-y-merienda", "Desayuno y Merienda", [
        "galletas/c/L7001",
        "cereales/c/L7002",
        "mermeladas-y-cremas/c/L7003",
        "miel-y-edulcorantes/c/L7004",
        "pan-tostado-y-biscotes/c/L7005",
        "chocolates-y-cacaos/c/L7006",
        "cafes-e-infusiones/c/L7007",
        "bolleria-y-pasteleria/c/L7008",
    ]),
    ("bebidas", "Bebidas", [
        "agua/c/L8001",
        "refrescos/c/L8002",
        "zumos/c/L8003",
        "cervezas/c/L8004",
        "vinos-y-cavas/c/L8005",
        "otras-bebidas-alcoholicas/c/L8006",
    ]),
    ("snacks-y-dulces", "Snacks y Dulces", [
        "patatas-fritas-y-snacks/c/L9001",
        "frutos-secos/c/L9002",
        "aceitunas-y-encurtidos/c/L9003",
        "caramelos-y-gominolas/c/L9004",
    ]),
    ("drogueria", "Droguería", [
        "detergentes/c/L10001",
        "suavizantes/c/L10002",
        "limpiahogar/c/L10003",
        "papel-higienico-y-cocina/c/L10004",
        "bolsas-y-film/c/L10005",
    ]),
    ("higiene-y-belleza", "Higiene y Belleza", [
        "geles-y-jabones/c/L11001",
        "champus-y-acondicionadores/c/L11002",
        "desodorantes/c/L11003",
        "higiene-bucal/c/L11004",
        "cremas-y-cosmetica/c/L11005",
        "higiene-femenina/c/L11006",
    ]),
    ("bebes", "Bebés", [
        "panales/c/L12001",
        "alimentacion-bebe/c/L12002",
        "higiene-bebe/c/L12003",
    ]),
    ("mascotas", "Mascotas", [
        "comida-perros/c/L13001",
        "comida-gatos/c/L13002",
        "accesorios-mascotas/c/L13003",
    ]),
]


def _aceptar_cookies(page):
    """Acepta el banner de cookies si aparece."""
    try:
        btn = page.locator("button#onetrust-accept-btn-handler, button[id*='accept'], button[class*='accept-cookie']").first
        if btn.is_visible(timeout=3000):
            btn.click()
            time.sleep(1)
    except Exception:
        pass


def _extraer_productos_de_pagina(page, url_categoria, nombre_categoria):
    """
    Navega a la URL de categoría e intercepta las respuestas de la API interna de Dia.
    Dia usa una API interna en /api/v1/products o similar al cargar cada página de categoría.
    """
    productos = []
    interceptados = []

    def capturar_respuesta(response):
        url = response.url
        # Capturar llamadas a la API de productos de Dia
        if ("/api/v1/products" in url or
                "/api/v1/plp" in url or
                "product-search" in url or
                "/search?" in url) and response.status == 200:
            try:
                data = response.json()
                interceptados.append(data)
            except Exception:
                pass

    page.on("response", capturar_respuesta)

    try:
        page.goto(url_categoria, wait_until="networkidle", timeout=30000)
        _aceptar_cookies(page)
        time.sleep(2)

        # Scroll para cargar lazy-loaded content
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

    except PlaywrightTimeoutError:
        logger.warning(f"Timeout navegando {url_categoria}")
    except Exception as e:
        logger.warning(f"Error navegando {url_categoria}: {e}")
    finally:
        page.remove_listener("response", capturar_respuesta)

    # Procesar respuestas interceptadas
    for data in interceptados:
        nuevos = _parsear_respuesta_api(data, nombre_categoria)
        productos.extend(nuevos)

    # Si no se interceptó nada, intentar extracción DOM
    if not productos:
        productos = _extraer_dom(page, nombre_categoria)

    return productos


def _parsear_respuesta_api(data, categoria):
    """Parsea la respuesta JSON de la API de Dia."""
    productos = []

    # Estructura típica de la API de Dia
    items = []
    if isinstance(data, dict):
        items = (data.get("products") or
                 data.get("items") or
                 data.get("results") or
                 data.get("data", {}).get("products") or
                 [])
    elif isinstance(data, list):
        items = data

    for item in items:
        if not isinstance(item, dict):
            continue

        try:
            # Extraer precio
            precio = None
            precio_info = item.get("price") or item.get("prices") or {}
            if isinstance(precio_info, dict):
                precio = (precio_info.get("value") or
                         precio_info.get("formattedValue") or
                         precio_info.get("current") or
                         precio_info.get("sale"))
            elif isinstance(precio_info, (int, float)):
                precio = precio_info

            if precio is None:
                precio = item.get("priceValue") or item.get("currentPrice")

            if precio is None:
                continue

            # Limpiar precio
            if isinstance(precio, str):
                precio = float(re.sub(r"[^\d.,]", "", precio).replace(",", "."))

            producto = {
                "Id": str(item.get("code") or item.get("id") or item.get("ean") or ""),
                "Nombre": item.get("name") or item.get("title") or "",
                "Precio": float(precio),
                "Precio_unidad": item.get("pricePerUnit") or item.get("unitPrice") or "",
                "Categoria": categoria,
                "Supermercado": "Dia",
                "URL": f"{BASE_URL}/es/p/{item.get('code', '')}",
                "URL_imagen": (item.get("images") or [{}])[0].get("url") if item.get("images") else item.get("imageUrl") or "",
            }

            if producto["Id"] and producto["Nombre"]:
                productos.append(producto)

        except Exception:
            continue

    return productos


def _extraer_dom(page, categoria):
    """
    Fallback: extrae productos directamente del DOM renderizado.
    Funciona cuando no se interceptan respuestas API.
    """
    productos = []

    try:
        # Esperar a que haya tarjetas de producto
        page.wait_for_selector(
            "article[class*='product'], div[class*='product-tile'], li[class*='product']",
            timeout=8000
        )
    except PlaywrightTimeoutError:
        return productos

    try:
        items = page.evaluate("""
            () => {
                const results = [];
                const selectors = [
                    'article[class*="product"]',
                    'div[class*="product-tile"]',
                    'li[class*="product-item"]',
                    '[data-product-code]',
                    '[data-ean]'
                ];
                
                let elements = [];
                for (const sel of selectors) {
                    elements = document.querySelectorAll(sel);
                    if (elements.length > 0) break;
                }
                
                elements.forEach(el => {
                    const code = el.dataset.productCode || el.dataset.ean || el.dataset.id || '';
                    const nameEl = el.querySelector('[class*="name"], [class*="title"], h2, h3');
                    const priceEl = el.querySelector('[class*="price"]:not([class*="unit"]):not([class*="old"])');
                    const imgEl = el.querySelector('img');
                    
                    if (code && nameEl && priceEl) {
                        results.push({
                            code: code,
                            name: nameEl.innerText.trim(),
                            price: priceEl.innerText.trim(),
                            img: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                        });
                    }
                });
                return results;
            }
        """)

        for item in items:
            try:
                precio_str = re.sub(r"[^\d.,]", "", item["price"]).replace(",", ".")
                if not precio_str:
                    continue
                precio = float(precio_str)

                productos.append({
                    "Id": str(item["code"]),
                    "Nombre": item["name"],
                    "Precio": precio,
                    "Precio_unidad": "",
                    "Categoria": categoria,
                    "Supermercado": "Dia",
                    "URL": f"{BASE_URL}/es/p/{item['code']}",
                    "URL_imagen": item.get("img", ""),
                })
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Error extracción DOM: {e}")

    return productos


def _paginar_categoria(page, url_base, nombre_categoria, pagina_size=48):
    """Itera páginas de una categoría hasta que no haya más resultados."""
    todos = []
    vistos = set()
    pagina = 1

    while True:
        # Dia suele usar ?currentPage=N o ?page=N
        if pagina == 1:
            url = url_base
        else:
            sep = "&" if "?" in url_base else "?"
            url = f"{url_base}{sep}currentPage={pagina - 1}"

        antes = len(todos)
        nuevos = _extraer_productos_de_pagina(page, url, nombre_categoria)

        # Filtrar ya vistos
        for p in nuevos:
            if p["Id"] and p["Id"] not in vistos:
                vistos.add(p["Id"])
                todos.append(p)

        ahora = len(todos)

        if ahora - antes < 5:
            # Sin productos nuevos significativos → fin de categoría
            break

        if len(nuevos) < pagina_size:
            # Última página (devolvió menos de los esperados)
            break

        pagina += 1
        if pagina > 20:  # Salvaguarda
            break

    return todos


def gestion_dia(codigo_postal="28001"):
    """
    Scraper principal de Dia usando Playwright completo.
    Navega categorías e intercepta respuestas de la API interna.
    """
    import pandas as pd
    inicio = time.time()
    logger.info("Iniciando extracción de Dia con Playwright (modo completo)...")

    todos_productos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
            extra_http_headers={
                "Accept-Language": "es-ES,es;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )

        page = context.new_page()

        # Primera visita para aceptar cookies y establecer sesión
        logger.info("Estableciendo sesión en Dia...")
        try:
            page.goto(f"{BASE_URL}/es/", wait_until="domcontentloaded", timeout=20000)
            _aceptar_cookies(page)

            # Configurar código postal si hay selector
            try:
                cp_btn = page.locator("[class*='postal'], [class*='location'], [data-testid*='postal']").first
                if cp_btn.is_visible(timeout=3000):
                    cp_btn.click()
                    time.sleep(1)
                    page.fill("input[placeholder*='postal'], input[name*='postal']", codigo_postal)
                    page.keyboard.press("Enter")
                    time.sleep(2)
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Error en visita inicial: {e}")

        # Navegar categorías
        total_categorias = sum(len(subs) for _, _, subs in CATEGORIAS_DIA)
        procesadas = 0

        for seccion, nombre_seccion, subcategorias in CATEGORIAS_DIA:
            for sub_path in subcategorias:
                url = f"{BASE_URL}/es/compra-online/{seccion}/{sub_path}"
                nombre_cat = f"{nombre_seccion}"

                try:
                    productos_cat = _paginar_categoria(page, url, nombre_cat)
                    todos_productos.extend(productos_cat)
                    procesadas += 1

                    if productos_cat:
                        logger.info(f"  {nombre_cat} ({sub_path.split('/')[0]}): {len(productos_cat)} productos (total: {len(todos_productos)})")
                    else:
                        logger.debug(f"  {nombre_cat} ({sub_path.split('/')[0]}): sin productos")

                except Exception as e:
                    logger.warning(f"  Error en {url}: {e}")
                    procesadas += 1

        browser.close()

    # Deduplicar
    vistos = set()
    unicos = []
    for p in todos_productos:
        key = (p["Id"], p["Supermercado"])
        if key not in vistos:
            vistos.add(key)
            unicos.append(p)

    duracion = int(time.time() - inicio)
    logger.info(f"Extracción de Dia completada: {len(unicos)} productos en {duracion // 60}m {duracion % 60}s")

    if not unicos:
        return pd.DataFrame()

    df = pd.DataFrame(unicos)
    df = df[df["Precio"] > 0]
    return df
