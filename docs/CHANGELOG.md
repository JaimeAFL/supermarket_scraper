# Changelog

Registro de todos los cambios realizados en Supermarket Price Tracker.

---

## v5.0.0 — API REST y estabilidad de base de datos (2026-04-12)

Versión mayor con una nueva capa API REST completa (FastAPI) y múltiples correcciones de robustez en la base de datos y el pipeline de CI/CD.

### Añadido

#### API REST con FastAPI

- **`api/`** — Nueva capa de API REST con 25 endpoints bajo el prefijo `/api/v1/`:
  - `api/main.py`: app FastAPI con CORS, rate limiter (SlowAPI, 60 req/min por IP) y gestión de ciclo de vida de la conexión DB.
  - `api/dependencies.py`: inyección de dependencia `get_db()` (reutiliza `DatabaseManager`) y `verify_api_key()` para autenticación opcional por API key.
  - `api/schemas.py`: modelos Pydantic para todas las respuestas.
  - `api/routers/productos.py`: `GET /api/v1/productos` (lista paginada), `GET /api/v1/productos/buscar` (búsqueda inteligente), `GET /api/v1/productos/{id}` (detalle).
  - `api/routers/precios.py`: `GET /api/v1/productos/{id}/precios` (histórico de precios).
  - `api/routers/comparador.py`: `GET /api/v1/comparar` (tabla por supermercado), `GET /api/v1/productos/{id}/alternativa` (alternativa más barata).
  - `api/routers/favoritos.py`: `GET / POST / DELETE /api/v1/favoritos`.
  - `api/routers/listas.py`: CRUD completo — `GET / POST /api/v1/listas`, `GET / PUT / DELETE /api/v1/listas/{id}`, `POST /api/v1/listas/{id}/duplicar`, `POST / PUT / DELETE /api/v1/listas/{id}/productos/{producto_id}`, `GET /api/v1/listas/{id}/cesta`.
  - `api/routers/envios.py`: `GET /api/v1/envios`, `GET /api/v1/envios/{supermercado}`.
  - `api/routers/estadisticas.py`: `GET /api/v1/estadisticas`, `GET /api/v1/categorias`.
  - `api/routers/rutas.py`: `POST /api/v1/rutas/geocodificar`, `POST /api/v1/rutas/supermercados-cercanos`, `POST /api/v1/rutas/optimizar`.
- **Swagger UI** disponible en `http://localhost:8000/docs`. **ReDoc** en `http://localhost:8000/redoc`.

#### Selección manual de scrapers en CI/CD

- `workflow_dispatch` acepta el parámetro `scrapers` (p. ej. `mercadona,carrefour` o `todos`). Cada job tiene una condición `if` que lo salta si no está incluido, permitiendo re-ejecutar scrapers concretos sin lanzar el pipeline completo.

### Corregido

#### Base de datos

- **`fix(db): replace ON CONFLICT upsert with SELECT+INSERT/UPDATE`** — El upsert de `guardar_productos()` pasó de `ON CONFLICT DO UPDATE` a un patrón SELECT + INSERT/UPDATE explícito, necesario porque PostgreSQL requiere el índice UNIQUE antes de compilar la cláusula `ON CONFLICT`. Ahora funciona correctamente en bases de datos recién creadas o migradas.
- **`fix(init_db): add missing UNIQUE constraint on productos(id_externo, supermercado)`** — Se añadió la restricción UNIQUE que el upsert requiere y que faltaba en el schema original.
- **`fix(db): expose silent errors and prevent psycopg2 transaction cascade`** — Los errores de psycopg2 en `guardar_productos()` provocaban que el cursor quedara en estado de error, haciendo fallar todas las operaciones posteriores de la misma conexión. Ahora se hace `rollback()` explícito y se re-lanza la excepción.
- **`fix(init_db): cast attname to text for pg_index array comparison`** — La consulta de migración automática que detecta columnas faltantes fallaba en algunas versiones de PostgreSQL por incompatibilidad de tipos en el array `pg_index`. Corregido con `::text`.

#### Dashboard

- **`fix: chart dates showing 1970`** — Las fechas de los gráficos de histórico aparecían como 01/01/1970 en instalaciones con Pandas 2.0+. La causa era que `datetime64[us]` no se convierte automáticamente a timestamp Unix en nanosegundos como hacía Pandas 1.x. Corregido con conversión explícita antes de pasar los datos a Plotly.

#### CI/CD

- **Carrefour sin Playwright** — El scraper de Carrefour se migró a llamadas de API directas, eliminando la dependencia de Playwright en su job de CI/CD (más rápido y estable).
- **Eroski timeout ampliado** — El timeout del job de Eroski pasó de 80 a 120 minutos para absorber variaciones en tiempos de scraping con scroll infinito.

### Cambiado

- **`requirements.txt`**: añadidos `fastapi`, `uvicorn[standard]`, `slowapi`, `python-multipart`.
- **`docs/arquitectura.md`**: diagrama y estructura de archivos actualizados con la capa `api/`; nueva sección REST API; descripción actualizada del mecanismo de upsert.
- **`docs/ci_cd.md`**: `workflow_dispatch` con selección de scrapers documentado; timeouts actualizados.
- **`README.md`**: roadmap, estructura, tecnologías y características técnicas actualizados.

---

## v4.0.0 — Listas de la compra, envíos y ruta óptima (2026-03-19)

Versión mayor con tres nuevas funcionalidades: gestión de listas reutilizables, información de costes de envío por supermercado y cálculo de ruta óptima entre tiendas físicas.

### Añadido

#### Listas de la compra reutilizables (Paso 1)

- **Tabla `listas`** en PostgreSQL: `nombre`, `etiqueta`, `notas`, `fecha_creacion`, `fecha_actualizacion`. Soporta 7 etiquetas predefinidas (Compra semanal, Compra mensual, Barbacoa, Cumpleaños, Bebé, Dieta, Otra).
- **Tabla `lista_productos`** con FK a `listas` (CASCADE DELETE) y FK a `productos`. Restricción `UNIQUE(lista_id, producto_id)`.
- **12 métodos nuevos en `DatabaseManager`**: `crear_lista`, `obtener_listas`, `obtener_lista_detalle`, `añadir_producto_a_lista`, `quitar_producto_de_lista`, `actualizar_cantidad_lista`, `eliminar_lista`, `renombrar_lista`, `duplicar_lista`, `cargar_lista_en_cesta`, `obtener_envios`, `obtener_envio_supermercado`.
- **Página `5_Listas.py`**: UI completa para crear, ver, editar, duplicar y eliminar listas. Desglose por supermercado, buscador de productos, exportación a PDF y enlaces de email (Gmail, Outlook, Yahoo), carga directa en cesta.
- **Botón "Añadir a lista"** en `2_Comparador.py` (junto a los botones de cesta/favoritos), `1_Historico_precios.py` (en el detalle de producto) y `app.py` (en los resultados de búsqueda rápida).

#### Información de envíos (Paso 2)

- **Tabla `envios`** con datos de los 7 supermercados: `coste_envio`, `umbral_gratis`, `pedido_minimo`, `notas`, `fecha_verificacion`. Datos iniciales con `ON CONFLICT DO NOTHING`.
- **Desglose de envíos en `4_Cesta.py`**: para cada supermercado en la cesta, muestra el coste de envío, avisa si no se cumple el pedido mínimo, indica cuánto falta para envío gratis y calcula el coste total real (productos + envíos).

#### Ruta óptima entre tiendas (Paso 3)

- **`routing.py`** — Nuevo módulo con tres funciones:
  - `geocodificar(direccion, pais)` — Nominatim (OpenStreetMap), sin API key. Respeta límite 1 req/seg.
  - `buscar_supermercados_cercanos(lat, lon, supermercados, radio_metros)` — Overpass API, busca nodos y ways, devuelve solo la tienda más cercana por cadena.
  - `calcular_ruta_optima(origen, paradas, modo)` — OSRM `/trip` con TSP. Devuelve paradas reordenadas, geometría GeoJSON, tramos y métricas.
- **Sección "Ruta de compra" en `4_Cesta.py`**: input de dirección, selector de modo (coche/a pie/bici), slider de radio. Mapa Folium interactivo con marcador de casa, marcadores de tienda con color por supermercado y polilínea de ruta. Métricas de distancia, duración y número de tiendas. Caché en `st.session_state['ruta_cache']`.
- **`folium>=0.15.0`** y **`streamlit-folium>=0.18.0`** añadidos a `requirements.txt`.

#### Tests unitarios (Pasos 1.5, 2.4, 3.2)

- **`tests/test_listas.py`** — 24 tests para todos los métodos de listas y envíos. Fixture `mock_db` con `psycopg2` mockeado, sin dependencia de PostgreSQL real.
- **`tests/test_routing.py`** — 19 tests para `geocodificar`, `buscar_supermercados_cercanos`, `calcular_ruta_optima` y `_distancia_haversine`. Mocks de `requests.get` y `requests.post`.

### Cambiado

- **`database/init_db.py`**: añadidas tablas `listas`, `lista_productos`, `envios` con índices e inserts iniciales de datos de envío.
- **`dashboard/utils/styles.py`**: color de Condis actualizado a `#C0392B` (dict Python y variable CSS).
- **`dashboard/pages/4_Cesta.py`**: desglose por supermercado reescrito para mostrar envíos; añadida sección de ruta óptima con mapa Folium.
- **`docs/arquitectura.md`**: modelo de datos actualizado con nuevas tablas; módulo `routing.py` documentado; estructura de archivos actualizada a 6 páginas.
- **`README.md`**: descripción, roadmap, estructura de archivos y tabla de tecnologías actualizados a v4.0.0.

---

## v3.0.0 — Migración a PostgreSQL y Aiden (2026-03-13)

Migración completa de la capa de base de datos de SQLite a PostgreSQL alojado en Aiden.

### Añadido

- **`DATABASE_URL`** como variable de entorno obligatoria. Sustituye a `SUPERMARKET_DB_PATH`. Acepta cualquier cadena de conexión PostgreSQL estándar.
- **Secret `DATABASE_URL`** en GitHub Actions: el job de merge lo inyecta en el entorno antes de ejecutar `import_results.py`.

### Cambiado

- **`database/database_db_manager.py`**: reemplazado `sqlite3` por `psycopg2`. Placeholders `?` migrados a `%s`. Eliminados `PRAGMA`, `check_same_thread` y `sqlite3.Row`. Conexión gestionada por pool.
- **`database/init_db.py`**: sintaxis `CREATE TABLE` migrada a PostgreSQL (`SERIAL` en lugar de `AUTOINCREMENT`, tipos de columna ajustados). Eliminada creación de directorio y archivo `.db`.
- **`scraper_semanal.yml`**: el job de merge (`guardar-en-db`) ya no ejecuta `git add database/*.db && git commit && git push`. La base de datos persiste en Aiden independientemente del pipeline; no se versiona en el repositorio.
- **`example.env`**: eliminada `SUPERMARKET_DB_PATH`; añadida `DATABASE_URL`.
- **`tests/test_db.py`**: fixture `db_temporal` reescrita para conectar a la BD de test vía `DATABASE_URL`. Si la variable no está definida, los tests de base de datos se saltan con `pytest.skip()`. Limpieza de datos entre tests con `DELETE` en lugar de borrar el archivo `.db`.
- **`.gitignore`**: eliminada la entrada `*.db`; añadida `export/` para excluir los CSVs temporales de los scrapers.
- **`requirements.txt`**: añadido `psycopg2-binary`; eliminado cualquier driver exclusivo de SQLite.
- **README** y documentación técnica actualizados para reflejar el nuevo stack.

### Eliminado

- `database/supermercados.db` — eliminado del repositorio. Los datos persisten en Aiden.
- Variable de entorno `SUPERMARKET_DB_PATH`.

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

- **URLs silenciosamente descartadas**: `guardar_productos()` en `database_db_manager.py` normalizaba inconsistentemente los nombres de columna `Url` vs `URL`. Ahora se estandariza `Url` en todos los scrapers y en el guardado.
- **Fallback de URL**: cuando `url` está vacía, se construye automáticamente a partir de `id_externo` + patrones de URL conocidos por supermercado.
- **Flag `--single-process` eliminado**: este flag de Chromium rompía silenciosamente `page.on("response")` en Playwright, devolviendo 0 productos. Todos los scrapers Playwright usan ahora solo `--disable-dev-shm-usage`, `--no-sandbox`, `--disable-gpu`.
- **Orden de scrapers optimizado**: `main.py` ejecuta primero los scrapers por API (Mercadona, Dia, Consum, Condis) y después los de Playwright (Carrefour, Alcampo, Eroski) para minimizar el impacto de fallos de memoria.
- **Typo en `main.py` línea 49**: `.` → `,`.
- **Caracteres españoles corregidos** en textos del dashboard (tildes, ñ).

### Cambiado

- **SMTP eliminado**: reemplazado completamente por enlaces de composición web. No requiere configuración de servidor de correo.
- **Múltiples mejoras de UX** en páginas Histórico, Comparador, Favoritos y Cesta.
- **README reescrito** para audiencia técnica y no técnica.

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
- Migración automática en `init_db.py`: detecta columnas faltantes, las crea y normaliza los productos existentes.
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

Resolución de 6 bugs del dashboard y rediseño del workflow de GitHub Actions para ejecución paralela.

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
