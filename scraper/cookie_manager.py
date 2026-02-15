# -*- coding: utf-8 -*-

"""
Gestor de cookies para supermercados que requieren autenticación.

Este módulo proporciona funciones para:
- Verificar si las cookies actuales siguen siendo válidas.
- (Opcional) Automatizar la obtención de cookies con Selenium/Playwright.

Supermercados que requieren cookies:
- Carrefour: COOKIE_CARREFOUR
- Dia: COOKIE_DIA
- Alcampo: COOKIE_ALCAMPO
- Eroski: COOKIE_EROSKI

Supermercados que NO requieren cookies:
- Mercadona: API pública sin autenticación.

Para obtener las cookies manualmente:
1. Abre la web del supermercado en el navegador.
2. Pulsa F12 → Red → Filtrar por Fetch/XHR.
3. Haz una petición (recarga la página o navega).
4. Haz clic en la petición y busca "Cookie" en los encabezados de solicitud.
5. Copia el valor completo y pégalo en el archivo .env.

Para más detalles, consulta docs/guia_env.md
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

# URLs de verificación: si responden correctamente, la cookie es válida
VERIFICATION_URLS = {
    'COOKIE_CARREFOUR': 'https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu/',
    'COOKIE_DIA': (
        'https://www.dia.es/api/v1/plp-insight/initial_analytics/'
        'charcuteria-y-quesos/jamon-cocido-lacon-fiambres-y-mortadela/'
        'c/L2001?navigation=L2001'
    ),
}


def verificar_cookie(nombre_cookie):
    """
    Verifica si una cookie de sesión sigue siendo válida.
    
    Args:
        nombre_cookie (str): Nombre de la variable de entorno (ej: 'COOKIE_CARREFOUR').
    
    Returns:
        bool: True si la cookie es válida, False si ha caducado o no está configurada.
    """
    cookie_value = os.getenv(nombre_cookie, '')
    
    if not cookie_value or cookie_value.startswith('TU_COOKIE'):
        logger.warning(f"{nombre_cookie} no está configurada.")
        return False

    url = VERIFICATION_URLS.get(nombre_cookie)
    if not url:
        logger.warning(f"No hay URL de verificación para {nombre_cookie}.")
        return False

    headers = {
        'Cookie': cookie_value,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.json()  # Si devuelve JSON válido, la cookie funciona
        logger.info(f"{nombre_cookie} es válida.")
        return True
    except Exception:
        logger.warning(f"{nombre_cookie} ha caducado o es inválida.")
        return False


def verificar_todas_las_cookies():
    """
    Verifica todas las cookies configuradas y muestra un resumen.
    
    Returns:
        dict: Diccionario con el estado de cada cookie {nombre: bool}.
    """
    resultados = {}
    
    cookies_a_verificar = ['COOKIE_CARREFOUR', 'COOKIE_DIA', 'COOKIE_ALCAMPO', 'COOKIE_EROSKI']
    
    for nombre in cookies_a_verificar:
        resultados[nombre] = verificar_cookie(nombre)
    
    # Resumen
    validas = sum(1 for v in resultados.values() if v)
    total = len(resultados)
    logger.info(f"Cookies válidas: {validas}/{total}")
    
    for nombre, valida in resultados.items():
        estado = "OK" if valida else "CADUCADA/NO CONFIGURADA"
        logger.info(f"  {nombre}: {estado}")
    
    return resultados
