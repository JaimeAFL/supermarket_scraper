# Arquitectura técnica

Documento técnico que explica cómo funciona internamente el proyecto
Supermarket Price Tracker.

## Visión general

```
┌──────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions (CI/CD)                              │
│              5 jobs paralelos + merge final                            │
├─────────┬──────────┬─────────┬──────────┬────────────────────────────┤
│Mercadona│Carrefour │   Dia   │ Alcampo  │  Eroski                    │
│ ~30 seg │ ~15 min  │ ~1 min  │ ~17 min  │  ~62 min                   │
│ API REST│Playwright│API+Plwr │Playwright│  Playwright                │
├─────────┴──────────┴─────────┴──────────┴────────────────────────────┤
│                    run_scraper.py (por scraper)                        │
│                    → export CSV / guardar en DB                        │
├──────────────────────────────────────────────────────────────────────┤
│                    matching/normalizer.py                              │
│                    Método 1: reglas de posición por supermercado       │
│                    Método 2: taxonomía de 26 categorías                │
│                    Diccionario: 1.480 marcas (marcas.json)             │
├──────────────────────────────────────────────────────────────────────┤
│                    database/db_manager.py                              │
│                    SQLite + búsqueda inteligente por tipo_producto     │
├──────────────────────────────────────────────────────────────────────┤
│                    matching/product_matcher.py                         │
│                    Equivalencias cross-retailer (rapidfuzz + SQL)      │
├──────────────────────────────────────────────────────────────────────┤
│                    dashboard/app.py (Streamlit)                       │
│                    4 vistas: métricas, histórico, comparador, favs    │
└──────────────────────────────────────────────────────────────────────┘
```

## Flujo de datos

### 1. Extracción (Scrapers)

Cada scraper en `scraper/` sigue el mismo patrón:

1. Conecta con la API interna del supermercado.
2. Obtiene el árbol de categorías.
3. Itera cada categoría para extraer todos los productos.
4. Devuelve un `pd.DataFrame` con columnas normalizadas.

Las columnas del DataFrame son siempre las mismas:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| Id | str | ID del producto en el supermercado |
| Nombre | str | Nombre del producto |
| Precio | float | Precio actual en euros |
| Precio_por_unidad | float | Precio por kg/L |
| Formato | str | Peso, volumen, unidades |
| Categoria | str | Categoría original del supermercado |
| Supermercado | str | Nombre del supermercado |
| Url | str | URL del producto |
| Url_imagen | str | URL de la imagen |

#### Tiempos de ejecución medidos

| Scraper | Tiempo | Productos | Método |
|---------|--------|-----------|--------|
| Mercadona | ~30 seg | 4.295 | API REST pública |
| Carrefour | ~15 min | 2.378 | API + Playwright |
| Dia | ~1 min | 3.193 | API + cookie automática |
| Alcampo | ~17 min | 9.970 | API + Playwright |
| Eroski | ~62 min | 10.036 | Web scraping + Playwright |

### 2. Normalización (Motor NLP)

Antes de llegar a la base de datos, cada producto pasa por
`matching/normalizer.py` que extrae información semántica del nombre.

#### Problema que resuelve

Cada supermercado nombra los productos de forma distinta:
- Mercadona: `Leche entera Hacendado`
- Eroski: `Leche entera EROSKI, brik 1 litro`
- Alcampo: `AUCHAN Leche entera de vaca 1 l.`

Además, una búsqueda de "leche" no debería devolver "café con leche"
ni "chocolate con leche". El normalizador resuelve ambos problemas.

#### Método 1: Reglas de posición

Cada supermercado tiene un patrón de naming predecible:

```
Alcampo:    MARCA EN MAYÚSCULAS + tipo + formato
            AUCHAN Leche entera de vaca 1 l.
            ^^^^^^ → marca    ^^^^^^^^^^^^^^^^ → tipo

Eroski:     tipo + MARCA EN MAYÚSCULAS + , formato
            Leche entera EROSKI, brik 1 litro
            ^^^^^^^^^^^^ → tipo  ^^^^^^ → marca

Mercadona:  tipo + marca (de diccionario) + variante
            Leche entera Hacendado
            ^^^^^^^^^^^^ → tipo  ^^^^^^^^^ → marca
```

El diccionario `marcas.json` contiene 1.480 marcas auto-extraídas
de los datos de Alcampo y Eroski (donde la marca va en MAYÚSCULAS
y es fácil de detectar), complementadas con marcas manuales para
Mercadona, Carrefour y Dia.

#### Método 2: Taxonomía de categorías

Una vez extraído el tipo de producto, se clasifica en 26 categorías
normalizadas mediante coincidencia de prefijos:

| Tipo extraído | Categoría |
|---------------|-----------|
| Leche entera | Lácteos |
| Café molido | Cafés e infusiones |
| Chocolate con leche | Chocolates y cacao |
| Cerveza rubia | Cervezas |
| Gel de ducha | Higiene personal |

Las 26 categorías cubren: Lácteos, Bebidas, Cervezas, Vinos y licores,
Cafés e infusiones, Panadería, Galletas y bollería, Cereales y legumbres,
Pasta, Harinas, Conservas de pescado, Conservas vegetales, Aceites y vinagres,
Embutidos y fiambres, Carnes, Pescados y mariscos, Frutas y verduras,
Congelados y preparados, Huevos, Salsas y condimentos, Azúcar y edulcorantes,
Chocolates y cacao, Dulces y untables, Snacks y frutos secos,
Higiene personal, Limpieza del hogar, Bebé y Mascotas.

#### Cobertura

- **Marca extraída:** 72,6% de los 29.872 productos
- **Categoría asignada:** 44,2% (cubre alimentación e higiene; excluye
  electrónica, ropa, bricolaje y otros productos no alimentarios)

#### Resultado por producto

```python
normalizar_producto("Leche entera Hacendado", "Mercadona")
# → {
#     "tipo_producto": "Leche entera",
#     "marca": "Hacendado",
#     "nombre_normalizado": "leche entera",
#     "categoria_normalizada": "Lácteos",
# }
```

### 3. Almacenamiento (Base de datos)

`database/db_manager.py` recibe el DataFrame ya normalizado y hace:

- **Upsert en `productos`:** Si el producto no existe (por `id_externo` +
  `supermercado`), lo crea con sus campos normalizados. Si ya existe,
  actualiza nombre, categoría, tipo_producto, marca, etc.
- **Insert en `precios`:** Un registro por producto por día con precio
  y fecha. Verificación de duplicados por fecha para evitar registros
  repetidos si el scraper se ejecuta más de una vez al día.

#### Migración automática

`init_db.py` detecta si las columnas de normalización no existen
(`tipo_producto`, `marca`, `nombre_normalizado`, `categoria_normalizada`)
y las crea con `ALTER TABLE`. Después migra los productos existentes
pasándolos por el normalizador. Esto permite actualizar el código sin
tocar la base de datos manualmente.

### 4. Búsqueda inteligente

Las búsquedas del dashboard usan una estrategia de dos niveles:

1. **Prioridad 1 — tipo_producto:** `nombre_normalizado LIKE 'leche%'`
   encuentra productos cuyo tipo ES leche.
2. **Prioridad 2 — nombre completo:** `nombre LIKE '%leche%'`
   encuentra productos que mencionan leche (café con leche, etc.).

Ambos niveles se combinan con `UNION ALL` y un campo `prioridad`
que permite al dashboard separar resultados directos de menciones
secundarias. Además, `ROW_NUMBER() OVER (PARTITION BY supermercado)`
distribuye resultados equitativamente entre supermercados.

#### Ejemplo

Buscar "leche":
- **Prioridad 1 (477 resultados):** Leche entera, Leche desnatada,
  Leche sin lactosa, Leche condensada...
- **Prioridad 2 (590 resultados):** Café con leche, Chocolate con leche,
  Galletas con leche, Arroz con leche...

### 5. Equivalencias (Matching)

`matching/product_matcher.py` vincula productos de distintos supermercados
que son el mismo artículo. Ofrece dos modos:

- **Manual:** El usuario define equivalencias desde el comparador del dashboard.
- **Automático:** Usa la búsqueda por `tipo_producto` como base, y opcionalmente
  puntúa con `rapidfuzz` para refinar. La normalización previa mejora
  significativamente la calidad del matching respecto al fuzzy puro.

### 6. Visualización (Dashboard)

`dashboard/app.py` es una app Streamlit con cuatro vistas:

- **Principal:** Métricas, distribución de precios (histograma con mediana),
  búsqueda rápida con filtro de categoría.
- **Histórico:** Gráfico temporal de un producto individual con min/max/media.
- **Comparador:** Tabla resumen por supermercado (más barato, mediana, más caro,
  diferencia porcentual) + gráfico de barras horizontales.
- **Favoritos:** Lista de seguimiento con búsqueda integrada.

## Modelo de datos (SQLite)

```
┌──────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     productos        │     │     precios      │     │  equivalencias   │
├──────────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (PK)              │◄───┐│ id (PK)          │     │ id (PK)          │
│ id_externo           │    ││ producto_id (FK) ─┼────►│ nombre_comun     │
│ nombre               │    ││ precio           │     │ prod_mercadona_id│
│ supermercado         │    ││ precio_por_unidad│     │ prod_carrefour_id│
│ categoria            │    ││ fecha_captura    │     │ prod_dia_id      │
│ formato              │    │└──────────────────┘     │ prod_alcampo_id  │
│ url                  │    │                         │ prod_eroski_id   │
│ url_imagen           │    │                         └──────────────────┘
│ fecha_creacion       │    │
│ fecha_actualizacion  │    │  ┌──────────────────┐
│ tipo_producto     ◄──┼─┐  │  │   favoritos      │
│ marca                │ │  │  ├──────────────────┤
│ nombre_normalizado   │ │  └──│ producto_id (FK) │
│ categoria_normalizada│ │     │ fecha_agregado   │
└──────────────────────┘ │     └──────────────────┘
                         │
                    Campos añadidos por
                    el normalizador (v2)
```

Relaciones clave:
- `precios.producto_id` → `productos.id` (muchos precios por producto)
- `equivalencias` usa IDs externos por supermercado (no FK directos)
- `favoritos.producto_id` → `productos.id` (un favorito por producto)

Índices para búsqueda:
- `idx_productos_tipo` → búsqueda por tipo_producto
- `idx_productos_nombre_norm` → búsqueda por nombre_normalizado
- `idx_productos_cat_norm` → filtro por categoría normalizada
- `idx_productos_marca` → filtro por marca

## APIs de supermercados

### Mercadona

- **Base URL:** `https://tienda.mercadona.es/api/`
- **Autenticación:** Ninguna (API pública).
- **Flujo:** GET `/categories/` → lista de IDs → GET `/categories/{id}`.
- **Rate limit:** `time.sleep(1)` entre peticiones.
- **Tiempo:** ~30 segundos para ~4.300 productos.

### Carrefour

- **Base URL:** `https://www.carrefour.es/cloud-api/`
- **Autenticación:** Cookie de sesión (header `Cookie`).
- **Flujo:** GET árbol de categorías → navegar 3 niveles → GET productos
  con paginación (offset de 24 en 24).
- **Rate limit:** `time.sleep(1)` entre peticiones.
- **Tiempo:** ~15 minutos para ~2.400 productos.

### Dia

- **Base URL:** `https://www.dia.es/api/`
- **Autenticación:** Cookie de sesión (obtención automática con Playwright).
- **Flujo:** GET menú → función recursiva para navegar children → extraer
  productos de cada nodo hoja.
- **Rate limit:** `time.sleep(1)` entre peticiones.
- **Tiempo:** ~1 minuto para ~3.200 productos.

### Alcampo

- **Base URL:** API interna de Alcampo.
- **Autenticación:** No requiere cookie manual.
- **Flujo:** Navegación por categorías con Playwright → extracción de
  productos vía API interna.
- **Rate limit:** `time.sleep(1)` entre peticiones.
- **Tiempo:** ~17 minutos para ~10.000 productos.

### Eroski

- **Base URL:** `https://supermercado.eroski.es/`
- **Autenticación:** No requiere cookie manual.
- **Flujo:** Búsqueda por términos clave con Playwright → paginación
  por scroll → extracción de productos.
- **Rate limit:** Implicit (Playwright wait).
- **Tiempo:** ~62 minutos para ~10.000 productos.

## Automatización

### GitHub Actions (ejecución paralela)

El workflow `.github/workflows/scraper_semanal.yml` ejecuta los 5 scrapers
como **jobs independientes en paralelo**:

```
                    ┌─ mercadona ──→ mercadona.csv ─┐
                    ├─ carrefour ──→ carrefour.csv ─┤
Lunes 7:00 AM (España) ──┼─ dia ────────→ dia.csv ───────┼─→ guardar-en-db → git push
                    ├─ alcampo ───→ alcampo.csv ───┤
                    └─ eroski ────→ eroski.csv ────┘
```

Cada job:
1. Instala Python 3.11, dependencias y Playwright (si es necesario).
2. Ejecuta `run_scraper.py <super> --export-csv export/<super>.csv --skip-db`.
3. Sube el CSV como artifact de GitHub Actions.
4. Tiene `continue-on-error: true` → si falla, no bloquea a los demás.

El job final (`guardar-en-db`):
1. Descarga los 5 artifacts.
2. Ejecuta `import_results.py export/*.csv` → inserta todo en la DB
   con normalización automática.
3. Hace `git commit` y `git push` de la DB actualizada.

**Tiempo total:** ~64 minutos (lo que tarda Eroski + 2 min de merge),
frente a ~96 minutos en ejecución secuencial.

### Ejecución local

```bash
# Todos los supermercados (secuencial)
python main.py

# Un supermercado individual
python run_scraper.py mercadona

# Exportar a CSV sin tocar la DB
python run_scraper.py dia --export-csv export/dia.csv --skip-db

# Importar CSVs a la DB
python import_results.py export/*.csv

# Dashboard
streamlit run dashboard/app.py
```

## Estructura de carpetas

```
supermarket-price-tracker/
├── .github/workflows/       # CI/CD: scrapers paralelos + merge
├── .devcontainer/           # Config para GitHub Codespaces
├── scraper/                 # Scrapers de cada supermercado
├── database/                # SQLite: schema, migración, CRUD
├── matching/                # Normalización NLP + matching
│   ├── normalizer.py        # Motor de extracción tipo/marca/categoría
│   ├── marcas.json          # Diccionario de 1.480 marcas
│   └── product_matcher.py   # Matching cross-retailer
├── dashboard/               # App web Streamlit
│   ├── app.py               # Página principal
│   ├── pages/               # Subpáginas (histórico, comparador, favoritos)
│   └── utils/               # Gráficos Plotly
├── export/                  # CSVs de scrapers (CI/CD)
├── logs/                    # Logs de ejecución
├── docs/                    # Documentación del proyecto
└── tests/                   # Tests unitarios
```
