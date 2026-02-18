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
import subprocess
import logging
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

from scraper.mercadona import gestion_mercadona
from scraper.carrefour import gestion_carrefour
from scraper.dia import gestion_dia
from scraper.alcampo import gestion_alcampo
from scraper.eroski import gestion_eroski
from database.init_db import inicializar_base_datos
from database.database_db_manager import DatabaseManager


def setup_logging():
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


def _asegurar_playwright(logger):
    """
    Verifica que Playwright esté instalado. Si no, intenta instalarlo.
    """
    try:
        from playwright.sync_api import sync_playwright
        logger.info("Playwright disponible.")
        return True
    except ImportError:
        logger.info("Playwright no encontrado. Instalando...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'playwright', '-q'])
            subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'])
            logger.info("Playwright instalado correctamente.")
            return True
        except Exception as e:
            logger.warning("No se pudo instalar Playwright: %s", e)
            logger.warning("Carrefour, Dia, Alcampo y Eroski no estarán disponibles.")
            return False


def main():
    # Cargar variables de entorno
    load_dotenv()

    # Configurar logging
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("SUPERMARKET PRICE TRACKER - Inicio de ejecución")
    logger.info("Fecha: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # Inicializar base de datos
    inicializar_base_datos()
    db = DatabaseManager()

    # Asegurar que Playwright está disponible
    _asegurar_playwright(logger)

    # Obtener cookie automática para Dia (único super que la necesita vía requests)
    # Carrefour, Alcampo y Eroski usan Playwright directo (no necesitan cookies manuales)
    logger.info("")
    logger.info("Configurando cookies automáticas...")
    try:
        from scraper.cookie_manager import obtener_y_configurar_cookies
        estado_cookies = obtener_y_configurar_cookies()
        for nombre, estado in estado_cookies.items():
            logger.info("  %s: %s", nombre, estado)
    except Exception as e:
        logger.warning("Error configurando cookies: %s", e)

    # Carpeta de exportación
    os.makedirs('export', exist_ok=True)

    # Scrapers a ejecutar
    resultados = {}
    scrapers = [
        ("Mercadona", gestion_mercadona),
        ("Carrefour", gestion_carrefour),
        ("Dia", gestion_dia),
        ("Alcampo", gestion_alcampo),
        ("Eroski", gestion_eroski),
    ]

    df_total = pd.DataFrame()

    for nombre, funcion_scraper in scrapers:
        logger.info("")
        logger.info("-" * 40)
        logger.info(nombre.upper())
        logger.info("-" * 40)

        try:
            df = funcion_scraper()
        except Exception as e:
            logger.error("Error ejecutando scraper de %s: %s", nombre, e)
            df = pd.DataFrame()

        resultados[nombre] = len(df)

        if not df.empty:
            df_total = pd.concat([df_total, df], ignore_index=True)
            try:
                resumen = db.guardar_productos(df)
                logger.info(
                    f"DB: {resumen['productos_nuevos']} nuevos, "
                    f"{resumen['productos_actualizados']} actualizados, "
                    f"{resumen['precios_registrados']} precios."
                )
            except Exception as e:
                logger.error("Error guardando %s en DB: %s", nombre, e)

    # Deduplicar: mismo producto en varias categorías
    if not df_total.empty:
        antes = len(df_total)
        df_total = df_total.drop_duplicates(
            subset=["Id", "Supermercado"], keep="first"
        )
        eliminados = antes - len(df_total)
        if eliminados > 0:
            logger.info(
                "Deduplicación: %d duplicados eliminados (%d → %d)",
                eliminados, antes, len(df_total),
            )

    # Resumen
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMEN DE EXTRACCIÓN")
    logger.info("=" * 60)
    for nombre, cantidad in resultados.items():
        logger.info("  %-12s: %d productos", nombre, cantidad)
    logger.info("  %-12s: %d productos (tras dedup)", "TOTAL", len(df_total))
    logger.info("=" * 60)

    # Estadísticas DB
    try:
        stats = db.obtener_estadisticas()
        logger.info("")
        logger.info("ESTADO DE LA BASE DE DATOS")
        logger.info("  Productos totales:    %s", stats["total_productos"])
        logger.info("  Registros de precios: %s", stats["total_registros_precios"])
        logger.info("  Supermercados:        %s", stats["total_supermercados"])
        logger.info("  Primera captura:      %s", stats["primera_captura"])
        logger.info("  Última captura:       %s", stats["ultima_captura"])
    except Exception as e:
        logger.warning("No se pudieron obtener estadísticas: %s", e)

    # Exportar a Excel (backup)
    if not df_total.empty:
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        filepath = f"export/products_{timestamp}.xlsx"
        df_total.to_excel(filepath, sheet_name='Productos', index=False)
        logger.info("Datos exportados a: %s", filepath)

    db.cerrar()
    logger.info("")
    logger.info("Ejecución finalizada.")


if __name__ == "__main__":
    main()
