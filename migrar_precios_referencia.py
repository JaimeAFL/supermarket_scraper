#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script PUNTUAL de migración retroactiva.
Recorre todos los registros de `precios` donde precio_referencia IS NULL,
recalcula los campos y los actualiza en PostgreSQL.

Ejecución:  python migrar_precios_referencia.py
Es idempotente. Eliminar tras ejecutar con éxito.
"""

import os, sys, logging

_RAIZ = os.path.dirname(os.path.abspath(__file__))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_RAIZ, ".env"))
except ImportError:
    pass

try:
    import psycopg2, psycopg2.extras
except ImportError:
    print("ERROR: pip install psycopg2-binary"); sys.exit(1)

try:
    from matching.normalizer import calcular_precio_unitario
except ImportError as e:
    print(f"ERROR: {e}"); sys.exit(1)

TAMAÑO_BATCH = 1000
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def _conectar():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL no definida."); sys.exit(1)
    url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, sslmode="require")
    conn.autocommit = False
    return conn

def _barra(actual, total, ancho=40):
    p = actual / total if total else 1.0
    b = "█" * int(p * ancho) + "░" * (ancho - int(p * ancho))
    print(f"\r  [{b}] {actual:>7}/{total}  ({p*100:.1f}%)", end="", flush=True)

def migrar():
    conn = _conectar()
    cur_r = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur_w = conn.cursor()

    cur_r.execute("SELECT COUNT(*) AS total FROM precios WHERE precio_referencia IS NULL")
    total = cur_r.fetchone()["total"]
    if total == 0:
        print("No hay registros pendientes. Migración ya realizada.")
        conn.close(); return

    print(f"Registros pendientes: {total:,}  |  batch={TAMAÑO_BATCH:,}\n")

    cur_r.execute("""
        SELECT pr.id, pr.precio, pr.precio_por_unidad, p.formato_normalizado
        FROM   precios pr
        JOIN   productos p ON p.id = pr.producto_id
        WHERE  pr.precio_referencia IS NULL
        ORDER  BY pr.id
    """)

    migrados = sin_formato = con_error = batch = procesados = 0

    fila = cur_r.fetchone()
    while fila:
        procesados += 1
        try:
            res = calcular_precio_unitario(
                fila["precio"],
                fila["formato_normalizado"] or "",
                fila["precio_por_unidad"],
            )
            pr, ur = res.get("precio_referencia"), res.get("unidad_referencia") or ""
            cur_w.execute(
                "UPDATE precios SET precio_referencia=%s, unidad_referencia=%s WHERE id=%s",
                (pr, ur, fila["id"]),
            )
            batch += 1
            if pr is None: sin_formato += 1
            else: migrados += 1
        except Exception as exc:
            con_error += 1
            logger.warning("Error id=%s: %s", fila["id"], exc)

        if batch >= TAMAÑO_BATCH:
            conn.commit(); batch = 0

        if procesados % 100 == 0 or procesados == total:
            _barra(procesados, total)

        fila = cur_r.fetchone()

    if batch: conn.commit()
    _barra(total, total); print("\n")
    conn.close()

    print("─" * 55)
    print(f"  Migrados      : {migrados:>7,}")
    print(f"  Sin formato   : {sin_formato:>7,}")
    print(f"  Con error     : {con_error:>7,}")
    print(f"  Total leídos  : {procesados:>7,}")
    print("─" * 55)
    if con_error: print(f"ATENCIÓN: {con_error} filas fallaron.")
    else: print("Migración completada sin errores.")

if __name__ == "__main__":
    migrar()
