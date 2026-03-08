# -*- coding: utf-8 -*-

"""
scraper/lidl.py - Scraper para LIDL España

Contexto técnico
----------------
lidl.es NO tiene tienda de supermercado online. Los productos de alimentación
(y del resto de categorías) son artículos del catálogo físico semanal que se
muestran en la web pero no se pueden comprar online.

La web usa una arquitectura de "islas" (Nuxt 3 + fragmentos Vue): el HTML
inicial llega vacío de datos de producto; cuando el JS corre en el navegador,
el fragmento /p/fragment/ hace una llamada XHR a la API interna de Lidl para
cargar la rejilla de productos. Esa llamada NO es accesible vía requests
directos (devuelve HTML vacío o 404 según el path).

Estrategia de extracción
------------------------
Se usa Playwright con interceptación de respuestas de red:

  1. Obtener el árbol de categorías desde la navegación HTML del sitio.
     El endpoint GET https://www.lidl.es/n/es-ES/mobile-navigation devuelve
     HTML con enlaces <a href="/h/{slug}/h{id}">. Se parsean con regex para
     obtener (nombre, slug, id) de cada categoría.

  2. Para cada categoría, navegar con Playwright a:
       https://www.lidl.es/h/{slug}/h{id}
     y registrar un listener de respuestas que capture la llamada XHR que el
     fragmento realiza al endpoint de búsqueda de Lidl. Ese endpoint tiene la
     forma:
       https://www.lidl.es/q/api/search?q=*&categoryId={id}&fetchsize=...
     o similar — el listener lo descubre en tiempo de ejecución y extrae el
     JSON de la respuesta.

  3. Si la interceptación no captura nada (p.ej. la página no tiene productos),
     se hace fallback a la API pública /q/api/search con category={nombre},
     que devuelve los productos online disponibles (subconjunto reducido pero
     válido).

  4. Los campos se mapean al esquema normalizado del proyecto.

Categorías objetivo
-------------------
Se filtran las categorías de alimentación, bebidas, droguería e higiene
(las relevantes para un comparador de supermercado). Las categorías de moda,
deporte, hogar, bricolaje, etc. se descartan.

Cobertura esperada: ~500-2.000 productos (variable según catálogo semanal).
Tiempo estimado: ~10-20 minutos (Playwright, una página por categoría).
"""

import re
import time
import logging

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

BASE_URL        = "https://www.lidl.es"
URL_NAVEGACION  = f"{BASE_URL}/n/es-ES/mobile-navigation"
URL_BUSQUEDA    = f"{BASE_URL}/q/api/search"

HEADERS_BASE = {
    "Accept-Language": "es-ES,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL + "/",
}

HEADERS_API = {
    **HEADERS_BASE,
    "Accept": "application/mindshift.search+json;version=2",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Pausa entre categorías (segundos)
PAUSA_ENTRE_CATEGORIAS = 1.0

# Máximo de productos por petición a la API de fallback
FETCHSIZE_FALLBACK = 1000

# Slugs de URL que identifican categorías de supermercado relevantes
SLUGS_DESEADOS = {
    "alimentacion", "frescos", "lacteos", "lacteos-y-huevos",
    "carnes-y-embutidos", "carnes", "embutidos", "charcuteria",
    "pescado", "pescados", "marisco", "frutas", "verduras",
    "fruta-y-verdura", "congelados",
    "pan", "panaderia", "bolleria", "pasteleria",
    "cereales", "galletas", "aperitivos",
    "conservas", "salsas", "aceite", "aceites", "especias",
    "pasta", "arroz", "legumbres",
    "cafe", "cafe-e-infusiones", "infusiones",
    "chocolate", "dulces", "snacks", "confiteria",
    "platos-preparados", "comida-preparada",
    "queso", "quesos", "productos-lacteos",
    "huevos",
    "bebidas", "agua", "refrescos", "zumos", "cerveza", "vino",
    "bebidas-alcoholicas", "bebidas-sin-alcohol",
    "drogueria", "limpieza", "detergentes", "higiene",
    "higiene-personal", "cuidado-personal",
    "papel-higienico", "papel", "bebe",
    "mascotas", "animales",
}

# Palabras clave en el nombre de categoría para inclusión (minúsculas)
NOMBRES_DESEADOS = {
    "alimentaci", "fresc", "lácteo", "lacteo", "leche", "yogur",
    "queso", "mantequilla", "nata", "huevo",
    "carne", "embutido", "jamón", "jamon", "charcutería", "charcuteria",
    "pescado", "marisco", "fruta", "verdura", "hortaliza",
    "congelado", "pan", "bollería", "bolleria", "pasteler", "cereal",
    "galleta", "aperitivo", "confitería", "confiteria",
    "conserva", "salsa", "aceite", "especia", "mostaza",
    "pasta", "arroz", "legumbre", "café", "cafe", "infusión", "infusion",
    "chocolate", "cacao", "dulce", "snack",
    "plato preparado", "comida preparada",
    "bebida", "agua", "refresco", "zumo", "cerveza", "vino", "licor",
    "droguería", "drogueria", "limpieza", "detergente", "higiene",
    "papel", "bebé", "bebe", "mascota", "animal",
    "delicatessen", "gourmet",
}


# ─── Punto de entrada ────────────────────────────────────────────────────────

def gestion_lidl() -> pd.DataFrame:
    """
    Función principal. Orquesta la extracción del catálogo de LIDL.

    Intenta primero con Playwright (interceptación de red) para obtener el
    catálogo completo. Si Playwright no está disponible, hace fallback a la
    API pública de búsqueda (catálogo online reducido).

    Returns:
        pd.DataFrame con columnas normalizadas del proyecto.
    """
    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de LIDL...")

    categorias = _obtener_categorias()
    if not categorias:
        logger.error("No se han podido obtener las categorías de LIDL.")
        return pd.DataFrame()

    logger.info("Categorías relevantes a procesar: %d", len(categorias))

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        logger.info("Playwright disponible — usando interceptación de red.")
        df = _extraer_con_playwright(categorias)
    except ImportError:
        logger.warning("Playwright no disponible — usando API pública (fallback).")
        df = _extraer_con_api_publica(categorias)

    if df.empty:
        logger.warning("LIDL: 0 productos extraídos.")
        return pd.DataFrame()

    duracion = int(time.time() - tiempo_inicio)
    logger.info(
        "LIDL completado: %d productos en %dm %ds",
        len(df), duracion // 60, duracion % 60,
    )
    return df


# ─── Obtención de categorías ─────────────────────────────────────────────────

def _obtener_categorias() -> list[dict]:
    """
    Descarga el árbol de navegación y extrae las categorías relevantes.

    El endpoint devuelve HTML. Las categorías aparecen como:
        <a href="/h/{slug}/h{id}" ...><span ...>Nombre</span>

    Filtra por slug y nombre para quedarse solo con las categorías de
    alimentación, bebidas, droguería e higiene.

    Returns:
        Lista de dicts con claves: nombre, id, slug, url.
    """
    try:
        resp = requests.get(
            URL_NAVEGACION,
            headers={**HEADERS_BASE, "Accept": "text/html"},
            timeout=15,
        )
        resp.raise_for_status()
        contenido = resp.text
    except requests.exceptions.RequestException as e:
        logger.error("Error descargando árbol de navegación de LIDL: %s", e)
        return []

    # Patrón HTML: href="/h/{slug}/h{id}" ...><span ...>Nombre</span>
    patron = re.compile(
        r'href="/h/([^/\"]+)/h(\d+)"[^>]*>.*?<span[^>]*>\s*([^<]+?)\s*</span>',
        re.DOTALL,
    )
    coincidencias = patron.findall(contenido)

    categorias_vistas = set()
    categorias = []

    for slug, cat_id, nombre in coincidencias:
        nombre = nombre.strip()
        if cat_id in categorias_vistas:
            continue
        if not _es_categoria_deseada(slug, nombre):
            continue
        categorias_vistas.add(cat_id)
        categorias.append({
            "nombre": nombre,
            "id":     cat_id,
            "slug":   slug,
            "url":    f"{BASE_URL}/h/{slug}/h{cat_id}",
        })

    logger.info(
        "Total entradas en navegación: %d → relevantes: %d",
        len(coincidencias), len(categorias),
    )
    return categorias


def _es_categoria_deseada(slug: str, nombre: str) -> bool:
    """
    Devuelve True si la categoría es relevante para el comparador de precios.

    Comprueba el slug contra SLUGS_DESEADOS y el nombre (en minúsculas)
    contra NOMBRES_DESEADOS.
    """
    if slug.lower() in SLUGS_DESEADOS:
        return True
    nombre_lower = nombre.lower()
    return any(kw in nombre_lower for kw in NOMBRES_DESEADOS)


# ─── Extracción con Playwright (método principal) ─────────────────────────────

def _extraer_con_playwright(categorias: list[dict]) -> pd.DataFrame:
    """
    Navega cada categoría con Playwright e intercepta la llamada XHR al API
    interno de Lidl que carga la rejilla de productos.

    Cuando el fragmento /p/fragment/ se carga en el navegador, hace una
    petición GET a un endpoint de búsqueda cuya URL contiene '/q/api/search'
    y devuelve JSON con estructura {'items': [...], 'numFound': N}.
    Esta función captura esa respuesta.

    Si la interceptación no produce resultados para una categoría, intenta
    el fallback a la API pública para esa categoría concreta.

    Returns:
        pd.DataFrame con todos los productos concatenados y deduplicados.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa

    filas = []
    ids_vistos = set()
    total = len(categorias)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            user_agent=HEADERS_BASE["User-Agent"],
            locale="es-ES",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.new_page()

        # Visita inicial para establecer sesión/cookies
        logger.info("Estableciendo sesión en lidl.es...")
        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=20000)
            _aceptar_cookies(page)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning("Error en visita inicial: %s", e)

        for idx, cat in enumerate(categorias, start=1):
            logger.info(
                "[%d/%d] %s (h%s)",
                idx, total, cat["nombre"], cat["id"],
            )

            productos_cat = _extraer_categoria_playwright(page, cat)

            # Fallback a API pública si Playwright no capturó nada
            if not productos_cat:
                logger.debug(
                    "  Sin resultados vía Playwright para '%s' — probando API pública.",
                    cat["nombre"],
                )
                productos_cat = _pedir_api_publica(cat["nombre"], cat["id"])

            nuevos = 0
            for prod in productos_cat:
                erp = prod.get("Id", "")
                if not erp or erp in ids_vistos:
                    continue
                ids_vistos.add(erp)
                filas.append(prod)
                nuevos += 1

            if nuevos:
                logger.debug(
                    "  → %d nuevos (total acumulado: %d)", nuevos, len(filas),
                )

            time.sleep(PAUSA_ENTRE_CATEGORIAS)

        browser.close()

    return pd.DataFrame(filas) if filas else pd.DataFrame()


def _extraer_categoria_playwright(page, cat: dict) -> list[dict]:
    """
    Navega a la URL de categoría y captura la respuesta XHR del fragmento.

    Registra un listener de respuestas antes de navegar. El listener filtra
    las respuestas cuya URL contiene '/q/api/search' y cuyo Content-Type
    incluye 'json' o 'mindshift'. Cuando la detecta, extrae los productos.

    El listener usa una lista mutable para acumular productos porque los
    closures de Python no permiten reasignación de variables externas.

    Args:
        page: instancia de Playwright Page.
        cat:  dict con claves nombre, id, slug, url.

    Returns:
        Lista de dicts de productos mapeados al esquema del proyecto.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    productos_capturados: list[dict] = []
    endpoint_detectado: list[str | None] = [None]

    def _on_response(response):
        url = response.url
        # Solo nos interesan las llamadas a la API de búsqueda de Lidl
        if "/q/api/search" not in url:
            return
        if response.status != 200:
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct and "mindshift" not in ct:
            return

        try:
            datos = response.json()
        except Exception:
            return

        items = datos.get("items", [])
        if not items:
            return

        endpoint_detectado[0] = url
        for item in items:
            if item.get("resultClass") != "product":
                continue
            data = item.get("gridbox", {}).get("data", {})
            if not data:
                continue
            fila = _mapear_producto(data, cat["nombre"])
            if fila:
                productos_capturados.append(fila)

    page.on("response", _on_response)

    try:
        page.goto(cat["url"], wait_until="domcontentloaded", timeout=25000)
        # Esperar a que el fragmento JS dispare la XHR (normalmente ~2-3s)
        page.wait_for_timeout(4000)
        # Scroll para activar lazy loading si lo hubiera
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        page.wait_for_timeout(2000)
    except PWTimeout:
        logger.warning("  Timeout navegando a '%s'", cat["url"])
    except Exception as e:
        logger.warning("  Error en '%s': %s", cat["url"], str(e)[:80])
    finally:
        # Siempre desregistrar el listener para no acumular listeners entre páginas
        page.remove_listener("response", _on_response)

    if endpoint_detectado[0]:
        logger.debug("  XHR capturada: %s", endpoint_detectado[0][:100])

    return productos_capturados


def _aceptar_cookies(page) -> None:
    """Acepta el banner de cookies de Lidl si aparece."""
    selectores = [
        "#onetrust-accept-btn-handler",
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
        '[data-testid="cookie-accept"]',
    ]
    for sel in selectores:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                page.wait_for_timeout(1500)
                return
        except Exception:
            continue


# ─── Extracción con API pública (fallback sin Playwright) ─────────────────────

def _extraer_con_api_publica(categorias: list[dict]) -> pd.DataFrame:
    """
    Fallback cuando Playwright no está disponible.

    Usa el endpoint público /q/api/search para obtener los productos
    disponibles online. Es un subconjunto reducido del catálogo físico,
    pero mejor que nada.

    Returns:
        pd.DataFrame con los productos obtenidos.
    """
    filas = []
    ids_vistos = set()
    total = len(categorias)

    for idx, cat in enumerate(categorias, start=1):
        logger.info(
            "[%d/%d] %s (h%s) — API pública",
            idx, total, cat["nombre"], cat["id"],
        )
        productos = _pedir_api_publica(cat["nombre"], cat["id"])
        for prod in productos:
            erp = prod.get("Id", "")
            if erp and erp not in ids_vistos:
                ids_vistos.add(erp)
                filas.append(prod)

        time.sleep(PAUSA_ENTRE_CATEGORIAS)

    return pd.DataFrame(filas) if filas else pd.DataFrame()


def _pedir_api_publica(nombre_categoria: str, cat_id: str) -> list[dict]:
    """
    Consulta la API pública /q/api/search para una categoría.

    Prueba primero con category={nombre} (funciona para categorías de primer
    nivel como 'Alimentación'). Si no obtiene resultados, prueba con
    categoryId={id} (aunque en la práctica no filtra correctamente).

    Args:
        nombre_categoria: Nombre legible de la categoría.
        cat_id:           ID numérico de la categoría.

    Returns:
        Lista de dicts de productos mapeados al esquema del proyecto.
    """
    intentos = [
        {"q": "*", "category":   nombre_categoria, "fetchsize": FETCHSIZE_FALLBACK,
         "offset": 0, "locale": "es_ES", "assortment": "ES", "version": "2.1.0"},
        {"q": "*", "categoryId": cat_id,           "fetchsize": FETCHSIZE_FALLBACK,
         "offset": 0, "locale": "es_ES", "assortment": "ES", "version": "2.1.0"},
    ]

    for params in intentos:
        try:
            resp = requests.get(
                URL_BUSQUEDA,
                params=params,
                headers=HEADERS_API,
                timeout=20,
            )
            resp.raise_for_status()
            datos = resp.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning("  Error API pública '%s': %s", nombre_categoria, e)
            continue

        items = datos.get("items", [])
        num_total = datos.get("numFound", 0)

        if not items:
            continue

        if num_total and num_total > FETCHSIZE_FALLBACK:
            logger.warning(
                "  '%s': %d productos en API pero fetchsize=%d. "
                "Usa Playwright para el catálogo completo.",
                nombre_categoria, num_total, FETCHSIZE_FALLBACK,
            )

        productos = []
        for item in items:
            if item.get("resultClass") != "product":
                continue
            data = item.get("gridbox", {}).get("data", {})
            if data:
                fila = _mapear_producto(data, nombre_categoria)
                if fila:
                    productos.append(fila)

        if productos:
            return productos

    return []


# ─── Mapeo de campos ──────────────────────────────────────────────────────────

def _mapear_producto(data: dict, categoria_scrapeada: str) -> dict | None:
    """
    Transforma un dict de datos de producto Lidl al esquema del proyecto.

    Los datos provienen de la misma estructura en ambas fuentes:
      - Respuesta XHR interceptada por Playwright (gridbox.data)
      - Respuesta de /q/api/search (gridbox.data)

    Esquema de salida (columnas del DataFrame del proyecto):
        Id, Nombre, Precio, Precio_por_unidad, Formato,
        Categoria, Supermercado, Url, Url_imagen

    Args:
        data:                 Dict con los datos del producto (gridbox.data).
        categoria_scrapeada:  Nombre de la categoría usada en la petición.

    Returns:
        Dict con el esquema normalizado, o None si faltan campos esenciales.
    """
    # ── Campos obligatorios ──────────────────────────────────────────────────
    erp    = str(data.get("erpNumber", "")).strip()
    nombre = (data.get("fullTitle") or data.get("name") or "").strip()
    precio_raw = data.get("price", {}).get("price")

    if not erp or not nombre or precio_raw is None:
        return None

    try:
        precio = float(precio_raw)
    except (TypeError, ValueError):
        return None

    if precio <= 0:
        return None

    # ── Formato / packaging ──────────────────────────────────────────────────
    # Fuente 1: price.packaging.text  →  "1,5 l", "500 g", "6 x 1 l"
    formato = (
        data.get("price", {})
            .get("packaging", {})
            .get("text", "")
        or ""
    ).strip()

    # Fuente 2: keyfacts.description  →  "<ul><li>1,5 l</li></ul>"
    if not formato:
        desc_html = data.get("keyfacts", {}).get("description", "")
        match = re.search(r"<li>([^<]+)</li>", desc_html)
        if match:
            formato = match.group(1).strip()

    # Normalizar separador decimal: "1,5 l" → "1.5 l" para el normalizer
    formato = formato.replace(",", ".")

    # ── Precio por unidad ────────────────────────────────────────────────────
    # packaging.price es el precio por kg/l cuando está disponible
    precio_unitario = None
    pkg_price = data.get("price", {}).get("packaging", {}).get("price")
    if pkg_price is not None:
        try:
            precio_unitario = float(pkg_price)
        except (TypeError, ValueError):
            pass

    # ── Categoría ────────────────────────────────────────────────────────────
    # Preferencia: breadcrumb del producto > data.category > categoría scrapeada
    categoria = categoria_scrapeada
    breadcrumbs = data.get("wonCategoryBreadcrumbs", [])
    if breadcrumbs and len(breadcrumbs[0]) > 1:
        cat_bc = breadcrumbs[0][1].get("name", "")
        if cat_bc:
            categoria = cat_bc
    elif data.get("category"):
        categoria = data["category"]

    # ── URL del producto ──────────────────────────────────────────────────────
    canonical = data.get("canonicalPath") or data.get("canonicalUrl", "")
    if canonical and not canonical.startswith("http"):
        url = BASE_URL + canonical
    else:
        url = canonical or f"{BASE_URL}/p/producto/p{erp}"

    # ── URL de imagen ─────────────────────────────────────────────────────────
    url_imagen = data.get("image", "")
    if isinstance(url_imagen, list) and url_imagen:
        url_imagen = url_imagen[0].get("url", "")

    return {
        "Id":                erp,
        "Nombre":            nombre,
        "Precio":            precio,
        "Precio_por_unidad": precio_unitario,   # normalizer.py lo calculará si es None
        "Formato":           formato,
        "Categoria":         categoria,
        "Supermercado":      "Lidl",
        "Url":               url,
        "Url_imagen":        url_imagen,
    }
