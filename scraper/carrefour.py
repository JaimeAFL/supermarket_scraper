# -*- coding: utf-8 -*-

"""
Scraper de Carrefour.
Utiliza la API interna de carrefour.es.
Obtiene cookies automáticamente con Playwright si no están configuradas.
"""

import os
import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

URL_CATEGORIES = "https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu/"
URL_PRODUCTS_BY_CATEGORY = "https://www.carrefour.es/cloud-api/plp-food-papi/v1"

PRODUCTS_PER_PAGE = 24
REQUEST_DELAY = 1


def _get_headers():
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Cookie': os.getenv('COOKIE_CARREFOUR', ''),
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


def _asegurar_cookie():
    """
    Comprueba si hay cookie válida. Si no, la obtiene con Playwright.
    """
    cookie = os.getenv('COOKIE_CARREFOUR', '')
    if cookie and cookie != 'TU_COOKIE_CARREFOUR':
        from scraper.cookie_manager import verificar_cookie
        if verificar_cookie('COOKIE_CARREFOUR'):
            return True

    logger.info("Cookie de Carrefour no disponible. Obteniendo con Playwright...")
    try:
        from scraper.cookie_manager import obtener_cookie_carrefour
        nueva = obtener_cookie_carrefour()
        if nueva:
            os.environ['COOKIE_CARREFOUR'] = nueva
            return True
    except Exception as e:
        logger.error(f"Error obteniendo cookie automática de Carrefour: {e}")
    return False


def gestion_carrefour():
    if not _asegurar_cookie():
        logger.error("No se pudo obtener cookie de Carrefour.")
        return pd.DataFrame()

    tiempo_inicio = time.time()
    logger.info("Iniciando extracción de Carrefour...")

    list_categories = get_ids_categorys()
    if not list_categories:
        logger.error("No se pudieron obtener categorías de Carrefour.")
        return pd.DataFrame()

    logger.info(f"Se han encontrado {len(list_categories)} subcategorías.")
    df_carrefour = get_products_by_category(list_categories)

    duracion = time.time() - tiempo_inicio
    logger.info(f"Carrefour completado: {len(df_carrefour)} productos en {int(duracion//60)}m {int(duracion%60)}s")
    return df_carrefour


def get_ids_categorys():
    headers = _get_headers()
    try:
        response = requests.get(URL_CATEGORIES, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"Error categorías Carrefour: {e}")
        return []

    try:
        df = pd.json_normalize(data["menu"], sep="_")
        df_categories = pd.json_normalize(data["menu"], "childs", sep="_", record_prefix="childs_")
        df = pd.concat([df, df_categories], axis=1)

        filtro = (
            df['childs_url_rel'].str.startswith('/supermercado') &
            ~df['childs_url_rel'].fillna('').astype(str).str.contains('ofertas')
        )
        df = df[filtro]
        category_ids = df["childs_id"].explode().dropna().astype(str).tolist()

        sub_category_ids = []
        for cat_id in category_ids:
            url_sub = (
                f"https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu"
                f"?sale_point=005704&depth=1&current_category={cat_id}&limit=3&lang=es&freelink=true"
            )
            try:
                resp = requests.get(url_sub, headers=headers)
                resp.raise_for_status()
                data_sub = resp.json()

                df_menu = pd.json_normalize(data_sub, "menu", sep="_")
                df_childs = pd.json_normalize(df_menu["childs"].explode(), sep="_")
                df_childs_deep = pd.json_normalize(df_childs["childs"].explode(), sep="_")
                df_sub = pd.json_normalize(df_childs_deep["childs"].explode(), sep="_")
                sub_category_ids += df_sub["url_rel"].explode().dropna().astype(str).tolist()
            except Exception as e:
                logger.warning(f"Error subcategoría {cat_id}: {e}")

        return sub_category_ids
    except Exception as e:
        logger.error(f"Error procesando categorías Carrefour: {e}")
        return []


def get_products_by_category(list_categories):
    headers = _get_headers()
    df_products = pd.DataFrame()

    for index, cat in enumerate(list_categories):
        logger.info(f"{index+1}/{len(list_categories)} - {cat}")
        url = URL_PRODUCTS_BY_CATEGORY + str(cat)

        offset = 0
        while True:
            try:
                resp = requests.get(f"{url}?offset={offset}", headers=headers)
                resp.raise_for_status()
                data = resp.json()

                df_p = pd.json_normalize(data["results"], "items")
                df_p['url'] = 'https://www.carrefour.es' + df_p['url']
                df_p['categoria'] = cat
                df_p['supermercado'] = "Carrefour"

                cols = ['product_id', 'name', 'price', 'price_per_unit',
                        'measure_unit', 'categoria', 'supermercado', 'url', 'images.desktop']
                renames = {
                    'product_id': 'Id', 'name': 'Nombre', 'price': 'Precio',
                    'price_per_unit': 'Precio_por_unidad', 'measure_unit': 'Formato',
                    'categoria': 'Categoria', 'supermercado': 'Supermercado',
                    'url': 'Url', 'images.desktop': 'Url_imagen'
                }

                df_cat = df_p[cols].rename(columns=renames)
                first_id = df_cat.loc[0, 'Id']
                if 'Id' in df_products.columns and first_id in df_products['Id'].values:
                    break

                df_products = pd.concat([df_products, df_cat], ignore_index=True)
                offset += PRODUCTS_PER_PAGE
            except Exception:
                break

        time.sleep(REQUEST_DELAY)

    return df_products
