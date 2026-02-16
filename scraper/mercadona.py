# -*- coding: utf-8 -*-

"""
Scraper de Mercadona.
Utiliza la API interna de tienda.mercadona.es.
No requiere cookies ni autenticación.
"""
import time
import logging
import requests
import pandas as pd


logger = logging.getLogger(__name__)

URL_CATEGORIES = "https://tienda.mercadona.es/api/categories/"
URL_PRODUCTS_BY_CATEGORY = "https://tienda.mercadona.es/api/categories/"

# Pausa entre peticiones para no saturar el servidor (en segundos)
REQUEST_DELAY = 0.01


def gestion_mercadona():
    """
    Función principal que orquesta la extracción de productos de Mercadona.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos de Mercadona.
    """
    tiempo_inicio = time.time()

    logger.info("Iniciando extracción de Mercadona...")
    
    list_categories = get_ids_categorys()
    
    if not list_categories:
        logger.error("No se han podido obtener las categorías de Mercadona.")
        return pd.DataFrame()
    
    logger.info(f"Se han encontrado {len(list_categories)} categorías.")
    
    df_mercadona = get_products_by_category(list_categories)

    tiempo_fin = time.time()
    duracion = tiempo_fin - tiempo_inicio
    minutos = int(duracion // 60)
    segundos = int(duracion % 60)

    logger.info(f"Extracción de Mercadona completada: {len(df_mercadona)} productos en {minutos}m {segundos}s")
    
    return df_mercadona


def get_ids_categorys():
    """
    Obtiene la lista de IDs de todas las categorías de Mercadona.
    
    Returns:
        list: Lista de IDs de categorías (enteros).
    """
    try:
        response = requests.get(URL_CATEGORIES)
        response.raise_for_status()
        data = response.json()

        df = pd.json_normalize(data["results"], sep="_")
        df_categories = pd.json_normalize(
            data["results"], "categories", sep="_", record_prefix="category_"
        )
        df = pd.concat([df, df_categories], axis=1)

        category_ids = df["category_id"].explode().dropna().astype(int).tolist()
        
        return category_ids
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener categorías de Mercadona: {e}")
        return []
    except (KeyError, ValueError) as e:
        logger.error(f"Error al procesar categorías de Mercadona: {e}")
        return []


def get_products_by_category(list_categories):
    """
    Obtiene todos los productos de cada categoría.
    
    Args:
        list_categories (list): Lista de IDs de categorías.
    
    Returns:
        pd.DataFrame: DataFrame con todos los productos.
    """
    df_products = pd.DataFrame()

    for index, id_categoria in enumerate(list_categories):
        logger.info(
            f"{index + 1}/{len(list_categories)} - Categoría {id_categoria}"
        )
        
        url = URL_PRODUCTS_BY_CATEGORY + str(id_categoria)

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            df_productos = pd.json_normalize(data["categories"], "products")

            # Ajustar precios aproximados (productos a granel)
            condicion = df_productos['price_instructions.approx_size']
            df_productos.loc[condicion, 'price_instructions.unit_size'] = 1
            df_productos.loc[condicion, 'price_instructions.unit_price'] = (
                df_productos.loc[condicion, 'price_instructions.bulk_price']
            )

            df_productos['categoria'] = str(id_categoria)
            df_productos['supermercado'] = "Mercadona"

            selected_columns = [
                'id', 'display_name', 'price_instructions.unit_price',
                'price_instructions.bulk_price', 'price_instructions.size_format',
                'categoria', 'supermercado', 'share_url', 'thumbnail'
            ]
            renamed_columns = {
                'id': 'Id',
                'display_name': 'Nombre',
                'price_instructions.unit_price': 'Precio',
                'price_instructions.bulk_price': 'Precio_por_unidad',
                'price_instructions.size_format': 'Formato',
                'categoria': 'Categoria',
                'supermercado': 'Supermercado',
                'share_url': 'Url',
                'thumbnail': 'Url_imagen'
            }

            df_by_category = df_productos[selected_columns].rename(columns=renamed_columns)
            df_products = pd.concat([df_products, df_by_category], ignore_index=True)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error en categoría {id_categoria}: {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"Error procesando categoría {id_categoria}: {e}")

        time.sleep(REQUEST_DELAY)

    return df_products
