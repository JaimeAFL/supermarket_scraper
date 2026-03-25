#!/usr/bin/env python3
"""Análisis de precios para post: ¿Cuál es el supermercado más barato de España?"""

import os
import psycopg2
import psycopg2.extras

url = os.environ.get("DATABASE_URL", "")
if not url:
    raise ValueError("Pon DATABASE_URL en el entorno")

conn = psycopg2.connect(url, connect_timeout=15)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

SEP = "=" * 60

# ── 1. Visión general ──────────────────────────────────────────
print(SEP)
print("1. PRODUCTOS POR SUPERMERCADO")
print(SEP)
cur.execute("""
    SELECT supermercado, COUNT(*) as n_productos
    FROM productos
    GROUP BY supermercado
    ORDER BY n_productos DESC
""")
for r in cur.fetchall():
    print(f"  {r['supermercado']:15} {r['n_productos']:>6} productos")

# ── 2. Precio más reciente por producto ───────────────────────
print()
print(SEP)
print("2. PRECIO MEDIANO Y MEDIO (último precio de cada producto)")
print(SEP)
cur.execute("""
    WITH ultimo_precio AS (
        SELECT DISTINCT ON (producto_id)
            producto_id,
            precio
        FROM precios
        ORDER BY producto_id, fecha_captura DESC
    )
    SELECT
        p.supermercado,
        COUNT(*)                            AS n,
        ROUND(AVG(up.precio)::numeric, 2)   AS media,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY up.precio)::numeric, 2) AS mediana,
        ROUND(MIN(up.precio)::numeric, 2)   AS min,
        ROUND(MAX(up.precio)::numeric, 2)   AS max,
        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY up.precio)::numeric, 2) AS p25,
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY up.precio)::numeric, 2) AS p75
    FROM ultimo_precio up
    JOIN productos p ON p.id = up.producto_id
    GROUP BY p.supermercado
    ORDER BY mediana ASC
""")
rows = cur.fetchall()
print(f"  {'Super':15} {'N':>6} {'Media':>7} {'Mediana':>8} {'P25':>7} {'P75':>7} {'Min':>6} {'Max':>7}")
print("  " + "-"*65)
for r in rows:
    print(f"  {r['supermercado']:15} {r['n']:>6} {r['media']:>7} {r['mediana']:>8} {r['p25']:>7} {r['p75']:>7} {r['min']:>6} {r['max']:>7}")

# ── 3. Cesta básica normalizada ───────────────────────────────
print()
print(SEP)
print("3. CESTA BÁSICA — precio mínimo disponible por producto")
print(SEP)

cesta = {
    'Leche entera 1L':          'leche entera',
    'Leche semidesnatada 1L':   'leche semidesnatada',
    'Aceite oliva virgen extra': 'aceite de oliva virgen extra',
    'Aceite girasol 1L':        'aceite girasol',
    'Arroz 1kg':                'arroz',
    'Pasta':                    'macarr',
    'Harina 1kg':               'harina de trigo',
    'Azúcar 1kg':               'azúcar',
    'Sal':                      'sal fina',
    'Huevos 12ud':              'huevos',
    'Mantequilla':              'mantequilla',
    'Yogur natural':            'yogur natural',
    'Tomate frito':             'tomate frito',
    'Tomate triturado':         'tomate triturado',
    'Lentejas':                 'lentejas',
    'Garbanzos':                'garbanzos',
    'Pan de molde':             'pan de molde',
    'Papel higiénico':          'papel higién',
    'Detergente lavadora':      'detergente',
    'Lejía':                    'lejía',
    'Cerveza lata':             'cerveza',
    'Agua mineral 1.5L':        'agua mineral',
    'Patatas fritas':           'patatas fritas',
    'Atún en aceite':           'atún en aceite',
    'Galletas':                 'galletas',
}

cur.execute("""
    WITH ultimo_precio AS (
        SELECT DISTINCT ON (producto_id)
            producto_id, precio
        FROM precios
        ORDER BY producto_id, fecha_captura DESC
    )
    SELECT
        p.supermercado,
        LOWER(p.nombre) AS nombre,
        up.precio
    FROM ultimo_precio up
    JOIN productos p ON p.id = up.producto_id
    WHERE up.precio > 0 AND up.precio <= 50
""")
all_prods = cur.fetchall()

from collections import defaultdict
# Agrupar por supermercado
by_super = defaultdict(list)
for r in all_prods:
    by_super[r['supermercado']].append((r['nombre'], float(r['precio'])))

supers = sorted(by_super.keys())
totales = defaultdict(float)
n_encontrados = defaultdict(int)

print(f"  {'Producto':30}", end="")
for s in supers:
    print(f"  {s[:10]:>10}", end="")
print()
print("  " + "-" * (30 + 12 * len(supers)))

for label, kw in cesta.items():
    print(f"  {label:30}", end="")
    for s in supers:
        hits = [precio for nombre, precio in by_super[s] if kw.lower() in nombre]
        if hits:
            p = min(hits)
            totales[s] += p
            n_encontrados[s] += 1
            print(f"  {p:>10.2f}", end="")
        else:
            print(f"  {'—':>10}", end="")
    print()

print()
print(f"  {'TOTAL CESTA':30}", end="")
for s in supers:
    print(f"  {totales[s]:>10.2f}", end="")
print()
print(f"  {'Nº productos encontrados':30}", end="")
for s in supers:
    print(f"  {n_encontrados[s]:>10}", end="")
print()

# ── 4. Ranking final ──────────────────────────────────────────
print()
print(SEP)
print("4. RANKING FINAL (cesta básica, precio mínimo)")
print(SEP)
ranking = sorted(totales.items(), key=lambda x: x[1])
for i, (s, t) in enumerate(ranking, 1):
    print(f"  {i}. {s:15} {t:.2f}€")

mas_barato = ranking[0]
mas_caro   = ranking[-1]
diff = mas_caro[1] - mas_barato[1]
print(f"\n  Diferencia {mas_caro[0]} vs {mas_barato[0]}: {diff:.2f}€ por compra")
print(f"  Anualizado (compra semanal): {diff * 52:.0f}€/año")

# ── 5. Por categoría normalizada ─────────────────────────────
print()
print(SEP)
print("5. MEDIANA POR CATEGORÍA NORMALIZADA (top categorías)")
print(SEP)
cur.execute("""
    WITH ultimo_precio AS (
        SELECT DISTINCT ON (producto_id)
            producto_id, precio
        FROM precios
        ORDER BY producto_id, fecha_captura DESC
    )
    SELECT
        p.supermercado,
        p.categoria_normalizada,
        COUNT(*) as n,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY up.precio)::numeric, 2) AS mediana
    FROM ultimo_precio up
    JOIN productos p ON p.id = up.producto_id
    WHERE p.categoria_normalizada != ''
      AND up.precio > 0 AND up.precio <= 50
    GROUP BY p.supermercado, p.categoria_normalizada
    HAVING COUNT(*) >= 5
    ORDER BY p.categoria_normalizada, mediana
""")
cat_rows = cur.fetchall()

# Pivotar
from collections import defaultdict
cat_data = defaultdict(dict)
for r in cat_rows:
    cat_data[r['categoria_normalizada']][r['supermercado']] = (float(r['mediana']), r['n'])

# Solo cats presentes en al menos 3 supers
cats_comunes = {c: d for c, d in cat_data.items() if len(d) >= 3}
print(f"  Categorías con datos en ≥3 supers: {len(cats_comunes)}")
print()

# Ganador por categoría
ganadores = defaultdict(int)
print(f"  {'Categoría':25} {'Ganador':15} {'Precio':>7}  (resto)")
print("  " + "-"*70)
for cat, datos in sorted(cats_comunes.items()):
    ganador = min(datos.items(), key=lambda x: x[1][0])
    resto = {s: v[0] for s, v in datos.items() if s != ganador[0]}
    resto_str = "  ".join(f"{s[:5]}:{v:.2f}" for s, v in sorted(resto.items(), key=lambda x: x[1]))
    print(f"  {cat:25} {ganador[0]:15} {ganador[1][0]:>7.2f}  {resto_str}")
    ganadores[ganador[0]] += 1

print()
print(SEP)
print("6. VICTORIAS POR CATEGORÍA")
print(SEP)
for s, n in sorted(ganadores.items(), key=lambda x: -x[1]):
    print(f"  {s:15} gana en {n} categorías")

conn.close()
print()
print("✓ Análisis completo")
