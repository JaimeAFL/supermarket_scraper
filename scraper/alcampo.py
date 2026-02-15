# -*- coding: utf-8 -*-

"""
Scraper de Alcampo.
Utiliza la API interna de compraonline.alcampo.es.
Requiere cookie de sesión configurada en .env (COOKIE_ALCAMPO).

TODO: Investigar la API de Alcampo:
    1. Abrir https://www.compraonline.alcampo.es/ 
    2. F12 → Red → Filtrar por Fetch/XHR
    3. Navegar por categorías y productos
    4. Identificar los endpoints de categorías y productos
    5. Documentar la estructura de los JSON de respuesta
    6. Implementar las funciones de extracción
"""

import os
import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

# TODO: Reemplazar con los endpoints reales una vez investigados
URL_CATEGORIES = ""
URL_PRODUCTS_BY_CATEGORY = ""

REQUEST_DELAY = 1


def _get_headers():
    """
    Construye los headers necesarios para las peticiones a Alcampo.
    
    Returns:
        dict: Headers HTTP con la cookie de sesión.
    """
    return {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Cookie': os.getenv('COOKIE_ALCAMPO', ''),
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


def gestion_alcampo():
    """
    Función principal que orquesta la extracción de productos de Alcampo.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos de Alcampo.
    """
    logger.warning("Scraper de Alcampo pendiente de implementación.")
    logger.warning("Consulta los TODOs en scraper/alcampo.py para instrucciones.")
    return pd.DataFrame()


def get_ids_categorys():
    """
    TODO: Obtiene la lista de IDs de todas las categorías de Alcampo.
    
    Returns:
        list: Lista de IDs de categorías.
    """
    # TODO: Implementar una vez investigada la API
    return []


def get_products_by_category(list_categories):
    """
    TODO: Obtiene todos los productos de cada categoría.
    
    Args:
        list_categories (list): Lista de IDs de categorías.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos.
    """
    # TODO: Implementar siguiendo el mismo patrón que mercadona.py / carrefour.py
    # El DataFrame debe tener las columnas:
    # Id, Nombre, Precio, Precio_por_unidad, Formato, Categoria, Supermercado, Url, Url_imagen
    return pd.DataFrame()
