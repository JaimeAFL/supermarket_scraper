# -*- coding: utf-8 -*-

"""
Scraper de Dia.
Utiliza la API interna de dia.es.
Obtiene cookies automáticamente con Playwright si no están configuradas.
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

REQUEST_DELAY = 1


def _get_headers():
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Cookie': os.getenv('COOKIE_DIA', ''),
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


def _asegurar_cookie():
    """
    Comprueba si hay cookie válida. Si no, la obtiene con Playwright.
    """
    cookie = os.getenv('COOKIE_DIA', '')
    if cookie and cookie != 'TU_COOKIE_DIA':
        from scraper.cookie_manager import verificar_cookie
        if verificar_cookie('COOKIE_DIA'):
            return True

    logger.info("Cookie de Dia no disponible. Obteniendo con Playwright...")
    try:
        from scraper.cookie_manager import obtener_cookie_dia
        nueva = obtener_cookie_dia()
        if nueva:
            os.environ['COOKIE_DIA'] = nueva
            return True
    except Exception as e:
        logger.error(f"Error obteniendo cookie automática de Dia: {e}")
    return False


def gestion_dia():
    if not _asegurar_cookie():
        logger.error("No se pudo obtener cookie de Dia.")
        return pd.DataFrame()

    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Dia...")

    list_categories = get_ids_categorys()
    if not list_categories:
        logger.error("No se pudieron obtener categorías de Dia.")
        return pd.DataFrame()

    logger.info(f"Se han encontrado {len(list_categories)} categorías.")
    df_dia = get_products_by_category(list_categories)

    duracion = time.time() - tiempo_inicio
    logger.info(f"Dia completado: {len(df_dia)} productos en {int(duracion//60)}m {int(duracion%60)}s")
    return df_dia


def get_ids_categorys():
    headers = _get_headers()
    try:
        response = requests.get(URL_CATEGORIES, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"Error categorías Dia: {e}")
        return []

    try:
        info = data['menu_analytics']
        nodes = _procesar_nodo(info)
        df = pd.DataFrame(nodes, columns=['id', 'parameter', 'path'])
        df = df[df['parameter'].notna()]
        return df["path"].explode().dropna().astype(str).tolist()
    except Exception as e:
        logger.error(f"Error procesando categorías Dia: {e}")
        return []


def _procesar_nodo(nodo, parent_path=""):
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
    headers = _get_headers()
    df_products = pd.DataFrame()

    for index, cat in enumerate(list_categories):
        logger.info(f"{index+1}/{len(list_categories)} - {cat}")
        url = URL_PRODUCTS_BY_CATEGORY + str(cat)

        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            df_p = pd.json_normalize(data["plp_items"], sep="_")
            df_p['url'] = 'https://www.dia.es' + df_p['url']
            df_p['image'] = 'https://www.dia.es' + df_p['image']
            df_p['categoria'] = cat
            df_p['supermercado'] = "Dia"

            cols = ['object_id', 'display_name', 'prices_price',
                    'prices_price_per_unit', 'prices_measure_unit',
                    'categoria', 'supermercado', 'url', 'image']
            renames = {
                'object_id': 'Id', 'display_name': 'Nombre',
                'prices_price': 'Precio', 'prices_price_per_unit': 'Precio_por_unidad',
                'prices_measure_unit': 'Formato', 'categoria': 'Categoria',
                'supermercado': 'Supermercado', 'url': 'Url', 'image': 'Url_imagen'
            }

            df_cat = df_p[cols].rename(columns=renames)
            df_products = pd.concat([df_products, df_cat], ignore_index=True)
        except Exception as e:
            logger.warning(f"Error en categoría {cat}: {e}")

        time.sleep(REQUEST_DELAY)

    return df_products
