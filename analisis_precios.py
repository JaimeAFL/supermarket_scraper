#!/usr/bin/env python3
"""
Análisis: ¿Cuál es el supermercado más barato de España para la compra básica?
Cesta basada en las categorías de mayor gasto del INE (IPCA España).
"""

import os
import psycopg2
import psycopg2.extras
from collections import defaultdict

url = os.environ.get("DATABASE_URL", "")
if not url:
    raise ValueError("Pon DATABASE_URL en el entorno")

conn = psycopg2.connect(url, connect_timeout=15)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

SEP = "=" * 70

# ── 1. Visión general ──────────────────────────────────────────────────
print(SEP)
print("1. PRODUCTOS EN BD POR SUPERMERCADO")
print(SEP)
cur.execute("""
    SELECT supermercado, COUNT(*) as n
    FROM productos
    GROUP BY supermercado ORDER BY n DESC
""")
for r in cur.fetchall():
    print(f"  {r['supermercado']:15} {r['n']:>6} productos")

# ── 2. Ranking global por mediana ──────────────────────────────────────
print()
print(SEP)
print("2. RANKING GLOBAL — mediana del último precio de cada producto")
print(SEP)
cur.execute("""
    WITH ultimo AS (
        SELECT DISTINCT ON (producto_id) producto_id, precio
        FROM precios ORDER BY producto_id, fecha_captura DESC
    )
    SELECT
        p.supermercado,
        COUNT(*)                            AS n,
        ROUND(AVG(u.precio)::numeric, 2)    AS media,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY u.precio)::numeric, 2) AS mediana,
        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY u.precio)::numeric, 2) AS p25,
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY u.precio)::numeric, 2) AS p75
    FROM ultimo u
    JOIN productos p ON p.id = u.producto_id
    WHERE u.precio > 0
    GROUP BY p.supermercado
    ORDER BY mediana ASC
""")
print(f"  {'Super':15} {'N':>6}  {'Mediana':>8}  {'Media':>7}  {'P25':>6}  {'P75':>6}")
print("  " + "-" * 55)
for r in cur.fetchall():
    print(f"  {r['supermercado']:15} {r['n']:>6}  {r['mediana']:>8}  {r['media']:>7}  {r['p25']:>6}  {r['p75']:>6}")

# ── 3. Cesta INE ───────────────────────────────────────────────────────
# Basada en las categorías de mayor gasto del INE para hogares españoles.
# Por cada categoría se usan varios keywords: el primero que dé hits es el usado.
# Se toma el precio mínimo disponible (la opción más barata en cada super).

CESTA_INE = {
    # ── Lácteos ───────────────────────────────────────────────────────
    'Leche entera 1L':          [('leche entera', 0, 4)],
    'Leche semidesnatada 1L':   [('leche semidesnatada', 0, 4)],

    # ── Huevos ────────────────────────────────────────────────────────
    # min 1.50€ para excluir huevos sueltos o medias docenas
    'Huevos 12 ud':             [('huevos', 1.50, 10)],

    # ── Carne de ave ──────────────────────────────────────────────────
    'Pechuga de pollo':         [('pechuga de pollo', 1.50, 15), ('pechuga pollo', 1.50, 15)],
    'Pollo entero':             [('pollo entero', 2.50, 15)],

    # ── Carne de vacuno ───────────────────────────────────────────────
    'Carne picada vacuno':      [('carne picada', 1.50, 15)],

    # ── Carne de porcino ──────────────────────────────────────────────
    # min 3€ para excluir precios por 100g
    'Lomo de cerdo':            [('lomo de cerdo', 3.00, 15), ('lomo cerdo', 3.00, 15)],

    # ── Pescado ───────────────────────────────────────────────────────
    'Merluza':                  [('merluza', 1.50, 25)],
    'Atún/bonito (lata)':       [('atún en aceite', 0, 10), ('bonito en aceite', 0, 10)],
    # Salmón eliminado: precio muy variable (por lonja vs pieza), no comparable

    # ── Frutas frescas ────────────────────────────────────────────────
    'Manzana':                  [('manzana', 0, 10)],
    'Naranja':                  [('naranja', 0, 10)],
    'Plátano':                  [('plátano', 0, 10), ('platano', 0, 10)],

    # ── Hortalizas y legumbres ────────────────────────────────────────
    'Tomate':                   [('tomate', 0, 8)],
    'Lechuga':                  [('lechuga', 0, 5)],
    'Cebolla':                  [('cebolla', 0, 5)],
    'Zanahoria':                [('zanahoria', 0, 5)],
    'Patatas (bolsa)':          [('patatas', 0, 8)],
    'Lentejas':                 [('lentejas', 0, 5)],
    'Garbanzos':                [('garbanzos', 0, 5)],

    # ── Cereales y féculas ────────────────────────────────────────────
    'Arroz 1kg':                [('arroz', 0, 5)],
    'Pan de molde':             [('pan de molde', 0, 5)],
    'Pasta (espagueti/macarrón)':[('espagueti', 0, 5), ('macarr', 0, 5)],

    # ── Aceite ────────────────────────────────────────────────────────
    'Aceite de oliva virgen':   [('aceite de oliva virgen extra', 0, 15), ('aceite oliva virgen extra', 0, 15)],
    'Aceite de girasol':        [('aceite de girasol', 0, 10), ('aceite girasol', 0, 10)],

    # ── Limpieza del hogar ────────────────────────────────────────────
    'Detergente lavadora':      [('detergente', 0, 25)],
    'Limpiahogar multiusos':    [('multiusos', 0, 10), ('limpiahogar', 0, 10)],
    'Lejía':                    [('lejía', 0, 5), ('lejia', 0, 5)],
    'Papel higiénico':          [('papel higiénico', 0, 15), ('papel higienico', 0, 15)],
    'Bolsas de basura':         [('bolsas de basura', 0, 10), ('bolsas basura', 0, 10)],
    'Papel de cocina':          [('papel de cocina', 0, 10), ('papel cocina', 0, 10)],

    # ── Higiene y cosmética ───────────────────────────────────────────
    'Champú':                   [('champú', 0, 10), ('champu', 0, 10)],
    'Gel de ducha':             [('gel de ducha', 0, 8), ('gel ducha', 0, 8)],
    'Pasta de dientes':         [('pasta de dientes', 0, 8), ('dentífrico', 0, 8)],
    'Desodorante':              [('desodorante', 0, 8)],
}

print()
print(SEP)
print("3. CESTA BÁSICA INE — precio mínimo disponible por producto (€)")
print(SEP)

# Cargar todos los últimos precios
cur.execute("""
    WITH ultimo AS (
        SELECT DISTINCT ON (producto_id) producto_id, precio
        FROM precios ORDER BY producto_id, fecha_captura DESC
    )
    SELECT p.supermercado, LOWER(p.nombre) AS nombre, u.precio
    FROM ultimo u
    JOIN productos p ON p.id = u.producto_id
    WHERE u.precio > 0
""")
all_rows = cur.fetchall()

by_super = defaultdict(list)
for r in all_rows:
    by_super[r['supermercado']].append((r['nombre'], float(r['precio'])))

supers = sorted(by_super.keys())

totales      = defaultdict(float)
n_enc        = defaultdict(int)
detalle      = {}   # detalle[producto][super] = precio

for label, variantes in CESTA_INE.items():
    detalle[label] = {}
    for s in supers:
        for (kw, pmin, pmax) in variantes:
            hits = [
                precio for nombre, precio in by_super[s]
                if kw.lower() in nombre and pmin <= precio <= pmax
            ]
            if hits:
                p = min(hits)
                detalle[label][s] = p
                totales[s] += p
                n_enc[s] += 1
                break

# Imprimir tabla
header = f"  {'Producto':32}"
for s in supers:
    header += f"  {s[:10]:>10}"
print(header)
print("  " + "-" * (32 + 12 * len(supers)))

for label in CESTA_INE:
    row = f"  {label:32}"
    for s in supers:
        if s in detalle[label]:
            row += f"  {detalle[label][s]:>10.2f}"
        else:
            row += f"  {'—':>10}"
    print(row)

print("  " + "-" * (32 + 12 * len(supers)))
row_total = f"  {'TOTAL CESTA':32}"
row_n     = f"  {'Nº productos encontrados':32}"
for s in supers:
    row_total += f"  {totales[s]:>10.2f}"
    row_n     += f"  {n_enc[s]:>10}"
print(row_total)
print(row_n)

# ── 4. Ranking final ───────────────────────────────────────────────────
print()
print(SEP)
print("4. RANKING FINAL — cesta básica (precio mínimo)")
print(SEP)
ranking = sorted([(s, totales[s]) for s in supers if totales[s] > 0], key=lambda x: x[1])
for i, (s, t) in enumerate(ranking, 1):
    print(f"  {i}. {s:15} {t:.2f}€  ({n_enc[s]} productos)")

if len(ranking) >= 2:
    mas_barato = ranking[0]
    mas_caro   = ranking[-1]
    diff = mas_caro[1] - mas_barato[1]
    print(f"\n  {mas_caro[0]} vs {mas_barato[0]}: {diff:.2f}€ más caro por compra")
    print(f"  Diferencia anualizada (1 compra/semana): {diff * 52:.0f}€/año")

# ── 5. Quién gana en cada categoría ───────────────────────────────────
print()
print(SEP)
print("5. GANADOR POR PRODUCTO (supermercado más barato)")
print(SEP)
ganadores = defaultdict(int)
print(f"  {'Producto':32}  {'Ganador':15}  {'Precio':>7}  {'2º':>7}  {'Ahorro':>7}")
print("  " + "-" * 75)
for label in CESTA_INE:
    d = detalle[label]
    if len(d) < 2:
        continue
    orden = sorted(d.items(), key=lambda x: x[1])
    g_s, g_p = orden[0]
    s2, p2    = orden[1]
    ahorro    = p2 - g_p
    ganadores[g_s] += 1
    print(f"  {label:32}  {g_s:15}  {g_p:>7.2f}  {p2:>7.2f}  {ahorro:>+7.2f}")

print()
print(SEP)
print("6. VICTORIAS POR SUPERMERCADO (en cuántos productos es el más barato)")
print(SEP)
for s, n in sorted(ganadores.items(), key=lambda x: -x[1]):
    bar = "█" * n
    print(f"  {s:15}  {n:>3} victorias  {bar}")

conn.close()
print()
print("✓ Análisis completado")
