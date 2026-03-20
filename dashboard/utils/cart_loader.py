# -*- coding: utf-8 -*-
"""
dashboard/utils/cart_loader.py

Automatiza la carga de productos en el carrito online de Carrefour o Alcampo
mediante Playwright en modo visible (headed). El navegador queda abierto para
que el usuario complete el pedido con sus datos.

Uso como subprocess desde 4_Cesta.py:
    python dashboard/utils/cart_loader.py --supermercado carrefour --archivo /tmp/prods.json
"""

import sys
import json
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Selectores para botón "Añadir al carrito" ─────────────────────────────────
_SEL_CARREFOUR = [
    'button[data-testid="add-to-cart"]',
    'button[data-action="add-to-cart"]',
    'button.add-to-cart-button',
    'button.js-product-detail-add-to-cart',
    'button[class*="AddToCart"]',
    'button[class*="add-to-cart"]',
    'button[aria-label*="Añadir al carrito"]',
    'button:has-text("Añadir al carrito")',
    'button:has-text("Añadir")',
]

_SEL_ALCAMPO = [
    'button[data-testid="add-item"]',
    'button[data-testid="add-to-order"]',
    '[class*="AddToOrder"] button',
    '[class*="add-to-order"] button',
    'button[aria-label*="Añadir al carro"]',
    'button[aria-label*="Añadir"]',
    'button:has-text("Añadir al carro")',
    'button:has-text("Añadir")',
]

# ── URLs de carrito ────────────────────────────────────────────────────────────
_CART_URL_CARREFOUR = "https://www.carrefour.es/cart"
_CART_URL_ALCAMPO   = "https://www.compraonline.alcampo.es/checkout/trolley"
_HOME_CARREFOUR     = "https://www.carrefour.es/supermercado/"
_HOME_ALCAMPO       = "https://www.compraonline.alcampo.es/"


def _aceptar_cookies(page):
    for sel in [
        "#onetrust-accept-btn-handler",
        'button:has-text("Aceptar todas las cookies")',
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar")',
        'button[class*="accept-all"]',
        'button[id*="accept"]',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2500):
                el.click()
                page.wait_for_timeout(1500)
                return
        except Exception:
            continue


def _click_add(page, selectors, timeout=4000):
    """Intenta hacer clic en el botón de añadir con varios selectores."""
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=timeout):
                btn.click()
                page.wait_for_timeout(800)
                return True
        except Exception:
            continue
    return False


def _esperar_cierre(page):
    """Bloquea hasta que el usuario cierra la pestaña/navegador."""
    try:
        while not page.is_closed():
            time.sleep(1)
    except Exception:
        pass


def cargar_carrefour(productos):
    """
    Abre un navegador visible, acepta cookies, navega a cada URL de producto
    y hace clic en 'Añadir al carrito'. Al terminar navega al carrito.

    productos: list[dict] con claves 'nombre', 'cantidad', 'url', 'id_externo'
    """
    from playwright.sync_api import sync_playwright

    validos = [p for p in productos if p.get("url", "").startswith("http")]
    if not validos:
        logger.error("Carrefour: ningún producto tiene URL válida.")
        return

    logger.info(f"Carrefour: cargando {len(validos)} producto(s) en el carrito...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="es-ES",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = ctx.new_page()

        # Visita inicial para aceptar cookies
        logger.info("  Abriendo carrefour.es y aceptando cookies...")
        try:
            page.goto(_HOME_CARREFOUR, wait_until="domcontentloaded", timeout=30000)
            _aceptar_cookies(page)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"  Aviso en visita inicial: {e}")

        ok = 0
        fallo = 0
        for prod in validos:
            nombre   = prod.get("nombre", "?")
            cantidad = max(1, int(prod.get("cantidad", 1)))
            url      = prod["url"]

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1200)

                added = False
                for _ in range(cantidad):
                    if _click_add(page, _SEL_CARREFOUR):
                        added = True
                    else:
                        break

                if added:
                    logger.info(f"  [OK] {nombre} x{cantidad}")
                    ok += 1
                else:
                    logger.warning(f"  [FALLO] {nombre}: botón no encontrado")
                    fallo += 1

            except Exception as e:
                logger.error(f"  [ERROR] {nombre}: {e}")
                fallo += 1

        # Navegar al carrito
        logger.info(f"\nCarrefour: {ok} añadidos, {fallo} fallidos.")
        logger.info("Abriendo tu carrito... Completa el pedido en el navegador.")
        try:
            page.goto(_CART_URL_CARREFOUR, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

        _esperar_cierre(page)
        browser.close()


def cargar_alcampo(productos):
    """
    Igual que cargar_carrefour pero para compraonline.alcampo.es.
    Si no hay URL almacenada la reconstruye desde id_externo.
    """
    from playwright.sync_api import sync_playwright

    base = "https://www.compraonline.alcampo.es/products/"
    for p in productos:
        if not p.get("url", "").startswith("http"):
            id_ext = p.get("id_externo", "")
            if id_ext:
                p["url"] = base + id_ext

    validos = [p for p in productos if p.get("url", "").startswith("http")]
    if not validos:
        logger.error("Alcampo: ningún producto tiene URL válida.")
        return

    logger.info(f"Alcampo: cargando {len(validos)} producto(s) en el carrito...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="es-ES",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = ctx.new_page()

        logger.info("  Abriendo compraonline.alcampo.es y aceptando cookies...")
        try:
            page.goto(_HOME_ALCAMPO, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            _aceptar_cookies(page)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"  Aviso en visita inicial: {e}")

        ok = 0
        fallo = 0
        for prod in validos:
            nombre   = prod.get("nombre", "?")
            cantidad = max(1, int(prod.get("cantidad", 1)))
            url      = prod["url"]

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1500)

                added = False
                for _ in range(cantidad):
                    if _click_add(page, _SEL_ALCAMPO):
                        added = True
                    else:
                        break

                if added:
                    logger.info(f"  [OK] {nombre} x{cantidad}")
                    ok += 1
                else:
                    logger.warning(f"  [FALLO] {nombre}: botón no encontrado")
                    fallo += 1

            except Exception as e:
                logger.error(f"  [ERROR] {nombre}: {e}")
                fallo += 1

        logger.info(f"\nAlcampo: {ok} añadidos, {fallo} fallidos.")
        logger.info("Abriendo tu carrito... Completa el pedido en el navegador.")
        try:
            page.goto(_CART_URL_ALCAMPO, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

        _esperar_cierre(page)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--supermercado", required=True,
                        choices=["carrefour", "alcampo"])
    parser.add_argument("--archivo", required=True,
                        help="Ruta al JSON temporal con la lista de productos")
    args = parser.parse_args()

    try:
        with open(args.archivo, encoding="utf-8") as f:
            productos = json.load(f)
    except Exception as e:
        logger.error(f"No se pudo leer {args.archivo}: {e}")
        sys.exit(1)

    if args.supermercado == "carrefour":
        cargar_carrefour(productos)
    else:
        cargar_alcampo(productos)
