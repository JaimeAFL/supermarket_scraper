"""
scraper/dia.py - Scraper para Dia

Usa la API REST interna de Dia (misma que usa su web):
  - /api/v1/plp-insight/initial_analytics/... → árbol de categorías
  - /api/v1/plp-back/reduced/...              → productos por categoría

Requiere cookie de sesión (gestionada por cookie_manager).
"""

import os
import logging
import time
import requests
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

URL_CATEGORY_DIA = (
    "https://www.dia.es/api/v1/plp-insight/initial_analytics/"
    "charcuteria-y-quesos/jamon-cocido-lacon-fiambres-y-mortadela/c/L2001"
    "?navigation=L2001"
)
URL_PRODUCTS_BY_CATEGORY_DIA = "https://www.dia.es/api/v1/plp-back/reduced"

HEADERS_REQUEST_DIA = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
}


def gestion_dia():
    """Punto de entrada principal. Devuelve un DataFrame con todos los productos."""
    load_dotenv()

    cookie = os.getenv('COOKIE_DIA', '')
    if not cookie:
        logger.error("No se encontró COOKIE_DIA. Abortando scraper de Dia.")
        return pd.DataFrame()

    HEADERS_REQUEST_DIA['Cookie'] = cookie

    # Validar cookie antes de empezar
    if not _validar_cookie():
        logger.error("La cookie de Dia no es válida o ha caducado.")
        return pd.DataFrame()

    inicio = time.time()
    logger.info("Iniciando extracción de Dia...")

    # Obtener árbol de categorías
    list_categories = _get_ids_categorys()
    if not list_categories:
        logger.error("No se pudieron obtener categorías de Dia.")
        return pd.DataFrame()

    logger.info(f"Se han encontrado {len(list_categories)} categorías.")

    # Obtener productos de cada categoría
    df_products = _get_products_by_category(list_categories)

    duracion = int(time.time() - inicio)
    logger.info(
        f"Dia completado: {len(df_products)} productos "
        f"en {duracion // 60}m {duracion % 60}s"
    )

    return df_products


def _validar_cookie():
    """Comprueba que la cookie funcione haciendo una petición de prueba."""
    try:
        test_url = (
            URL_PRODUCTS_BY_CATEGORY_DIA
            + "/charcuteria-y-quesos/jamon-cocido-pavo-y-pollo/c/L2001"
        )
        resp = requests.get(test_url, headers=HEADERS_REQUEST_DIA, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "plp_items" in data:
                return True
        logger.warning(f"Cookie test: status {resp.status_code}")
        return False
    except Exception as e:
        logger.warning(f"Cookie test error: {e}")
        return False


def _get_ids_categorys():
    """Obtiene la lista de paths de categorías desde el árbol de navegación."""
    try:
        resp = requests.get(URL_CATEGORY_DIA, headers=HEADERS_REQUEST_DIA, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Error obteniendo categorías de Dia: {e}")
        return []

    info = data.get('menu_analytics', {})
    if not info:
        logger.error("No se encontró 'menu_analytics' en la respuesta.")
        return []

    # Extraer todos los paths del árbol recursivo
    nodos = _procesar_nodo(info)
    df = pd.DataFrame(nodos, columns=['id', 'parameter', 'path'])
    df = df[df['parameter'].notna()]

    category_paths = df['path'].explode().dropna().astype(str).tolist()

    return category_paths


def _procesar_nodo(nodo, parent_path=""):
    """Recorre recursivamente el árbol de categorías de Dia."""
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


def _get_products_by_category(list_categories):
    """Itera todas las categorías y obtiene los productos via API."""
    all_products = pd.DataFrame()

    for index, cat_path in enumerate(list_categories):
        logger.info(f"{index + 1}/{len(list_categories)} - {cat_path}")

        url = URL_PRODUCTS_BY_CATEGORY_DIA + str(cat_path)

        try:
            resp = requests.get(url, headers=HEADERS_REQUEST_DIA, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                logger.warning(f"Error en categoría {cat_path}: {e}")
            else:
                logger.error(f"Error HTTP en categoría {cat_path}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error en categoría {cat_path}: {e}")
            continue

        try:
            items = data.get("plp_items", [])
            if not items:
                continue

            df_cat = pd.json_normalize(items, sep="_")

            # Construir URLs completas
            if 'url' in df_cat.columns:
                df_cat['url'] = 'https://www.dia.es' + df_cat['url'].astype(str)
            if 'image' in df_cat.columns:
                df_cat['image'] = 'https://www.dia.es' + df_cat['image'].astype(str)

            df_cat['categoria'] = cat_path
            df_cat['supermercado'] = "Dia"

            # Mapear columnas al esquema estándar (debe coincidir con
            # lo que espera DatabaseManager.guardar_productos)
            col_map = {
                'object_id': 'Id',
                'display_name': 'Nombre',
                'prices_price': 'Precio',
                'prices_price_per_unit': 'Precio_unidad',
                'prices_measure_unit': 'Formato',
                'categoria': 'Categoria',
                'supermercado': 'Supermercado',
                'url': 'URL',
                'image': 'URL_imagen',
            }

            # Solo usar columnas que existan
            available = [c for c in col_map if c in df_cat.columns]
            df_selected = df_cat[available].rename(
                columns={k: col_map[k] for k in available}
            )

            all_products = pd.concat(
                [all_products, df_selected], ignore_index=True
            )

        except Exception as e:
            logger.warning(f"Error parseando productos de {cat_path}: {e}")

    return all_products
