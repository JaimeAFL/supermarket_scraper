"""
import_results.py - Importa CSVs de resultados de scrapers a la base de datos.

Usado por el workflow de GitHub Actions para fusionar resultados
de jobs paralelos en una sola base de datos.

Uso:
    python import_results.py export/mercadona.csv export/dia.csv ...
    python import_results.py export/*.csv
"""

import sys
import os
import logging
import glob
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    from database.init_db import inicializar_base_datos
    from database.database_db_manager import DatabaseManager

    # Recoger rutas de CSV (soporta globs)
    rutas = []
    for arg in sys.argv[1:]:
        expandidos = glob.glob(arg)
        rutas.extend(expandidos if expandidos else [arg])

    if not rutas:
        print("Uso: python import_results.py export/*.csv")
        sys.exit(1)

    inicializar_base_datos()
    db = DatabaseManager()

    total_productos = 0

    for ruta in sorted(rutas):
        if not os.path.exists(ruta):
            logger.warning("Archivo no encontrado: %s", ruta)
            continue

        logger.info("Importando: %s", ruta)
        try:
            df = pd.read_csv(ruta)
        except Exception as e:
            logger.error("Error leyendo %s: %s", ruta, e)
            continue

        if df.empty:
            logger.warning("  Vacío: %s", ruta)
            continue

        # Deduplicar dentro del CSV
        if "Id" in df.columns and "Supermercado" in df.columns:
            df = df.drop_duplicates(subset=["Id", "Supermercado"], keep="first")

        try:
            r = db.guardar_productos(df)
            n = r.get("productos_nuevos", 0)
            u = r.get("productos_actualizados", 0)
            p = r.get("precios_registrados", 0)
            logger.info(
                "  %s: %d filas → %d nuevos, %d actualizados, %d precios",
                os.path.basename(ruta), len(df), n, u, p,
            )
            total_productos += len(df)
        except Exception as e:
            logger.error("  Error importando %s: %s", ruta, e)

    # Estadísticas finales
    try:
        stats = db.obtener_estadisticas()
        logger.info("")
        logger.info("BASE DE DATOS ACTUALIZADA")
        logger.info("  Productos totales:    %s", stats["total_productos"])
        logger.info("  Registros de precios: %s", stats["total_registros_precios"])
        logger.info("  Días con datos:       %s", stats.get("dias_con_datos", "?"))
    except Exception:
        pass

    db.cerrar()
    logger.info("Importación completada: %d productos procesados.", total_productos)


if __name__ == "__main__":
    main()
