"""
run_scraper.py - Ejecuta un scraper individual y guarda en la base de datos.

Uso:
    python run_scraper.py dia
    python run_scraper.py mercadona
    python run_scraper.py carrefour
    python run_scraper.py alcampo
    python run_scraper.py eroski
"""

import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Mapa de scrapers ──────────────────────────────────────────────────────────
SCRAPERS = {
    "mercadona": ("scraper.mercadona", "gestion_mercadona"),
    "carrefour": ("scraper.carrefour", "gestion_carrefour"),
    "dia":       ("scraper.dia",       "gestion_dia"),
    "alcampo":   ("scraper.alcampo",   "gestion_alcampo"),
    "eroski":    ("scraper.eroski",     "gestion_eroski"),
}

# Scrapers que necesitan cookie automática antes de ejecutarse
NECESITA_COOKIE = {"dia"}


def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() not in SCRAPERS:
        print(f"Uso: python run_scraper.py <{'|'.join(SCRAPERS.keys())}>")
        sys.exit(1)

    nombre = sys.argv[1].lower()
    modulo_path, funcion_nombre = SCRAPERS[nombre]

    logger.info("=" * 50)
    logger.info("Ejecutando scraper: %s", nombre.upper())
    logger.info("Fecha: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 50)

    # ── Inicializar DB ─────────────────────────────────────────────────────────
    from database.init_db import inicializar_base_datos
    from database.database_db_manager import DatabaseManager

    inicializar_base_datos()
    db = DatabaseManager()

    # ── Cookie automática (solo los que la necesitan) ──────────────────────────
    if nombre in NECESITA_COOKIE:
        logger.info("Configurando cookies para %s...", nombre)
        try:
            from scraper.cookie_manager import obtener_y_configurar_cookies
            estado = obtener_y_configurar_cookies()
            for k, v in estado.items():
                logger.info("  %s: %s", k, v)
        except Exception as e:
            logger.warning("Error configurando cookies: %s", e)

    # ── Importar y ejecutar scraper ────────────────────────────────────────────
    import importlib
    try:
        modulo = importlib.import_module(modulo_path)
        funcion_scraper = getattr(modulo, funcion_nombre)
    except Exception as e:
        logger.error("No se pudo importar %s: %s", modulo_path, e)
        db.cerrar()
        sys.exit(1)

    try:
        df = funcion_scraper()
    except Exception as e:
        logger.error("Error ejecutando scraper de %s: %s", nombre, e)
        db.cerrar()
        sys.exit(1)

    if df is None or df.empty:
        logger.warning("No se obtuvieron productos de %s.", nombre)
        db.cerrar()
        return

    # ── Deduplicar ─────────────────────────────────────────────────────────────
    if "Id" in df.columns and "Supermercado" in df.columns:
        antes = len(df)
        df = df.drop_duplicates(subset=["Id", "Supermercado"], keep="first")
        if len(df) < antes:
            logger.info("Deduplicación: %d → %d productos", antes, len(df))

    # ── Guardar en SQLite ──────────────────────────────────────────────────────
    try:
        resumen = db.guardar_productos(df)
        logger.info(
            "DB: %d nuevos, %d actualizados, %d precios registrados.",
            resumen.get('productos_nuevos', resumen.get('nuevos', 0)),
            resumen.get('productos_actualizados', resumen.get('actualizados', 0)),
            resumen.get('precios_registrados', resumen.get('precios', 0)),
        )
    except Exception as e:
        logger.error("Error guardando en DB: %s", e)

    # ── Estadísticas finales ───────────────────────────────────────────────────
    try:
        stats = db.obtener_estadisticas()
        logger.info("")
        logger.info("ESTADO DE LA BASE DE DATOS")
        logger.info("  Productos totales:    %s", stats["total_productos"])
        logger.info("  Registros de precios: %s", stats["total_registros_precios"])
    except Exception:
        pass

    db.cerrar()
    logger.info("")
    logger.info("Hecho. %d productos de %s procesados.", len(df), nombre.capitalize())


if __name__ == "__main__":
    main()
