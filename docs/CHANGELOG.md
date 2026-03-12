# Changelog

Registro de todos los cambios realizados en Supermarket Price Tracker.

---

## v2.1.0 — Estabilidad de scrapers, UX y exportación (2026-03-12)

### Añadido

- **Exportación de la cesta a PDF**: `export.py` con `generar_pdf_cesta()` usando fpdf2. Genera PDF agrupado por supermercado con total estimado, descargable directamente desde el dashboard.
- **Exportación por email sin SMTP**: `generar_enlaces_email()` crea URLs directas de composición para Gmail, Outlook y Yahoo con el cuerpo pre-rellenado. Botones con iconos de marca vía Simple Icons CDN.
- **Página Cesta** (`4_Cesta.py`): lista de la compra con exportación integrada a PDF y email.
- **Limpieza de procesos Chromium huérfanos**: `main.py` incluye `_matar_chromium_huerfano()` vía `pkill` para liberar recursos entre scrapers y después de cada ejecución.
- **`gc.collect()` entre scrapers** para reducir consumo de memoria en ejecuciones largas.
- **Wrappers de ejecución segura** en `main.py`: cada scraper se ejecuta en bloque `try/except` independiente.
- **Funciones helper compartidas** en `components.py` para reducir duplicación entre páginas del dashboard.

### Corregido

- **URLs silenciosamente descartadas**: `guardar_productos()` en `database_db_manager.py` (líneas 81–82) normalizaba inconsistentemente los nombres de columna `Url` vs `URL`. Ahora se estandariza `Url` en todos los scrapers y en el guardado.
- **Fallback de URL**: cuando `url` está vacía, se construye automáticamente a partir de `id_externo` + patrones de URL conocidos por supermercado.
- **`sqlite3.Row` no subscriptable**: corregido acceso a filas con `.get()` explícito en lugar de indexación por posición.
- **Flag `--single-process` eliminado**: este flag de Chromium rompía silenciosamente `page.on("response")` en Playwright, devolviendo 0 productos. Todos los scrapers Playwright usan ahora solo `--disable-dev-shm-usage`, `--no-sandbox`, `--disable-gpu`.
- **Orden de scrapers optimizado**: `main.py` ejecuta primero los scrapers por API (Mercadona, Dia) y después los de Playwright (Carrefour, Alcampo, Eroski) para minimizar el impacto de fallos de memoria.
- **Typo en `main.py` línea 49**: `.` → `,`.
- **Caracteres españoles corregidos** en textos del dashboard (tildes, ñ).

### Cambiado

- **SMTP eliminado**: reemplazado completamente por enlaces de composición web. No requiere configuración de servidor de correo.
- **Múltiples mejoras de UX** en páginas Histórico, Comparador, Favoritos y Cesta.
- **README reescrito** para audiencia técnica y no técnica, con sección de API REST.

---

## v2.0.1 — Actualización de documentación (2026-03-01)

### Cambiado

- README actualizado con nombre de carpeta/repositorio actual (`supermarket_scraper`) y enlaces a documentación técnica.
- Documentación alineada con el estado real del código:
  - taxonomía de **28 categorías** (no 26),
  - referencia correcta a `database/database_db_manager.py`,
  - aclaraciones de cookies y ejecución en CI/CD.
- `api_supermercados.md` reescrito para reflejar la estrategia actual de extracción por supermercado.
- `guia_env.md` simplificada y sincronizada con `example.env` y los flujos de `main.py` / `run_scraper.py`.

---

## v2.0.0 — Motor de normalización NLP (2026-02-28)

Reescritura mayor del sistema de búsqueda y clasificación de productos.
Se añade un motor de normalización que extrae tipo de producto, marca y
categoría a partir del nombre, resolviendo el problema de que buscar
"leche" devolvía "café con leche".

### Añadido

- **`normalizer.py`** — Motor NLP con dos métodos combinados:
  - Método 1 (reglas de posición): cada supermercado tiene un patrón de naming distinto (Alcampo: MARCA + tipo, Eroski: tipo + MARCA + formato, Mercadona/Carrefour/Dia: tipo + marca por diccionario).
  - Método 2 (taxonomía): clasifica el tipo extraído en 28 categorías normalizadas (Lácteos, Cafés e infusiones, Chocolates y cacao, etc.).
- **`marcas.json`** — Diccionario de 1.480 marcas auto-extraídas de los datos de Alcampo y Eroski, complementadas con marcas manuales.
- **`import_results.py`** — Script para importar CSVs de scrapers paralelos a la base de datos con normalización automática.
- 4 columnas nuevas en tabla `productos`: `tipo_producto`, `marca`, `nombre_normalizado`, `categoria_normalizada`.
- 4 índices nuevos para búsqueda rápida por tipo, nombre normalizado, categoría y marca.
- Migración automática en `init_db.py`: detecta columnas faltantes, las crea con `ALTER TABLE` y normaliza los productos existentes.
- Filtro por categoría normalizada en la búsqueda del dashboard.
- Separación de resultados por prioridad: resultados directos (tipo = búsqueda) vs. menciones secundarias.

### Cambiado

- **Búsqueda inteligente:** todas las búsquedas usan `UNION ALL` con dos niveles: prioridad 1 = `nombre_normalizado LIKE 'leche%'`, prioridad 2 = `nombre LIKE '%leche%'`.
- **`database_db_manager.py`:** `guardar_productos()` normaliza cada producto antes del INSERT/UPDATE.
- **`product_matcher.py`:** usa búsqueda por `tipo_producto` como base, con RapidFuzz opcional para refinar puntuación.

### Métricas de cobertura

- Marca extraída: 72,6% de 29.872 productos
- Categoría normalizada: 44,2% (alimentación + higiene; excluye electrónica, bricolaje, ropa)
- Precisión de búsqueda: "leche" pasa de 1.067 a 477 resultados relevantes (55% de ruido eliminado)

---

## v1.1.0 — CI/CD paralelo y fixes del dashboard (2026-02-27)

### Corregido

- **Comparador sin resultados:** fuzzy matching con umbral 70 fallaba para nombres largos. Reemplazado por SQL LIKE multi-palabra (0.02s vs 0.64s).
- **Búsqueda solo Mercadona:** `buscar_productos()` sin `ORDER BY` devolvía siempre los IDs más bajos. Añadido `ROW_NUMBER() OVER (PARTITION BY supermercado)`.
- **Distribución de precios ilegible:** layouts en columnas 50/50 con sidebar → labels cortados. Cambiado a full-width con expander.
- **Fechas en formato ISO:** corregido con `xaxis_tickformat='%d/%m/%Y'` y `hovertemplate`.
- **Error con un solo punto de datos:** gráfico de histórico fallaba con un solo registro.
- **`KeyError: fecha_captura`:** alias de columna incorrecto en `obtener_historico_precios()`.

### Añadido

- **`run_scraper.py`** con flags `--export-csv` y `--skip-db` para CI/CD.
- **`scraper_semanal.yml`** reescrito: 5 jobs paralelos independientes + job de merge. Tiempo total: ~64 min (vs ~96 min secuencial).
- Métrica "Días de datos" en el dashboard principal.
- `buscar_para_comparar()` con tabla resumen por supermercado y diferencias porcentuales.

### Cambiado

- Histogramas: opacidad reducida a 0.45, línea de mediana con fondo blanco.
- Gráfico comparador: barras horizontales con etiquetas de precio y diferencial porcentual.

---

## v1.0.0 — Versión inicial (2026-02-19)

### Añadido

- Scrapers funcionales para Mercadona, Carrefour, Dia, Alcampo y Eroski.
- Base de datos SQLite con tablas `productos`, `precios`, `equivalencias` y `favoritos`.
- Dashboard Streamlit con 4 páginas: principal, histórico, comparador y favoritos.
- GitHub Actions para ejecución semanal (lunes 7:00 AM, secuencial).
- Sistema de cookies con `cookie_manager.py` (obtención automática para Dia).
- `main.py` como orquestador secuencial de todos los scrapers.
- `product_matcher.py` con fuzzy matching vía RapidFuzz.
