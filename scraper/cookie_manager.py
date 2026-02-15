# -*- coding: utf-8 -*-

"""
Gestor automático de cookies para supermercados.

Usa Playwright para abrir un navegador headless, navegar a la web
de cada supermercado, aceptar cookies y capturar la sesión.

Flujo:
    1. Intentar usar cookie del .env / variable de entorno.
    2. Si no existe o ha caducado → obtenerla automáticamente con Playwright.
    3. Inyectar la cookie en os.environ para que los scrapers la usen.

Supermercados soportados:
    - Carrefour (automático)
    - Dia (automático)
    - Mercadona: NO necesita cookie.
    - Alcampo / Eroski: pendiente de implementar scrapers.
"""

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

# Código postal por defecto (Madrid centro). Configurable en .env
CODIGO_POSTAL_DEFAULT = "28001"

# URLs para verificar si una cookie sigue siendo válida
VERIFICATION_URLS = {
    'COOKIE_CARREFOUR': 'https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu/',
    'COOKIE_DIA': (
        'https://www.dia.es/api/v1/plp-insight/initial_analytics/'
        'charcuteria-y-quesos/jamon-cocido-lacon-fiambres-y-mortadela/'
        'c/L2001?navigation=L2001'
    ),
}

# Headers base para verificación
HEADERS_BASE = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-ES,es;q=0.9',
}


# =============================================================================
# VERIFICACIÓN DE COOKIES
# =============================================================================

def verificar_cookie(nombre_cookie):
    """
    Verifica si una cookie de sesión sigue siendo válida.

    Args:
        nombre_cookie (str): Nombre de la variable de entorno.

    Returns:
        bool: True si la cookie funciona.
    """
    cookie_value = os.getenv(nombre_cookie, '')

    if not cookie_value or cookie_value.startswith('TU_COOKIE'):
        return False

    url = VERIFICATION_URLS.get(nombre_cookie)
    if not url:
        return False

    headers = {**HEADERS_BASE, 'Cookie': cookie_value}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        # Carrefour devuelve 'menu', Dia devuelve 'menu_analytics'
        if isinstance(data, dict) and len(data) > 0:
            logger.info(f"{nombre_cookie}: válida.")
            return True
    except Exception:
        pass

    logger.warning(f"{nombre_cookie}: caducada o inválida.")
    return False


# =============================================================================
# OBTENCIÓN AUTOMÁTICA CON PLAYWRIGHT
# =============================================================================

def _cookies_a_string(cookies):
    """Convierte lista de cookies de Playwright a string para header HTTP."""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def _aceptar_cookies_banner(page):
    """
    Intenta aceptar el banner de consentimiento de cookies.
    Prueba múltiples selectores y textos comunes.
    """
    selectores = [
        # Por ID
        '#onetrust-accept-btn-handler',
        '#accept-cookies',
        '#cookie-accept',
        '#acceptCookies',
        '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
        # Por clase
        '.accept-cookies-button',
        '.cookie-accept-button',
        # Por atributo data
        '[data-testid="cookie-accept"]',
        '[data-action="accept"]',
        # Por texto (botones)
        'button:has-text("Aceptar todas")',
        'button:has-text("Aceptar todo")',
        'button:has-text("Aceptar cookies")',
        'button:has-text("Aceptar")',
        'button:has-text("Acepto")',
        'button:has-text("Permitir todas")',
        'button:has-text("Permitir todo")',
        'button:has-text("Entendido")',
        'button:has-text("De acuerdo")',
        'button:has-text("OK")',
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        # Links
        'a:has-text("Aceptar todas")',
        'a:has-text("Aceptar")',
    ]

    for selector in selectores:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=500):
                el.click()
                logger.info(f"Banner de cookies aceptado con selector: {selector}")
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    logger.info("No se encontró banner de cookies (puede que ya estuvieran aceptadas).")
    return False


def obtener_cookie_carrefour(codigo_postal=None):
    """
    Obtiene automáticamente una cookie válida de Carrefour.

    Args:
        codigo_postal (str): Código postal para configurar la tienda.

    Returns:
        str: String de cookie para el header HTTP, o cadena vacía si falla.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Playwright no está instalado. "
            "Ejecuta: pip install playwright && playwright install chromium"
        )
        return ''

    cp = codigo_postal or os.getenv('CODIGO_POSTAL', CODIGO_POSTAL_DEFAULT)

    logger.info(f"Obteniendo cookie de Carrefour (CP: {cp})...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS_BASE['User-Agent'],
                locale='es-ES',
            )
            page = context.new_page()

            # 1. Ir a la home
            page.goto('https://www.carrefour.es', wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            # 2. Aceptar cookies
            _aceptar_cookies_banner(page)
            page.wait_for_timeout(2000)

            # 3. Intentar configurar código postal
            try:
                # Buscar input de código postal o botón de configurar tienda
                selectores_cp = [
                    'input[placeholder*="postal"]',
                    'input[name*="postal"]',
                    'input[name*="zipcode"]',
                    'input[data-testid*="postal"]',
                    '#postal-code-input',
                ]
                for selector in selectores_cp:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=1000):
                            el.fill(cp)
                            page.wait_for_timeout(1000)
                            # Intentar enviar
                            page.keyboard.press('Enter')
                            page.wait_for_timeout(2000)
                            logger.info(f"Código postal {cp} configurado.")
                            break
                    except Exception:
                        continue
            except Exception:
                logger.info("No se pudo configurar código postal (puede no ser necesario).")

            # 4. Navegar al supermercado para generar cookies de sesión completas
            try:
                page.goto(
                    'https://www.carrefour.es/supermercado/',
                    wait_until='domcontentloaded',
                    timeout=30000
                )
                page.wait_for_timeout(3000)
            except Exception:
                logger.warning("No se pudo navegar a /supermercado/")

            # 5. Extraer cookies
            cookies = context.cookies()
            cookie_string = _cookies_a_string(cookies)

            browser.close()

            if cookie_string:
                logger.info(f"Cookie de Carrefour obtenida ({len(cookies)} cookies).")
                return cookie_string
            else:
                logger.warning("No se obtuvieron cookies de Carrefour.")
                return ''

    except Exception as e:
        logger.error(f"Error obteniendo cookie de Carrefour: {e}")
        return ''


def obtener_cookie_dia(codigo_postal=None):
    """
    Obtiene automáticamente una cookie válida de Dia.

    Args:
        codigo_postal (str): Código postal para configurar la zona.

    Returns:
        str: String de cookie para el header HTTP, o cadena vacía si falla.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Playwright no está instalado. "
            "Ejecuta: pip install playwright && playwright install chromium"
        )
        return ''

    cp = codigo_postal or os.getenv('CODIGO_POSTAL', CODIGO_POSTAL_DEFAULT)

    logger.info(f"Obteniendo cookie de Dia (CP: {cp})...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS_BASE['User-Agent'],
                locale='es-ES',
            )
            page = context.new_page()

            # 1. Ir a la home
            page.goto('https://www.dia.es', wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            # 2. Aceptar cookies
            _aceptar_cookies_banner(page)
            page.wait_for_timeout(2000)

            # 3. Intentar configurar código postal / zona de entrega
            try:
                selectores_cp = [
                    'input[placeholder*="postal"]',
                    'input[placeholder*="dirección"]',
                    'input[placeholder*="direccion"]',
                    'input[name*="postal"]',
                    'input[name*="address"]',
                    '#postal-code-input',
                    '[data-testid*="postal"]',
                    '[data-testid*="address"]',
                ]
                for selector in selectores_cp:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=1000):
                            el.fill(cp)
                            page.wait_for_timeout(1500)
                            page.keyboard.press('Enter')
                            page.wait_for_timeout(3000)
                            logger.info(f"Código postal {cp} configurado en Dia.")
                            break
                    except Exception:
                        continue
            except Exception:
                logger.info("No se pudo configurar código postal en Dia.")

            # 4. Navegar a una categoría para generar sesión completa
            try:
                page.goto(
                    'https://www.dia.es/compra-online/',
                    wait_until='domcontentloaded',
                    timeout=30000
                )
                page.wait_for_timeout(3000)
            except Exception:
                logger.warning("No se pudo navegar a /compra-online/")

            # 5. Extraer cookies
            cookies = context.cookies()
            cookie_string = _cookies_a_string(cookies)

            browser.close()

            if cookie_string:
                logger.info(f"Cookie de Dia obtenida ({len(cookies)} cookies).")
                return cookie_string
            else:
                logger.warning("No se obtuvieron cookies de Dia.")
                return ''

    except Exception as e:
        logger.error(f"Error obteniendo cookie de Dia: {e}")
        return ''


# =============================================================================
# FUNCIÓN PRINCIPAL: OBTENER Y CONFIGURAR TODAS LAS COOKIES
# =============================================================================

def obtener_y_configurar_cookies():
    """
    Para cada supermercado que necesita cookie:
    1. Si ya hay una cookie válida en el entorno → la deja.
    2. Si no hay cookie o ha caducado → la obtiene con Playwright.
    3. Inyecta la cookie en os.environ para que los scrapers la usen.

    Returns:
        dict: Estado de cada cookie {nombre: 'manual'|'automatica'|'fallida'}.
    """
    resultados = {}

    configuracion = {
        'COOKIE_CARREFOUR': obtener_cookie_carrefour,
        'COOKIE_DIA': obtener_cookie_dia,
    }

    for nombre_cookie, funcion_obtener in configuracion.items():
        # 1. Comprobar si ya hay cookie válida
        if verificar_cookie(nombre_cookie):
            resultados[nombre_cookie] = 'manual (válida)'
            continue

        # 2. Intentar obtener automáticamente
        logger.info(f"{nombre_cookie}: intentando obtención automática...")
        cookie_nueva = funcion_obtener()

        if cookie_nueva:
            # Inyectar en entorno
            os.environ[nombre_cookie] = cookie_nueva

            # Verificar que funciona
            if verificar_cookie(nombre_cookie):
                resultados[nombre_cookie] = 'automática (OK)'
            else:
                resultados[nombre_cookie] = 'automática (obtenida pero no válida para API)'
        else:
            resultados[nombre_cookie] = 'fallida'

    # Resumen
    logger.info("")
    logger.info("Estado de cookies:")
    for nombre, estado in resultados.items():
        logger.info(f"  {nombre}: {estado}")

    return resultados


def verificar_todas_las_cookies():
    """
    Verificación simple (sin obtención automática).
    Muestra el estado de todas las cookies configuradas.

    Returns:
        dict: {nombre: bool}
    """
    resultados = {}
    cookies_a_verificar = ['COOKIE_CARREFOUR', 'COOKIE_DIA', 'COOKIE_ALCAMPO', 'COOKIE_EROSKI']

    for nombre in cookies_a_verificar:
        resultados[nombre] = verificar_cookie(nombre)

    validas = sum(1 for v in resultados.values() if v)
    total = len(resultados)
    logger.info(f"Cookies válidas: {validas}/{total}")

    for nombre, valida in resultados.items():
        estado = "OK" if valida else "CADUCADA/NO CONFIGURADA"
        logger.info(f"  {nombre}: {estado}")

    return resultados
