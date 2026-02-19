"""
scraper/carrefour.py - Scraper para Carrefour

FIXES aplicados tras inspección real de la red:
  1. URL de búsqueda: /?query=leche  (no /search?query=...&scope=supermarket)
  2. API interceptada: carrefour.es/search-api/query/v1/search  (no empathy.co)
  3. Estructura JSON real: content.docs[] con campos display_name, active_price,
     product_id, image_path, price_per_unit_text
"""

import logging
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)
BASE_URL = "https://www.carrefour.es"

TERMINOS_BUSQUEDA = [
    "leche", "yogur", "queso", "mantequilla", "nata", "natillas", "flan",
    "huevos", "fruta", "verdura", "patatas", "tomate", "cebolla", "zanahoria",
    "lechuga", "manzana", "naranja", "platano", "pera",
    "carne", "pollo", "cerdo", "ternera", "cordero", "jamon", "chorizo",
    "salchichon", "pavo", "fuet", "mortadela", "salchicha", "bacon",
    "pescado", "salmon", "atun", "merluza", "gambas", "marisco", "mejillones",
    "pan", "cereales", "galletas", "bolleria", "tostadas",
    "pasta", "arroz", "legumbres", "lentejas", "garbanzos", "alubias",
    "aceite", "vinagre", "sal", "azucar", "harina", "especias",
    "conserva", "tomate frito", "salsa", "mayonesa", "ketchup",
    "caldo", "sopa",
    "cafe", "te", "infusion", "cacao", "chocolate",
    "miel", "mermelada", "nocilla",
    "patatas fritas", "frutos secos", "aceitunas", "snacks",
    "pizza", "helado", "croquetas", "nuggets",
    "agua", "refresco", "coca cola", "zumo", "cerveza", "vino",
    "detergente", "suavizante", "lejia", "lavavajillas",
    "papel higienico", "papel cocina", "bolsas basura",
    "gel ducha", "champu", "jabon", "desodorante", "pasta dientes",
    "crema facial", "colonia",
    "panales", "toallitas bebe",
    "comida perro", "comida gato",
]

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


class _Acumulador:
    """
    Handler de red nombrado (no lambda) para poder registrarlo y
    quitarlo con page.on / page.remove_listener sin errores.
    """
    def __init__(self):
        self.datos = []

    def handler(self, response):
        url = response.url
        if response.status != 200:
            return
        # API real de Carrefour (confirmada por inspección de red)
        if "carrefour.es/search-api" in url:
            try:
                self.datos.append(response.json())
            except Exception:
                pass


def _aceptar_cookies(page):
    try:
        btn = page.locator(
            "#onetrust-accept-btn-handler, "
            "button[title='Aceptar todas las cookies'], "
            "button[class*='accept-all']"
        ).first
        if btn.is_visible(timeout=4000):
            btn.click()
            time.sleep(1.5)
    except Exception:
        pass


def _parsear_respuesta(data, categoria_fallback=""):
    """
    Parsea la respuesta real de carrefour.es/search-api/query/v1/search.

    Estructura confirmada:
    {
      "content": {
        "docs": [
          {
            "display_name": "Leche semidesnatada Carrefour brik 1 l.",
            "active_price": 0.88,
            "product_id": "521007071",
            "image_path": "https://static.carrefour.es/...",
            "price_per_unit_text": "0,88 €/l",
            "brand": "CARREFOUR",
            "url": "/supermercado/leche-semidesnatada.../R-521007071/p",
            "section": "15",
            ...
          }
        ],
        "numFound": 741
      }
    }
    """
    productos = []

    if not isinstance(data, dict):
        return productos

    docs = []
    content = data.get("content")
    if isinstance(content, dict):
        docs = content.get("docs") or []

    # Fallback por si la estructura cambia
    if not docs:
        docs = data.get("docs") or data.get("results") or []

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        try:
            # Precio — campo confirmado: active_price
            precio = None
            for campo in ["active_price", "list_price", "app_price", "price"]:
                val = doc.get(campo)
                if val is not None:
                    try:
                        precio = float(val)
                        if precio > 0:
                            break
                    except (ValueError, TypeError):
                        continue

            if not precio or precio <= 0:
                continue

            # ID — campo confirmado: product_id
            id_prod = str(
                doc.get("product_id") or doc.get("catalog_ref_id") or
                doc.get("id") or doc.get("ean13") or ""
            ).strip()
            if not id_prod:
                continue

            # Nombre — campo confirmado: display_name
            nombre = (
                doc.get("display_name") or doc.get("name") or doc.get("title") or ""
            ).strip()
            if not nombre:
                continue

            # Precio por unidad — campo confirmado: price_per_unit_text
            precio_unidad = str(doc.get("price_per_unit_text") or "").strip()

            # Imagen — campo confirmado: image_path
            imagen = str(doc.get("image_path") or "").strip()

            # URL — campo confirmado: url (relativa)
            url_prod = str(doc.get("url") or "").strip()
            if url_prod and not url_prod.startswith("http"):
                url_prod = BASE_URL + url_prod

            # Categoría
            categoria = str(
                doc.get("section") or doc.get("category") or categoria_fallback
            )

            productos.append({
                "Id":            id_prod,
                "Nombre":        nombre,
                "Precio":        precio,
                "Precio_unidad": precio_unidad,
                "Categoria":     categoria,
                "Supermercado":  "Carrefour",
                "URL":           url_prod,
                "URL_imagen":    imagen,
            })
        except Exception:
            continue

    return productos


def _fallback_dom(page, termino, ids_vistos):
    """Extracción DOM de último recurso."""
    nuevos = []
    try:
        datos = page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll(
                    '[data-product-id],[data-pid],[data-ean],'
                    'article[class*="product"],div[class*="ProductCard"]'
                ).forEach(el => {
                    const pid = el.dataset.productId || el.dataset.pid ||
                                el.dataset.ean || el.dataset.id || '';
                    const nameEl  = el.querySelector(
                        '[class*="title"],[class*="name"],h2,h3');
                    const priceEl = el.querySelector(
                        '[class*="price--sale"],[itemprop="price"],[class*="current"]');
                    const imgEl   = el.querySelector('img');
                    if (pid && nameEl && priceEl) {
                        results.push({
                            id:    pid,
                            name:  nameEl.innerText.trim(),
                            price: priceEl.getAttribute('content') ||
                                   priceEl.innerText.trim(),
                            img:   imgEl ? (imgEl.src || imgEl.dataset.src || '') : '',
                            url:   el.querySelector('a') ?
                                   el.querySelector('a').href : ''
                        });
                    }
                });
                return results;
            }
        """)
        for item in datos:
            if not item["id"] or item["id"] in ids_vistos:
                continue
            try:
                precio = float(
                    re.sub(r"[^\d.,]", "", str(item["price"])).replace(",", ".")
                )
                if precio <= 0:
                    continue
                ids_vistos.add(item["id"])
                nuevos.append({
                    "Id":            str(item["id"]),
                    "Nombre":        item["name"],
                    "Precio":        precio,
                    "Precio_unidad": "",
                    "Categoria":     termino.capitalize(),
                    "Supermercado":  "Carrefour",
                    "URL":           item.get("url", ""),
                    "URL_imagen":    item.get("img", ""),
                })
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"DOM fallback '{termino}': {e}")
    return nuevos


def _buscar_termino(page, termino, ids_vistos):
    """
    Navega a /?query=TERMINO (URL real confirmada) e intercepta
    la respuesta de search-api con handler nombrado.
    """
    acum = _Acumulador()
    page.on("response", acum.handler)
    try:
        # URL real: /?query=leche  (no /search?query=...&scope=supermarket)
        url = f"{BASE_URL}/?query={termino.replace(' ', '+')}"
        page.goto(url, wait_until="networkidle", timeout=35000)
        time.sleep(1.5)
        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(0.8)
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.debug(f"Timeout/error buscando '{termino}': {e}")
    finally:
        page.remove_listener("response", acum.handler)

    nuevos = []
    for data in acum.datos:
        for p in _parsear_respuesta(data, termino.capitalize()):
            if p["Id"] not in ids_vistos:
                ids_vistos.add(p["Id"])
                nuevos.append(p)

    if not nuevos:
        nuevos = _fallback_dom(page, termino, ids_vistos)

    return nuevos


def _navegar_categoria(page, url_cat, nombre_cat, ids_vistos):
    """Navega una categoría con paginación."""
    nuevos_total = []
    for pagina in range(1, 16):
        acum = _Acumulador()
        page.on("response", acum.handler)
        try:
            sep = "&" if "?" in url_cat else "?"
            url = (
                f"{BASE_URL}{url_cat}"
                if pagina == 1
                else f"{BASE_URL}{url_cat}{sep}start={(pagina - 1) * 24}"
            )
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1.2)
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error cat {url_cat} pág {pagina}: {e}")
        finally:
            page.remove_listener("response", acum.handler)

        nuevos_pag = []
        for data in acum.datos:
            for p in _parsear_respuesta(data, nombre_cat):
                if p["Id"] not in ids_vistos:
                    ids_vistos.add(p["Id"])
                    p["Categoria"] = nombre_cat
                    nuevos_pag.append(p)

        nuevos_total.extend(nuevos_pag)
        if len(nuevos_pag) < 3:
            break

    return nuevos_total


def gestion_carrefour():
    import pandas as pd
    inicio = time.time()
    logger.info("Iniciando extracción de Carrefour...")

    todos = []
    ids_vistos = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="es-ES",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        logger.info("Estableciendo sesión en carrefour.es...")
        try:
            page.goto(f"{BASE_URL}/supermercado/", wait_until="domcontentloaded", timeout=20000)
            _aceptar_cookies(page)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Error en visita inicial: {e}")

        # Fase 1: búsqueda por términos
        logger.info(f"Fase 1: búsqueda por {len(TERMINOS_BUSQUEDA)} términos...")
        for termino in TERMINOS_BUSQUEDA:
            nuevos = _buscar_termino(page, termino, ids_vistos)
            todos.extend(nuevos)
            if nuevos:
                logger.info(f"  '{termino}' → {len(nuevos)} nuevos (total: {len(todos)})")
            time.sleep(0.4)

        logger.info(f"Fase 1 completada: {len(todos)} productos")

        # Fase 2: navegación por categorías del menú
        logger.info(f"Fase 2: navegando {len(CATEGORIAS_MENU)} categorías...")
        for url_cat, nombre_cat in CATEGORIAS_MENU:
            nuevos = _navegar_categoria(page, url_cat, nombre_cat, ids_vistos)
            todos.extend(nuevos)
            if nuevos:
                logger.info(f"  '{nombre_cat}': {len(nuevos)} nuevos (total: {len(todos)})")

        browser.close()

    duracion = int(time.time() - inicio)
    logger.info(
        f"Carrefour completado: {len(todos)} productos en {duracion // 60}m {duracion % 60}s"
    )

    if not todos:
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    df = df[df["Precio"] > 0].drop_duplicates(subset=["Id"])
    return df
