"""
run_scraper.py - Ejecuta un scraper individual y guarda en la base de datos.

Uso:
    python run_scraper.py dia
    python run_scraper.py mercadona
    python run_scraper.py carrefour
    python run_scraper.py alcampo
    python run_scraper.py eroski

    # Exportar también a CSV (para CI/CD paralelo):
    python run_scraper.py dia --export-csv export/dia.csv

    # Solo CSV, sin tocar la DB:
    python run_scraper.py dia --export-csv export/dia.csv --skip-db
"""

import sys
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Forzar PROJECT_ROOT basado en la ubicación de este script
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

SCRAPERS = {
    "mercadona": ("scraper.mercadona", "gestion_mercadona"),
    "carrefour": ("scraper.carrefour", "gestion_carrefour"),
    "dia":       ("scraper.dia",       "gestion_dia"),
    "alcampo":   ("scraper.alcampo",   "gestion_alcampo"),
    "eroski":    ("scraper.eroski",     "gestion_eroski"),
    "lidl":      ("scraper.lidl",      "gestion_lidl"),
}

NECESITA_COOKIE = {"dia"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    csv_path = None
    if "--export-csv" in sys.argv:
        idx = sys.argv.index("--export-csv")
        if idx + 1 < len(sys.argv):
            csv_path = sys.argv[idx + 1]
    skip_db = "--skip-db" in sys.argv

    if not args or args[0].lower() not in SCRAPERS:
        print(f"Uso: python run_scraper.py <{'|'.join(SCRAPERS.keys())}> "
              "[--export-csv ruta.csv] [--skip-db]")
        sys.exit(1)

    nombre = args[0].lower()
    modulo_path, funcion_nombre = SCRAPERS[nombre]

    logger.info("=" * 50)
    logger.info("Ejecutando scraper: %s", nombre.upper())
    logger.info("Project root: %s", _PROJECT_ROOT)
    logger.info("=" * 50)

    db = None
    if not skip_db:
        from database.init_db import inicializar_base_datos
        from database.database_db_manager import DatabaseManager
        db_path = inicializar_base_datos()
        logger.info("Base de datos: %s", db_path)
        db = DatabaseManager(db_path)

    if nombre in NECESITA_COOKIE:
        logger.info("Configurando cookies...")
        try:
            from scraper.cookie_manager import obtener_y_configurar_cookies
            for k, v in obtener_y_configurar_cookies().items():
                logger.info("  %s: %s", k, v)
        except Exception as e:
            logger.warning("Error configurando cookies: %s", e)

    import importlib
    try:
        modulo = importlib.import_module(modulo_path)
        funcion_scraper = getattr(modulo, funcion_nombre)
    except Exception as e:
        logger.error("No se pudo importar %s: %s", modulo_path, e)
        if db:
            db.cerrar()
        sys.exit(1)

    try:
        df = funcion_scraper()
    except Exception as e:
        logger.error("Error ejecutando %s: %s", nombre, e)
        if db:
            db.cerrar()
        sys.exit(1)

    if df is None or df.empty:
        logger.warning("No se obtuvieron productos de %s.", nombre)
        if db:
            db.cerrar()
        return

    if "Id" in df.columns and "Supermercado" in df.columns:
        antes = len(df)
        df = df.drop_duplicates(subset=["Id", "Supermercado"], keep="first")
        if len(df) < antes:
            logger.info("Deduplicación: %d → %d", antes, len(df))

    if csv_path:
        os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
        df.to_csv(csv_path, index=False)
        logger.info("CSV exportado: %s (%d filas)", csv_path, len(df))

    if db:
        try:
            r = db.guardar_productos(df)
            logger.info("DB: %d nuevos, %d actualizados, %d precios.",
                        r['productos_nuevos'], r['productos_actualizados'],
                        r['precios_registrados'])
        except Exception as e:
            logger.error("Error guardando en DB: %s", e)
        db.cerrar()

    logger.info("Hecho. %d productos de %s.", len(df), nombre.capitalize())


if __name__ == "__main__":
    main()
