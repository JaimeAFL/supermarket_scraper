# -*- coding: utf-8 -*-

"""
Supermarket Price Tracker - Punto de entrada principal.

Ejecuta el scraping de todos los supermercados configurados,
almacena los datos en la base de datos SQLite y genera logs
de cada ejecución.

Uso:
    python main.py
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

from scraper.mercadona import gestion_mercadona
from scraper.carrefour import gestion_carrefour
from scraper.dia import gestion_dia
from scraper.alcampo import gestion_alcampo
from scraper.eroski import gestion_eroski
from scraper.cookie_manager import verificar_todas_las_cookies


def setup_logging():
    """
    Configura el sistema de logging para consola y archivo.
    """
    # Crear carpeta de logs si no existe
    os.makedirs('logs', exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/scraper_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def main():
    """
    Función principal que orquesta todo el proceso de scraping.
    """
    # Cargar variables de entorno
    load_dotenv()

    # Configurar logging
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("SUPERMARKET PRICE TRACKER - Inicio de ejecución")
    logger.info(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Verificar estado de las cookies
    logger.info("")
    logger.info("Verificando cookies...")
    verificar_todas_las_cookies()

    # Crear carpeta de exportación si no existe
    os.makedirs('export', exist_ok=True)

    # DataFrame que acumulará todos los productos
    df_total = pd.DataFrame()

    # --- MERCADONA (no requiere cookies) ---
    logger.info("")
    logger.info("-" * 40)
    logger.info("MERCADONA")
    logger.info("-" * 40)
    df_mercadona = gestion_mercadona()
    if not df_mercadona.empty:
        df_total = pd.concat([df_total, df_mercadona], ignore_index=True)

    # --- CARREFOUR ---
    logger.info("")
    logger.info("-" * 40)
    logger.info("CARREFOUR")
    logger.info("-" * 40)
    df_carrefour = gestion_carrefour()
    if not df_carrefour.empty:
        df_total = pd.concat([df_total, df_carrefour], ignore_index=True)

    # --- DIA ---
    logger.info("")
    logger.info("-" * 40)
    logger.info("DIA")
    logger.info("-" * 40)
    df_dia = gestion_dia()
    if not df_dia.empty:
        df_total = pd.concat([df_total, df_dia], ignore_index=True)

    # --- ALCAMPO (pendiente de implementación) ---
    logger.info("")
    logger.info("-" * 40)
    logger.info("ALCAMPO")
    logger.info("-" * 40)
    df_alcampo = gestion_alcampo()
    if not df_alcampo.empty:
        df_total = pd.concat([df_total, df_alcampo], ignore_index=True)

    # --- EROSKI (pendiente de implementación) ---
    logger.info("")
    logger.info("-" * 40)
    logger.info("EROSKI")
    logger.info("-" * 40)
    df_eroski = gestion_eroski()
    if not df_eroski.empty:
        df_total = pd.concat([df_total, df_eroski], ignore_index=True)

    # --- RESUMEN ---
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMEN DE EXTRACCIÓN")
    logger.info("=" * 60)
    logger.info(f"  Mercadona: {len(df_mercadona)} productos")
    logger.info(f"  Carrefour: {len(df_carrefour)} productos")
    logger.info(f"  Dia:       {len(df_dia)} productos")
    logger.info(f"  Alcampo:   {len(df_alcampo)} productos")
    logger.info(f"  Eroski:    {len(df_eroski)} productos")
    logger.info(f"  TOTAL:     {len(df_total)} productos")
    logger.info("=" * 60)

    # TODO: Aquí irá la integración con la base de datos (database/db_manager.py)
    # Por ahora, exportamos a Excel como hacía el proyecto original
    if not df_total.empty:
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        filepath = f"export/products_{timestamp}.xlsx"
        df_total.to_excel(filepath, sheet_name='Productos', index=False)
        logger.info(f"Datos exportados a: {filepath}")

    logger.info("")
    logger.info("Ejecución finalizada.")


if __name__ == "__main__":
    main()
