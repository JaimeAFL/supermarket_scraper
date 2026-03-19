# Arquitectura técnica

Documento técnico que explica cómo funciona internamente el proyecto Supermarket Price Tracker.

## Visión general

```
┌──────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions (CI/CD)                             │
│              7 jobs paralelos + merge final                           │
├───────┬──────────┬──────┬─────────┬──────────┬────────┬──────────────┤
│Mercad.│Carrefour │ Dia  │ Alcampo │  Eroski  │ Consum │  Condis      │
│ ~30s  │ ~15 min  │ ~1m  │ ~17 min │  ~62 min │ ~2 min │  ~5 min      │
│ API   │Playwright│ API  │Playwright│Playwright│ API    │  API Empathy │
├───────┴──────────┴──────┴─────────┴──────────┴───────────────────────┤
│                    run_scraper.py / main.py                           │
│                    → export CSV / guardar en DB                       │
├──────────────────────────────────────────────────────────────────────┤
│                    normalizer.py                                      │
│                    Método 1: reglas de posición por supermercado      │
│                    Método 2: taxonomía de 28 categorías               │
│                    Diccionario: 1.480 marcas (marcas.json)            │
│                    Formato: conversiones de unidades                  │
│                    Precio unitario: €/L, €/kg, €/ud                  │
├──────────────────────────────────────────────────────────────────────┤
│                    database_db_manager.py                             │
│                    PostgreSQL (Aiden) + búsqueda inteligente          │
│                    Fallback de URL por id_externo + patrón conocido   │
├──────────────────────────────────────────────────────────────────────┤
│                    product_matcher.py                                 │
│                    Equivalencias cross-retailer (rapidfuzz + SQL)     │
├──────────────────────────────────────────────────────────────────────┤
│                    routing.py                                         │
│                    Nominatim (geocodificación) · Overpass (tiendas)  │
│                    OSRM /trip (ruta óptima TSP)                      │
├──────────────────────────────────────────────────────────────────────┤
│                    app.py (Streamlit)                                 │
│                    6 vistas: métricas, histórico, comparador,        │
│                    favoritos, cesta (envíos + ruta), listas          │
└──────────────────────────────────────────────────────────────────────┘
```

## Estructura de archivos

```
supermarket_scraper/
├── .github/workflows/
│   └── scraper_semanal.yml       # CI/CD: scrapers en paralelo + merge a PostgreSQL
├── database/
│   ├── init_db.py                # Schema + migración automática (incluye listas, envíos)
│   └── database_db_manager.py    # CRUD, búsqueda inteligente, upsert, listas, envíos
├── scraper/
│   ├── mercadona.py              # Scraper Mercadona (API REST)
│   ├── carrefour.py              # Scraper Carrefour (Playwright)
│   ├── dia.py                    # Scraper Dia (API + cookie automática)
│   ├── alcampo.py                # Scraper Alcampo (Playwright)
│   ├── eroski.py                 # Scraper Eroski (Playwright)
│   ├── consum.py                 # Scraper Consum (API REST)
│   ├── condis.py                 # Scraper Condis (API Empathy)
│   └── cookie_manager.py         # Gestión y obtención automática de cookies
├── matching/
│   ├── normalizer.py             # Motor NLP: tipo, marca, categoría, formato
│   ├── marcas.json               # Diccionario de 1.480 marcas
│   └── product_matcher.py        # Matching cross-retailer con RapidFuzz
├── dashboard/
│   ├── app.py                    # Dashboard principal (métricas + búsqueda)
│   ├── pages/
│   │   ├── 1_Historico_precios.py        # Página: evolución temporal de precios
│   │   ├── 2_Comparador.py               # Página: comparador por precio unitario
│   │   ├── 3_Favoritos.py                # Página: lista de seguimiento
│   │   ├── 4_Cesta.py                    # Página: cesta + envíos + ruta óptima
│   │   └── 5_Listas.py                   # Página: listas reutilizables + exportación
│   └── utils/
│       ├── components.py                 # Componentes UI reutilizables
│       ├── charts.py                     # Gráficos Plotly
│       ├── styles.py                     # Estilos CSS del dashboard
│       └── export.py                     # Exportación, PDF y enlaces de email
├── tests/
│   ├── test_listas.py            # Tests unitarios: listas y envíos (24 tests)
│   └── test_routing.py           # Tests unitarios: routing con mocks (19 tests)
├── routing.py                    # Geocodificación + búsqueda tiendas + ruta óptima
├── main.py                       # Orquestador: todos los scrapers secuencial
├── run_scraper.py                # Ejecución individual + flags --export-csv, --skip-db
├── import_results.py             # Merge de CSVs paralelos → DB
├── requirements.txt
├── example.env
└── README.md
```

## Flujo de datos

### 1. Extracción (Scrapers)

Cada scraper sigue el mismo patrón:

1. Conecta con la API interna o la web del supermercado.
2. Obtiene el árbol de categorías.
3. Itera cada categoría para extraer todos los productos.
4. Devuelve un `pd.DataFrame` con columnas normalizadas.

Las columnas del DataFrame son siempre las mismas: `Id`, `Nombre`, `Precio`, `Precio_por_unidad`, `Formato`, `Categoria`, `Supermercado`, `Url`, `Url_imagen`.

#### Tiempos de ejecución

| Scraper | Tiempo | Productos | Método |
|---|---|---|---|
| Mercadona | ~30 seg | ~4.300 | API REST pública |
| Carrefour | ~15 min | ~2.400 | Playwright + interceptación XHR |
| Dia | ~1 min | ~3.200 | API REST + cookie automática |
| Alcampo | ~17 min | ~10.000 | Playwright + interceptación XHR |
| Eroski | ~62 min | ~10.000 | Playwright + scraping DOM |
| Consum | ~2 min | ~9.100 | API REST pública |
| Condis | ~4–6 min | ~5.800 | API Empathy (REST, sin Playwright) |

#### Gestión de memoria en ejecución local (`main.py`)

El orden de scrapers está optimizado: API primero (sin overhead de Chromium), Playwright después ordenados de menor a mayor carga. Entre cada scraper:

1. `gc.collect()` — libera objetos Python no referenciados.
2. `_matar_chromium_huerfano()` vía `pkill` — libera procesos Chromium que hayan quedado activos tras un crash.
3. Segundo `gc.collect()`.

Cada scraper corre en un `ProcessPoolExecutor` con timeout configurable (ver `guia_env.md`). Si el timeout se supera, el proceso se cancela y el orquestador continúa con el siguiente.

### 2. Normalización

Antes de llegar a la base de datos, cada producto pasa por `normalizer.py`, que extrae:

- **Tipo de producto** — qué es el producto ("Leche entera", "Café molido").
- **Marca** — detectada por reglas de posición específicas de cada supermercado + diccionario de 1.480 marcas como respaldo.
- **Categoría normalizada** — clasificación automática en 28 categorías canónicas.
- **Formato normalizado** — conversiones de unidades (ml→L, g→kg) y extracción de cantidad.
- **Precio unitario calculado** — `calcular_precio_unitario()` devuelve precio en €/L, €/kg o €/ud.

Ver `normalizacion.md` para el detalle completo.

### 3. Almacenamiento (Base de datos)

`database_db_manager.py` recibe el DataFrame ya normalizado y conecta a PostgreSQL mediante la variable de entorno `DATABASE_URL`:

- **Upsert en `productos`:** Si el producto no existe (por `id_externo` + `supermercado`), lo crea. Si ya existe, actualiza sus campos normalizados.
- **Insert en `precios`:** Un registro por producto por día. Deduplicación automática por fecha si el scraper se ejecuta más de una vez al día.
- **Fallback de URL:** Si `Url` llega vacía, construye la URL a partir de `id_externo` + el patrón de URL conocido para cada supermercado.

La base de datos está alojada en Aiden y no se versiona en el repositorio. No se hace ningún commit de datos al finalizar el pipeline.

#### Migración automática

`init_db.py` detecta columnas faltantes (`tipo_producto`, `marca`, `nombre_normalizado`, `categoria_normalizada`) y las crea. Después normaliza los productos existentes. Permite actualizar el esquema sin intervención manual.

### 4. Búsqueda inteligente

Las búsquedas del dashboard usan dos niveles con `UNION ALL`:

1. **Prioridad 1 — tipo_producto:** `nombre_normalizado LIKE 'leche%'` → productos cuyo tipo ES leche.
2. **Prioridad 2 — nombre completo:** `nombre LIKE '%leche%'` → productos que mencionan leche.

`ROW_NUMBER() OVER (PARTITION BY supermercado)` distribuye resultados equitativamente entre cadenas.

### 5. Equivalencias

`product_matcher.py` vincula productos de distintos supermercados que son el mismo artículo. Dos modos:

- **Manual:** el usuario define equivalencias desde el comparador del dashboard.
- **Automático:** búsqueda por `tipo_producto` como base, con RapidFuzz opcional para refinar puntuación.

### 6. Visualización (Dashboard)

`app.py` es una app Streamlit multipágina con seis vistas:

- **Principal:** métricas globales, distribución de precios (histograma con mediana), búsqueda rápida con filtro de categoría y botón "Añadir a lista".
- **Histórico:** gráfico temporal de un producto con min/max/media y evolución semanal. Incluye botón "Añadir a lista".
- **Comparador:** tabla resumen por supermercado (más barato, mediana, más caro, diferencia porcentual) + widget "Añadir a lista" por producto.
- **Favoritos:** lista de seguimiento con búsqueda integrada.
- **Cesta:** lista de la compra con desglose de envíos por supermercado (umbrales, pedido mínimo, coste real), exportación PDF/email y sección de ruta óptima entre tiendas físicas.
- **Listas:** listas de la compra reutilizables con etiquetas (semanal, barbacoa, cumpleaños…), gestión completa (crear, editar, duplicar, eliminar), exportación PDF/email y carga directa en cesta.

### 7. Routing (APIs externas gratuitas)

`routing.py` proporciona tres funciones independientes:

- **`geocodificar(direccion)`** — Llama a Nominatim (OpenStreetMap) para convertir una dirección o código postal en coordenadas. Respeta el límite de 1 req/seg con `time.sleep(1)`.
- **`buscar_supermercados_cercanos(lat, lon, supermercados, radio_metros)`** — Consulta Overpass API con una query que busca nodos y ways de los supermercados indicados dentro del radio. Devuelve solo la tienda más cercana por cadena.
- **`calcular_ruta_optima(origen, paradas, modo)`** — Llama a OSRM `/trip` con `source=first`, `destination=last`, `roundtrip=true`. Resuelve el TSP y devuelve las paradas reordenadas, geometría GeoJSON para Folium, tramos y métricas totales.

## Modelo de datos (PostgreSQL)

```
┌──────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     productos        │     │     precios      │     │  equivalencias   │
├──────────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (PK, SERIAL)      │◄───┐│ id (PK, SERIAL)  │     │ id (PK)          │
│ id_externo           │    ││ producto_id (FK) │     │ nombre_comun     │
│ nombre               │    ││ precio           │     │ prod_mercadona_id│
│ supermercado         │    ││ precio_por_unidad│     │ prod_carrefour_id│
│ categoria            │    ││ fecha_captura    │     │ prod_dia_id      │
│ formato              │    │└──────────────────┘     │ prod_alcampo_id  │
│ url                  │    │                         │ prod_eroski_id   │
│ url_imagen           │    │  ┌──────────────────┐   └──────────────────┘
│ fecha_creacion       │    │  │   favoritos      │
│ fecha_actualizacion  │    │  ├──────────────────┤
│ tipo_producto        │    └──│ producto_id (FK) │
│ marca                │       │ fecha_agregado   │
│ nombre_normalizado   │       └──────────────────┘
│ categoria_normalizada│
└──────────┬───────────┘
           │
           │         ┌─────────────────────┐     ┌──────────────────────┐
           │         │       listas        │     │       envios         │
           │         ├─────────────────────┤     ├──────────────────────┤
           │         │ id (PK, SERIAL)     │     │ id (PK, SERIAL)      │
           │         │ nombre              │     │ supermercado (UNIQUE) │
           │         │ etiqueta            │     │ coste_envio          │
           │         │ notas               │     │ umbral_gratis        │
           │         │ fecha_creacion      │     │ pedido_minimo        │
           │         │ fecha_actualizacion │     │ notas                │
           │         └────────┬────────────┘     │ fecha_verificacion   │
           │                  │                  └──────────────────────┘
           │         ┌────────▼────────────┐
           │         │  lista_productos    │
           │         ├─────────────────────┤
           └────────►│ producto_id (FK)    │
                     │ lista_id (FK)       │
                     │ cantidad            │
                     │ notas               │
                     │ fecha_agregado      │
                     │ UNIQUE(lista_id,    │
                     │        producto_id) │
                     └─────────────────────┘
```

Índices para búsqueda rápida:
- `idx_productos_tipo` → búsqueda por tipo_producto
- `idx_productos_nombre_norm` → búsqueda por nombre_normalizado
- `idx_productos_cat_norm` → filtro por categoría normalizada
- `idx_productos_marca` → filtro por marca
- `idx_lista_productos_lista` → búsqueda de productos por lista
- `idx_lista_productos_producto` → búsqueda de listas por producto

## Automatización (GitHub Actions)

El workflow `.github/workflows/scraper_semanal.yml` ejecuta los scrapers como **jobs independientes en paralelo**:

```
                      ┌─ mercadona (~30s)  ─→ mercadona.csv  ─┐
                      ├─ carrefour (~15m)  ─→ carrefour.csv  ─┤
                      ├─ dia       (~1m)   ─→ dia.csv        ─┤
Lunes 7:00 AM (España)┼─ alcampo   (~17m)  ─→ alcampo.csv   ─┼─→ merge → PostgreSQL (Aiden)
                      ├─ eroski    (~62m)  ─→ eroski.csv     ─┤
                      ├─ consum    (~2m)   ─→ consum.csv     ─┤
                      └─ condis    (~5m)   ─→ condis.csv     ─┘

Tiempo total: ~64 min (limitado por Eroski + 2 min de merge)
```

Cada job: instala dependencias → ejecuta `run_scraper.py <super> --export-csv ... --skip-db` → sube CSV como artifact. Tiene `continue-on-error: true`.

El job de merge descarga todos los artifacts y ejecuta `import_results.py export/*.csv` con normalización completa. Se ejecuta siempre (`if: always()`), incluso si algún scraper falló. No realiza ningún commit al repositorio.

## Ejecución local

```bash
# Todos los supermercados (secuencial, con timeouts por proceso)
python main.py

# Un supermercado individual → guarda en DB
python run_scraper.py mercadona

# Solo CSV, sin tocar la DB
python run_scraper.py dia --export-csv export/dia.csv --skip-db

# Importar CSVs a la DB (equivale al job de merge en CI)
python import_results.py export/*.csv

# Dashboard
streamlit run dashboard/app.py
```

## Tests

```bash
# Todos los tests (43 en total)
python -m pytest tests/ -v

# Solo tests de listas y envíos
python -m pytest tests/test_listas.py -v

# Solo tests de routing
python -m pytest tests/test_routing.py -v
```

Los tests usan `unittest.mock` para no depender de PostgreSQL real ni de las APIs externas (Nominatim, Overpass, OSRM).
