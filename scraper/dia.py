# -*- coding: utf-8 -*-

"""
Scraper de Dia.
Utiliza la API interna de dia.es.
Requiere cookie de sesión configurada en .env (COOKIE_DIA).
"""

import os
import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

URL_CATEGORIES = (
    "https://www.dia.es/api/v1/plp-insight/initial_analytics/"
    "charcuteria-y-quesos/jamon-cocido-lacon-fiambres-y-mortadela/"
    "c/L2001?navigation=L2001"
)
URL_PRODUCTS_BY_CATEGORY = "https://www.dia.es/api/v1/plp-back/reduced"

# Pausa entre peticiones (en segundos)
REQUEST_DELAY = 1


def _get_headers():
    """
    Construye los headers necesarios para las peticiones a Dia.
    
    Returns:
        dict: Headers HTTP con la cookie de sesión.
    """
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'es-GB,es;q=0.9',
        'Cookie': os.getenv('COOKIE_DIA', ''),
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


def gestion_dia():
    """
    Función principal que orquesta la extracción de productos de Dia.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos de Dia.
    """
    if not os.getenv('COOKIE_DIA') or os.getenv('COOKIE_DIA') == 'TU_COOKIE_DIA':
        logger.error("Cookie de Dia no configurada. Consulta la guía en docs/guia_env.md")
        return pd.DataFrame()

    tiempo_inicio = time.time()

    logger.info("Iniciando extracción de Dia...")

    list_categories = get_ids_categorys()
    
    if not list_categories:
        logger.error("No se han podido obtener las categorías de Dia. La cookie puede haber caducado.")
        return pd.DataFrame()
    
    logger.info(f"Se han encontrado {len(list_categories)} categorías.")
    
    df_dia = get_products_by_category(list_categories)

    tiempo_fin = time.time()
    duracion = tiempo_fin - tiempo_inicio
    minutos = int(duracion // 60)
    segundos = int(duracion % 60)

    logger.info(f"Extracción de Dia completada: {len(df_dia)} productos en {minutos}m {segundos}s")
    
    return df_dia


def get_ids_categorys():
    """
    Obtiene la lista de paths de todas las categorías de Dia.
    Navega el árbol de menú recursivamente.
    
    Returns:
        list: Lista de paths de categorías (strings).
    """
    headers = _get_headers()
    
    try:
        response = requests.get(URL_CATEGORIES, headers=headers)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener categorías de Dia: {e}")
        return []
    except ValueError as e:
        logger.error(f"Cookie de Dia caducada o respuesta inválida: {e}")
        return []

    try:
        info = data['menu_analytics']
        nodes = _procesar_nodo(info)
        df = pd.DataFrame(nodes, columns=['id', 'parameter', 'path'])
        df = df[df['parameter'].notna()]

        category_ids = df["path"].explode().dropna().astype(str).tolist()
        return category_ids

    except (KeyError, ValueError) as e:
        logger.error(f"Error procesando categorías de Dia: {e}")
        return []


def _procesar_nodo(nodo, parent_path=""):
    """
    Recorre recursivamente el árbol de categorías de Dia.
    
    Args:
        nodo (dict): Nodo del árbol de categorías.
        parent_path (str): Path acumulado del padre.
    
    Returns:
        list: Lista de tuplas (id, parameter, path).
    """
    data = []
    for key, value in nodo.items():
        path = f"{parent_path}/{key}" if parent_path else key
        parameter = value.get('parameter', None)
        path_list = value.get('path', None)
        data.append((key, parameter, path_list))
        children = value.get('children', {})
        if children:
            data.extend(_procesar_nodo(children, parent_path=path))
        elif 'children' in value:
            data.append(('', None, path))
    return data


def get_products_by_category(list_categories):
    """
    Obtiene todos los productos de cada categoría.
    
    Args:
        list_categories (list): Lista de paths de categorías.
    
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

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            df_productos = pd.json_normalize(data["plp_items"], sep="_")

            df_productos['url'] = 'https://www.dia.es' + df_productos['url']
            df_productos['image'] = 'https://www.dia.es' + df_productos['image']
            df_productos['categoria'] = string_categoria
            df_productos['supermercado'] = "Dia"

            selected_columns = [
                'object_id', 'display_name', 'prices_price',
                'prices_price_per_unit', 'prices_measure_unit',
                'categoria', 'supermercado', 'url', 'image'
            ]
            renamed_columns = {
                'object_id': 'Id',
                'display_name': 'Nombre',
                'prices_price': 'Precio',
                'prices_price_per_unit': 'Precio_por_unidad',
                'prices_measure_unit': 'Formato',
                'categoria': 'Categoria',
                'supermercado': 'Supermercado',
                'url': 'Url',
                'image': 'Url_imagen'
            }

            df_by_category = df_productos[selected_columns].rename(columns=renamed_columns)
            df_products = pd.concat([df_products, df_by_category], ignore_index=True)

        except Exception as e:
            logger.warning(f"Error en categoría {string_categoria}: {e}")

        time.sleep(REQUEST_DELAY)

    return df_products
