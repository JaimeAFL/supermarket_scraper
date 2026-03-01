# Changelog

Registro de todos los cambios realizados en Supermarket Price Tracker.

## v2.0.1 — Actualización de documentación (2026-03-01)

### Cambiado

- README actualizado con nombre de carpeta/repositorio actual (`supermarket_scraper`) y enlaces a documentación técnica.
- Documentación alineada con el estado real del código:
  - taxonomía de **28 categorías** (no 26),
  - referencia correcta a `database/database_db_manager.py`,
  - aclaraciones de cookies y ejecución en CI/CD.
- `docs/api_supermercados.md` reescrito para reflejar la estrategia actual de extracción por supermercado.
- `docs/guia_env.md` simplificada y sincronizada con `example.env` y los flujos de `main.py` / `run_scraper.py`.

---

## v2.0.0 — Motor de normalización NLP (2026-02-28)

Reescritura mayor del sistema de búsqueda y clasificación de productos.
Se añade un motor de normalización que extrae tipo de producto, marca y
categoría a partir del nombre, resolviendo el problema de que buscar
"leche" devolvía "café con leche".

### Añadido

- **`matching/normalizer.py`** — Motor NLP con dos métodos combinados:
  - Método 1 (reglas de posición): cada supermercado tiene un patrón de
    naming distinto (Alcampo: MARCA + tipo, Eroski: tipo + MARCA + formato,
    Mercadona/Carrefour/Dia: tipo + marca por diccionario).
  - Método 2 (taxonomía): clasifica el tipo extraído en 28 categorías
    normalizadas (Lácteos, Cafés e infusiones, Chocolates y cacao, etc.).
- **`matching/marcas.json`** — Diccionario de 1.480 marcas auto-extraídas
  de los datos de Alcampo y Eroski (donde la marca va en MAYÚSCULAS),
  complementadas con marcas manuales de Mercadona, Carrefour y Dia.
- **`import_results.py`** — Script para importar CSVs de scrapers paralelos
  a la base de datos con normalización automática.
- 4 columnas nuevas en tabla `productos`: `tipo_producto`, `marca`,
  `nombre_normalizado`, `categoria_normalizada`.
- 4 índices nuevos para búsqueda rápida por tipo, nombre normalizado,
  categoría y marca.
- Migración automática en `init_db.py`: al arrancar, detecta columnas
  faltantes, las crea con `ALTER TABLE` y normaliza los productos existentes.
- Filtro por categoría normalizada en la búsqueda rápida del dashboard.
- Separación de resultados por prioridad en el dashboard: resultados
  directos (tipo = búsqueda) vs. menciones secundarias.

### Cambiado

- **Búsqueda inteligente:** todas las búsquedas (principal, comparador,
  histórico, favoritos) ahora usan `UNION ALL` con dos niveles:
  prioridad 1 = `nombre_normalizado LIKE 'leche%'` (tipo),
  prioridad 2 = `nombre LIKE '%leche%'` (mención).
- **`database_db_manager.py`:** `guardar_productos()` ahora normaliza
  cada producto antes del INSERT/UPDATE.
- **`product_matcher.py`:** usa búsqueda por `tipo_producto` como base,
  con rapidfuzz opcional para refinar puntuación.

### Métricas de cobertura

- Marca extraída: 72,6% de 29.872 productos
- Categoría normalizada: 44,2% (alimentación + higiene; excluye
  electrónica, bricolaje, ropa)
- Precisión de búsqueda: "leche" pasa de 1.067 a 477 resultados
  relevantes (55% de ruido eliminado), "cerveza" 96% de precisión

---

## v1.1.0 — CI/CD paralelo y fixes del dashboard (2026-02-27)

Resolución de 6 bugs del dashboard y rediseño del workflow de GitHub Actions
para ejecución paralela.

### Corregido

- **Comparador sin resultados:** `buscar_para_comparar()` con fuzzy matching
  fallaba porque `token_sort_ratio("coca-cola", "COCA COLA ZERO Refresco de
  cola Zero azúcar botella 500ml")` ≈ 45, por debajo del umbral 70.
  Reemplazado por SQL LIKE multi-palabra (0.02s vs 0.64s fuzzy).
- **Búsqueda solo Mercadona:** `buscar_productos()` sin `ORDER BY` devolvía
  siempre los IDs más bajos (Mercadona = 1-4295). Añadido
  `ROW_NUMBER() OVER (PARTITION BY supermercado)` para distribuir resultados.
- **Distribución de precios ilegible:** dos gráficos en columnas de 50%
  con sidebar abierto → ~350px por gráfico → labels cortados. Cambiado
  a full-width en filas separadas con expander para la distribución completa.
- **Fechas en formato ISO:** gráficos mostraban "2026-02-19T22:59:32" en vez
  de "19/02/2026". Añadido `xaxis_tickformat='%d/%m/%Y'` y `hovertemplate`.
- **Error con un solo punto de datos:** gráfico de histórico fallaba con
  un solo registro. Añadido manejo para mostrar precio estático con caption.
- **`KeyError: fecha_captura`:** `obtener_historico_precios()` devolvía
  columna aliasada como `fecha` pero el chart esperaba `fecha_captura`.

### Añadido

- **`run_scraper.py`** con flags `--export-csv` y `--skip-db` para CI/CD.
- **`scraper_semanal.yml`** reescrito: 5 jobs paralelos independientes +
  job de merge final. Tiempo total: ~64 min (vs ~96 min secuencial).
  Cada job tiene `continue-on-error: true`.
- Métrica "Días de datos" en el dashboard principal.
- `obtener_estadisticas()` devuelve `dias_con_datos` y `productos_por_categoria`.
- `buscar_para_comparar()` con tabla resumen por supermercado y
  diferencias porcentuales vs. el más barato.

### Cambiado

- Histogramas de distribución: opacidad reducida a 0.45 (era 0.85),
  línea de mediana negra con fondo blanco (era roja sin fondo).
- Gráfico del comparador: barras horizontales ordenadas por precio
  con etiquetas "€X.XX (el más barato)" / "€X.XX (+Y%)".

---

## v1.0.0 — Versión inicial (2026-02-19)

### Añadido

- Scrapers funcionales para Mercadona, Carrefour, Dia, Alcampo y Eroski.
- Base de datos SQLite con tablas `productos`, `precios`, `equivalencias`
  y `favoritos`.
- Dashboard Streamlit con 4 páginas: principal, histórico, comparador
  y favoritos.
- GitHub Actions para ejecución semanal (lunes 7:00 AM, secuencial).
- Sistema de cookies con `cookie_manager.py` (obtención automática para Dia).
- `main.py` como orquestador secuencial de todos los scrapers.
- `product_matcher.py` con fuzzy matching vía rapidfuzz.
