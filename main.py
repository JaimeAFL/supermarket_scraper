# -*- coding: utf-8 -*-

"""
Supermarket Price Tracker - Punto de entrada principal.

Ejecuta el scraping de todos los supermercados configurados,
almacena los datos en la base de datos SQLite y genera logs
de cada ejecución.

Incluye gestión de memoria para entornos con RAM limitada
(Codespaces, Docker, CI/CD).

Uso:
    python main.py
"""

import os
import sys
import gc
import subprocess
import signal
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv
import pandas as pd

# Forzar PROJECT_ROOT basado en la ubicación REAL de este archivo
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scraper.mercadona import gestion_mercadona
from scraper.carrefour import gestion_carrefour
from scraper.dia import gestion_dia
from scraper.alcampo import gestion_alcampo
from scraper.eroski import gestion_eroski
from database.init_db import inicializar_base_datos
from database.database_db_manager import DatabaseManager


SCRAPER_TIMEOUTS = {
    "Mercadona": int(os.getenv("TIMEOUT_MERCADONA_MIN", "15")) * 60,
    "Carrefour": int(os.getenv("TIMEOUT_CARREFOUR_MIN", "40")) * 60,
    "Dia": int(os.getenv("TIMEOUT_DIA_MIN", "20")) * 60,
    "Alcampo": int(os.getenv("TIMEOUT_ALCAMPO_MIN", "45")) * 60,
    "Eroski": int(os.getenv("TIMEOUT_EROSKI_MIN", "110")) * 60,
}


def _run_scraper_function(funcion_scraper):
    """Ejecutor aislado para poder aplicar timeout por scraper."""
    return funcion_scraper()


def _ejecutar_scraper_con_timeout(nombre, funcion_scraper, logger):
    """Ejecuta un scraper en proceso aislado con timeout duro."""
    timeout = SCRAPER_TIMEOUTS.get(nombre, 3600)
    inicio = datetime.now()
    logger.info("Timeout de %s: %d min", nombre, timeout // 60)

    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_scraper_function, funcion_scraper)
        try:
            df = future.result(timeout=timeout)
            dur = (datetime.now() - inicio).total_seconds()
            logger.info(
                "%s finalizado en %dm %ds", nombre,
                int(dur // 60), int(dur % 60)
            )
            return df
        except FuturesTimeoutError:
            logger.error(
                "%s excedió el timeout de %d min y se ha abortado.",
                nombre, timeout // 60,
            )
            future.cancel()
            return pd.DataFrame()
        except Exception as e:
            logger.error("Error ejecutando scraper de %s: %s", nombre, e)
            return pd.DataFrame()


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
    """Verifica que Playwright esté instalado."""
    try:
        from playwright.sync_api import sync_playwright
        logger.info("Playwright disponible.")
        return True
    except ImportError:
        logger.info("Playwright no encontrado. Instalando...")
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'playwright', '-q'])
            subprocess.check_call(
                [sys.executable, '-m', 'playwright', 'install', 'chromium'])
            logger.info("Playwright instalado correctamente.")
            return True
        except Exception as e:
            logger.warning("No se pudo instalar Playwright: %s", e)
            return False


def _matar_chromium_huerfano(logger):
    """Mata todos los procesos de Chromium/Chrome que hayan quedado huérfanos.

    Esto es crítico en entornos con RAM limitada: si un scraper crashea
    sin cerrar el browser, los procesos de Chromium siguen consumiendo
    memoria y el siguiente scraper no puede arrancar.
    """
    try:
        # Linux (Codespaces, Docker, CI)
        resultado = subprocess.run(
            ['pkill', '-f', 'chromium|chrome'],
            capture_output=True, timeout=5
        )
        if resultado.returncode == 0:
            logger.info("  Procesos de Chromium huérfanos eliminados.")
    except FileNotFoundError:
        # Windows o sistema sin pkill
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'chrome.exe'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
    except Exception:
        pass


def _liberar_memoria(logger):
    """Fuerza la liberación de memoria entre scrapers.

    Combina:
    1. Garbage collector de Python (libera objetos no referenciados)
    2. Matar procesos de Chromium huérfanos (libera RAM del SO)
    """
    logger.info("  Liberando memoria...")
    gc.collect()
    _matar_chromium_huerfano(logger)
    gc.collect()


def _ejecutar_scraper_seguro(nombre, funcion_scraper, logger):
    """Ejecuta un scraper con protección contra errores y limpieza.

    Si el scraper falla por cualquier razón (timeout, OOM, crash de
    Chromium), captura el error, limpia la memoria y continúa con
    el siguiente scraper.

    Returns:
        pd.DataFrame: resultado del scraper (vacío si falló)
    """
    logger.info("")
    logger.info("-" * 40)
    logger.info(nombre.upper())
    logger.info("-" * 40)

    try:
        df = funcion_scraper()
        if df is None:
            df = pd.DataFrame()
        return df
    except MemoryError:
        logger.error(
            "ERROR DE MEMORIA ejecutando %s. "
            "El entorno no tiene suficiente RAM.", nombre)
        return pd.DataFrame()
    except Exception as e:
        logger.error("Error ejecutando scraper de %s: %s", nombre, e)
        return pd.DataFrame()
    finally:
        # Siempre limpiar después de cada scraper
        _liberar_memoria(logger)


def main():
    # Cargar variables de entorno
    load_dotenv()

    # Configurar logging
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("SUPERMARKET PRICE TRACKER - Inicio de ejecución")
    logger.info("Fecha: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Project root: %s", _PROJECT_ROOT)
    logger.info("=" * 60)

    # Inicializar base de datos
    db_path = inicializar_base_datos()
    logger.info("Base de datos: %s", db_path)
    db = DatabaseManager(db_path)

    # Asegurar que Playwright está disponible
    _asegurar_playwright(logger)

    # Limpiar Chromium que pueda haber quedado de ejecuciones anteriores
    _matar_chromium_huerfano(logger)

    # Obtener cookie automática para Dia
    logger.info("")
    logger.info("Configurando cookies automáticas...")
    try:
        from scraper.cookie_manager import obtener_y_configurar_cookies
        estado_cookies = obtener_y_configurar_cookies()
        for nombre, estado in estado_cookies.items():
            logger.info("  %s: %s", nombre, estado)
    except Exception as e:
        logger.warning("Error configurando cookies: %s", e)

    # Limpiar Chromium del cookie_manager
    _liberar_memoria(logger)

    # Carpeta de exportación
    os.makedirs('export', exist_ok=True)

    # ── Ejecutar scrapers en orden (API primero, Playwright después) ──
    # Orden estratégico:
    # 1. Mercadona (API REST pura, 0 RAM extra, siempre funciona)
    # 2. Dia (API REST pura, 0 RAM extra)
    # 3. Carrefour (Playwright, ~2.400 productos, moderado)
    # 4. Alcampo (Playwright, ~10.000 productos, pesado)
    # 5. Eroski (Playwright + infinite scroll, el más pesado)

    scrapers = [
        ("Mercadona", gestion_mercadona),
        ("Dia", gestion_dia),
        ("Carrefour", gestion_carrefour),
        ("Alcampo", gestion_alcampo),
        ("Eroski", gestion_eroski),
    ]

    resultados = {}
    df_total = pd.DataFrame()

    for nombre, funcion_scraper in scrapers:
<<<<<<< HEAD
        logger.info("")
        logger.info("-" * 40)
        logger.info(nombre.upper())
        logger.info("-" * 40)

        df = _ejecutar_scraper_con_timeout(nombre, funcion_scraper, logger)

=======
        df = _ejecutar_scraper_seguro(nombre, funcion_scraper, logger)
>>>>>>> 87a7abd (changes in scrapers fixing bug with timeout)
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

            # Liberar el DataFrame parcial de memoria
            del df
            gc.collect()

    # Deduplicar
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
        logger.info("  Días con datos:       %s", stats.get("dias_con_datos", "?"))
        logger.info("  Supermercados:        %s", stats["total_supermercados"])
        logger.info("  Primera captura:      %s", stats["primera_captura"])
        logger.info("  Última captura:       %s", stats["ultima_captura"])
    except Exception as e:
        logger.warning("No se pudieron obtener estadísticas: %s", e)

    # Exportar a Excel
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
