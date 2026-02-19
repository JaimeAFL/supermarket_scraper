"""
scraper/dia.py - Scraper para Dia

BUG CORREGIDO: El scraper anterior tardaba 14 minutos y extraía 0 productos.
Causas:
  1. Las URLs hardcodeadas (/es/compra-online/seccion/c/LXXX) no existen en Dia.
     La estructura real del sitio es diferente y los códigos L2001, L3001, etc.
     eran inventados.
  2. El filtro de intercepción era demasiado estricto ("/api/v1/products",
     "/api/v1/plp", "product-search") y no coincidía con las rutas reales de Dia.

SOLUCIÓN:
  1. Navegar desde la página principal descubriendo las URLs reales del menú.
  2. Interceptar TODAS las respuestas JSON y filtrar por contenido
     (arrays de productos) en lugar de filtrar por URL.
  3. Usar también búsqueda por términos como red de seguridad.
"""

import logging
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)
BASE_URL = "https://www.dia.es"

# Términos de búsqueda como fallback si la navegación por categorías falla
TERMINOS_DIA = [
    "leche", "yogur", "queso", "mantequilla", "huevos", "nata",
    "jamon", "chorizo", "salchichon", "mortadela", "bacon",
    "pollo", "carne", "ternera", "cerdo", "pescado", "salmon", "atun", "merluza",
    "fruta", "verdura", "patatas", "tomate", "cebolla",
    "pan", "cereales", "galletas", "bolleria",
    "pasta", "arroz", "legumbres", "aceite", "vinagre", "sal", "harina",
    "conservas", "salsa", "caldo", "sopa",
    "cafe", "te", "chocolate", "cacao", "miel", "mermelada", "azucar",
    "agua", "refresco", "zumo", "cerveza", "vino",
    "patatas fritas", "frutos secos", "aceitunas", "snacks", "helado",
    "detergente", "suavizante", "lejia", "papel higienico",
    "gel ducha", "champu", "desodorante", "pasta dientes",
    "panales", "comida perro", "comida gato",
]


class _Acumulador:
    """Handler de red nombrado (no lambda) para poder registrarlo y quitarlo."""
    def __init__(self):
        self.datos = []

    def handler(self, response):
        """Captura TODA respuesta JSON con status 200 para filtrar después."""
        if response.status != 200:
            return
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return
        try:
            data = response.json()
            # Solo guardar si parece una lista de productos
            if _parece_productos(data):
                self.datos.append(data)
        except Exception:
            pass


def _parece_productos(data):
    """Devuelve True si el JSON parece contener una lista de productos."""
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        primero = data[0]
        campos_producto = {"name", "price", "id", "code", "ean", "nombre", "precio"}
        return bool(campos_producto & set(primero.keys()))

    if isinstance(data, dict):
        for clave in ("products", "items", "results", "data", "productList"):
            val = data.get(clave)
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return True
        # Estructura paginada
        if "pagination" in data or "totalCount" in data or "total" in data:
            return True

    return False


def _parsear_json(data, categoria):
    """Extrae productos de cualquier estructura JSON de Dia."""
    productos = []

    # Normalizar a lista de items
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for clave in ("products", "items", "results", "productList", "data"):
            val = data.get(clave)
            if isinstance(val, list):
                items = val
                break
        if not items:
            # Puede ser un solo producto
            if "name" in data or "nombre" in data:
                items = [data]

    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            # Nombre
            nombre = (item.get("name") or item.get("nombre") or
                      item.get("title") or item.get("displayName") or "").strip()
            if not nombre:
                continue

            # ID
            id_prod = str(
                item.get("code") or item.get("id") or item.get("ean") or
                item.get("productCode") or item.get("sku") or ""
            ).strip()
            if not id_prod:
                continue

            # Precio
            precio = None
            for campo in ["price", "precio", "salePrice", "currentPrice", "priceValue"]:
                val = item.get(campo)
                if val is None:
                    continue
                if isinstance(val, dict):
                    # price: {value: 1.99} o price: {current: 1.99}
                    val = val.get("value") or val.get("current") or val.get("formattedValue")
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

            # Precio por unidad
            precio_unidad = ""
            for campo in ["pricePerUnit", "unitPrice", "precioUnidad", "priceUnit"]:
                val = item.get(campo)
                if val:
                    precio_unidad = str(val)
                    break

            # Imagen
            imagen = ""
            for campo in ["imageUrl", "image", "thumbnail", "imagen"]:
                val = item.get(campo)
                if isinstance(val, str) and val:
                    imagen = val
                    break
                if isinstance(val, list) and val:
                    imagen = val[0] if isinstance(val[0], str) else val[0].get("url", "")
                    break

            productos.append({
                "Id":           id_prod,
                "Nombre":       nombre,
                "Precio":       precio,
                "Precio_unidad": precio_unidad,
                "Categoria":    categoria,
                "Supermercado": "Dia",
                "URL":          f"{BASE_URL}/es/p/{id_prod}",
                "URL_imagen":   imagen,
            })
        except Exception:
            continue

    return productos


def _aceptar_cookies(page):
    try:
        btn = page.locator(
            "button#onetrust-accept-btn-handler, "
            "button[id*='accept-all'], "
            "button[class*='accept-cookie']"
        ).first
        if btn.is_visible(timeout=4000):
            btn.click()
            time.sleep(1.5)
    except Exception:
        pass


def _descubrir_urls_categorias(page):
    """
    Navega la página principal de Dia y extrae las URLs reales del menú de categorías.
    Así no dependemos de URLs hardcodeadas que pueden no existir.
    """
    urls = []
    try:
        page.goto(f"{BASE_URL}/es/compra-online/", wait_until="domcontentloaded", timeout=20000)
        _aceptar_cookies(page)
        time.sleep(2)

        # Extraer links del menú de categorías
        links = page.evaluate("""
            () => {
                const links = new Set();
                // Buscar en el menú principal y navegación lateral
                document.querySelectorAll(
                    'nav a[href*="/compra-online/"], '
                    'aside a[href*="/compra-online/"], '
                    '[class*="menu"] a[href*="/compra-online/"], '
                    '[class*="nav"] a[href*="/compra-online/"], '
                    '[class*="category"] a[href*="/compra-online/"]'
                ).forEach(a => {
                    if (a.href && !a.href.includes('?') && a.href.length < 150) {
                        links.add(a.href);
                    }
                });
                return Array.from(links);
            }
        """)

        for link in links:
            # Filtrar solo URLs de categorías reales (no la raíz)
            if link.count("/") >= 5:  # profundidad mínima de subcategoría
                nombre = link.rstrip("/").split("/")[-1].replace("-", " ").title()
                urls.append((link, nombre))

        logger.info(f"Categorías descubiertas en Dia: {len(urls)}")

    except Exception as e:
        logger.warning(f"No se pudieron descubrir categorías de Dia: {e}")

    return urls


def _navegar_categoria(page, url, nombre_cat, ids_vistos):
    """Navega una categoría interceptando todas las respuestas JSON."""
    nuevos_total = []

    for pagina in range(1, 15):
        acum = _Acumulador()
        page.on("response", acum.handler)

        try:
            if pagina == 1:
                url_pag = url
            else:
                sep = "&" if "?" in url else "?"
                url_pag = f"{url}{sep}currentPage={pagina - 1}"

            page.goto(url_pag, wait_until="networkidle", timeout=25000)
            time.sleep(1.5)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(0.8)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error en {url} pág {pagina}: {e}")
        finally:
            page.remove_listener("response", acum.handler)

        nuevos_pag = []
        for data in acum.datos:
            prods = _parsear_json(data, nombre_cat)
            for p in prods:
                if p["Id"] not in ids_vistos:
                    ids_vistos.add(p["Id"])
                    nuevos_pag.append(p)

        # También intentar extracción DOM si no hay intercepción
        if not nuevos_pag and pagina == 1:
            nuevos_pag = _extraer_dom(page, nombre_cat, ids_vistos)

        nuevos_total.extend(nuevos_pag)

        if len(nuevos_pag) < 5:
            break  # Sin más resultados

    return nuevos_total


def _buscar_termino(page, termino, ids_vistos):
    """Búsqueda por término como red de seguridad."""
    acum = _Acumulador()
    page.on("response", acum.handler)

    try:
        url = f"{BASE_URL}/es/search/?q={termino.replace(' ', '+')}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(1.5)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.debug(f"Error búsqueda '{termino}': {e}")
    finally:
        page.remove_listener("response", acum.handler)

    nuevos = []
    for data in acum.datos:
        for p in _parsear_json(data, termino.capitalize()):
            if p["Id"] not in ids_vistos:
                ids_vistos.add(p["Id"])
                nuevos.append(p)

    # Fallback DOM
    if not nuevos:
        nuevos = _extraer_dom(page, termino.capitalize(), ids_vistos)

    return nuevos


def _extraer_dom(page, categoria, ids_vistos):
    """Extracción DOM de último recurso."""
    nuevos = []
    try:
        items = page.evaluate("""
            () => {
                const results = [];
                const selectores = [
                    'article[class*="product"]',
                    'div[class*="product-tile"]',
                    'li[class*="product-item"]',
                    '[data-product-code]',
                    '[data-ean]',
                    '[data-product-id]'
                ];
                let elementos = [];
                for (const sel of selectores) {
                    elementos = document.querySelectorAll(sel);
                    if (elementos.length > 0) break;
                }
                elementos.forEach(el => {
                    const code = el.dataset.productCode || el.dataset.ean ||
                                 el.dataset.productId || el.dataset.id || '';
                    const nameEl  = el.querySelector('[class*="name"],[class*="title"],h2,h3');
                    const priceEl = el.querySelector('[class*="price"]:not([class*="unit"]):not([class*="old"])');
                    const imgEl   = el.querySelector('img');
                    if (code && nameEl && priceEl) {
                        results.push({
                            code:  code,
                            name:  nameEl.innerText.trim(),
                            price: priceEl.innerText.trim(),
                            img:   imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                        });
                    }
                });
                return results;
            }
        """)

        for item in items:
            if item["code"] in ids_vistos:
                continue
            try:
                precio_str = re.sub(r"[^\d.,]", "", item["price"]).replace(",", ".")
                if not precio_str:
                    continue
                precio = float(precio_str)
                if precio <= 0:
                    continue
                ids_vistos.add(item["code"])
                nuevos.append({
                    "Id":           str(item["code"]),
                    "Nombre":       item["name"],
                    "Precio":       precio,
                    "Precio_unidad": "",
                    "Categoria":    categoria,
                    "Supermercado": "Dia",
                    "URL":          f"{BASE_URL}/es/p/{item['code']}",
                    "URL_imagen":   item.get("img", ""),
                })
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"DOM error: {e}")
    return nuevos


def gestion_dia(codigo_postal="28001"):
    """
    Scraper principal de Dia.
    Estrategia doble: descubrimiento de categorías reales + búsqueda por términos.
    """
    import pandas as pd
    inicio = time.time()
    logger.info("Iniciando extracción de Dia con Playwright (modo completo)...")

    todos = []
    ids_vistos = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        page = context.new_page()

        # Fase 1: descubrir URLs reales del menú y navegar categorías
        logger.info("Fase 1: descubriendo categorías reales de Dia...")
        _aceptar_cookies(page)
        urls_cats = _descubrir_urls_categorias(page)

        if urls_cats:
            for url, nombre_cat in urls_cats:
                nuevos = _navegar_categoria(page, url, nombre_cat, ids_vistos)
                todos.extend(nuevos)
                if nuevos:
                    logger.info(f"  {nombre_cat}: {len(nuevos)} productos (total: {len(todos)})")
        else:
            logger.warning("No se encontraron categorías. Pasando directamente a búsqueda por términos.")

        # Fase 2: búsqueda por términos (cubre lo que la navegación no alcanzó)
        logger.info(f"Fase 2: búsqueda por {len(TERMINOS_DIA)} términos...")
        for termino in TERMINOS_DIA:
            nuevos = _buscar_termino(page, termino, ids_vistos)
            todos.extend(nuevos)
            if nuevos:
                logger.info(f"  '{termino}' → {len(nuevos)} nuevos (total: {len(todos)})")
            time.sleep(0.3)

        browser.close()

    duracion = int(time.time() - inicio)
    logger.info(f"Extracción de Dia completada: {len(todos)} productos en {duracion // 60}m {duracion % 60}s")

    if not todos:
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    df = df[df["Precio"] > 0]
    return df
