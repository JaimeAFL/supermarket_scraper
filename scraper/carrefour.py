# -*- coding: utf-8 -*-

"""
Scraper de Carrefour.
Utiliza la API interna de carrefour.es.
Requiere cookie de sesión configurada en .env (COOKIE_CARREFOUR).
"""

import os
import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

URL_CATEGORIES = "https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu/"
URL_PRODUCTS_BY_CATEGORY = "https://www.carrefour.es/cloud-api/plp-food-papi/v1"

# Productos por página en la API de Carrefour
PRODUCTS_PER_PAGE = 24

# Pausa entre peticiones (en segundos)
REQUEST_DELAY = 1


def _get_headers():
    """
    Construye los headers necesarios para las peticiones a Carrefour.
    
    Returns:
        dict: Headers HTTP con la cookie de sesión.
    """
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'es-GB,es;q=0.9,en-GB;q=0.8,en;q=0.7,es-419;q=0.6',
        'Cookie': os.getenv('COOKIE_CARREFOUR', ''),
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


def gestion_carrefour():
    """
    Función principal que orquesta la extracción de productos de Carrefour.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos de Carrefour.
    """
    if not os.getenv('COOKIE_CARREFOUR') or os.getenv('COOKIE_CARREFOUR') == 'TU_COOKIE_CARREFOUR':
        logger.error("Cookie de Carrefour no configurada. Consulta la guía en docs/guia_env.md")
        return pd.DataFrame()

    tiempo_inicio = time.time()
    
    logger.info("Iniciando extracción de Carrefour...")

    list_categories = get_ids_categorys()
    
    if not list_categories:
        logger.error("No se han podido obtener las categorías de Carrefour. La cookie puede haber caducado.")
        return pd.DataFrame()
    
    logger.info(f"Se han encontrado {len(list_categories)} subcategorías.")
    
    df_carrefour = get_products_by_category(list_categories)

    tiempo_fin = time.time()
    duracion = tiempo_fin - tiempo_inicio
    minutos = int(duracion // 60)
    segundos = int(duracion % 60)

    logger.info(f"Extracción de Carrefour completada: {len(df_carrefour)} productos en {minutos}m {segundos}s")
    
    return df_carrefour


def get_ids_categorys():
    """
    Obtiene las subcategorías de Carrefour navegando el árbol de categorías.
    Carrefour tiene varios niveles de anidación: categorías > subcategorías > sub-subcategorías.
    
    Returns:
        list: Lista de URLs relativas de subcategorías.
    """
    headers = _get_headers()
    
    try:
        response = requests.get(URL_CATEGORIES, headers=headers)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener categorías de Carrefour: {e}")
        return []
    except ValueError as e:
        logger.error(f"Cookie de Carrefour caducada o respuesta inválida: {e}")
        return []

    try:
        df = pd.json_normalize(data["menu"], sep="_")
        df_categories = pd.json_normalize(
            data["menu"], "childs", sep="_", record_prefix="childs_"
        )
        df = pd.concat([df, df_categories], axis=1)

        # Filtrar solo categorías del supermercado, excluyendo ofertas
        filtro = (
            df['childs_url_rel'].str.startswith('/supermercado') & 
            ~df['childs_url_rel'].fillna('').astype(str).str.contains('ofertas')
        )
        df = df[filtro]

        category_ids = df["childs_id"].explode().dropna().astype(str).tolist()

        # Obtener subcategorías de cada categoría
        sub_category_ids = []
        for string_categoria in category_ids:
            url_sub = (
                f"https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu"
                f"?sale_point=005704&depth=1&current_category={string_categoria}"
                f"&limit=3&lang=es&freelink=true"
            )
            
            try:
                response = requests.get(url_sub, headers=headers)
                response.raise_for_status()
                data_sub = response.json()

                df_menu = pd.json_normalize(data_sub, "menu", sep="_")
                df_childs = pd.json_normalize(df_menu["childs"].explode(), sep="_")
                df_childs_deep = pd.json_normalize(df_childs["childs"].explode(), sep="_")
                df_sub_categories = pd.json_normalize(df_childs_deep["childs"].explode(), sep="_")

                sub_category_ids += df_sub_categories["url_rel"].explode().dropna().astype(str).tolist()
                
            except Exception as e:
                logger.warning(f"Error en subcategoría {string_categoria}: {e}")

        return sub_category_ids

    except (KeyError, ValueError) as e:
        logger.error(f"Error procesando categorías de Carrefour: {e}")
        return []


def get_products_by_category(list_categories):
    """
    Obtiene todos los productos de cada subcategoría, gestionando la paginación.
    
    Args:
        list_categories (list): Lista de URLs relativas de subcategorías.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos.
    """
    headers = _get_headers()
    df_products = pd.DataFrame()

    for index, string_categoria in enumerate(list_categories):
        logger.info(
            f"{index + 1}/{len(list_categories)} - Categoría {string_categoria}"
        )
        
        url = URL_PRODUCTS_BY_CATEGORY + str(string_categoria)

        # Paginación: recorrer offsets hasta que se repitan productos
        offset = 0
        while True:
            try:
                url_page = f"{url}?offset={offset}"
                response = requests.get(url_page, headers=headers)
                response.raise_for_status()
                data = response.json()

                df_productos = pd.json_normalize(data["results"], "items")

                df_productos['url'] = 'https://www.carrefour.es' + df_productos['url']
                df_productos['categoria'] = string_categoria
                df_productos['supermercado'] = "Carrefour"

                selected_columns = [
                    'product_id', 'name', 'price', 'price_per_unit',
                    'measure_unit', 'categoria', 'supermercado', 'url', 'images.desktop'
                ]
                renamed_columns = {
                    'product_id': 'Id',
                    'name': 'Nombre',
                    'price': 'Precio',
                    'price_per_unit': 'Precio_por_unidad',
                    'measure_unit': 'Formato',
                    'categoria': 'Categoria',
                    'supermercado': 'Supermercado',
                    'url': 'Url',
                    'images.desktop': 'Url_imagen'
                }

                df_by_category = df_productos[selected_columns].rename(columns=renamed_columns)

                # Verificar si los productos ya existen (fin de paginación)
                first_id = df_by_category.loc[0, 'Id']
                if 'Id' in df_products.columns and first_id in df_products['Id'].values:
                    break

                df_products = pd.concat([df_products, df_by_category], ignore_index=True)
                offset += PRODUCTS_PER_PAGE

            except Exception:
                break

        time.sleep(REQUEST_DELAY)

    return df_products
