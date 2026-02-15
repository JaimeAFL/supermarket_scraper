# Arquitectura técnica

Documento técnico que explica cómo funciona internamente el proyecto
Supermarket Price Tracker.

## Visión general

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py                                   │
│                   (orquestador principal)                         │
├─────────┬─────────┬─────────┬──────────┬────────────────────────┤
│Mercadona│Carrefour│   Dia   │ Alcampo  │  Eroski                │
│ scraper │ scraper │ scraper │ scraper  │  scraper               │
├─────────┴─────────┴─────────┴──────────┴────────────────────────┤
│                    requests + APIs internas                       │
├─────────────────────────────────────────────────────────────────┤
│                    database/db_manager.py                         │
│                    (SQLite - supermercados.db)                    │
├─────────────────────────────────────────────────────────────────┤
│                    matching/product_matcher.py                    │
│                    (equivalencias entre supermercados)            │
├─────────────────────────────────────────────────────────────────┤
│                    dashboard/app.py (Streamlit)                  │
│                    (visualización web interactiva)               │
└─────────────────────────────────────────────────────────────────┘
```

## Flujo de datos

### 1. Extracción (Scrapers)

Cada scraper en `scraper/` sigue el mismo patrón:

1. Conecta con la API interna del supermercado usando `requests`.
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
| Categoria | str | Categoría del supermercado |
| Supermercado | str | Nombre del supermercado |
| Url | str | URL del producto |
| Url_imagen | str | URL de la imagen |

### 2. Almacenamiento (Base de datos)

`database/db_manager.py` recibe el DataFrame y hace dos cosas:

- **Upsert en `productos`:** Si el producto no existe (por `id_externo` + `supermercado`),
  lo crea. Si ya existe, actualiza sus datos (nombre, categoría, etc.).
- **Insert en `precios`:** Siempre inserta un nuevo registro con el precio actual
  y la fecha/hora. Esta tabla crece con cada ejecución y forma el histórico.

### 3. Equivalencias (Matching)

`matching/product_matcher.py` vincula productos de distintos supermercados
que son el mismo artículo. Ofrece dos modos:

- **Manual:** El usuario define las equivalencias desde el dashboard.
- **Automático:** Usa `rapidfuzz` para comparar nombres de productos.
  Con un umbral alto (85+), funciona bien para marcas conocidas.

### 4. Visualización (Dashboard)

`dashboard/app.py` es una app Streamlit con tres páginas:

- **Histórico:** Gráfico temporal de un producto individual.
- **Comparador:** Gráfico superpuesto del mismo producto en varios supermercados.
- **Favoritos:** Lista de seguimiento rápido con mini gráficos.

## Modelo de datos (SQLite)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  productos   │     │   precios    │     │  equivalencias   │
├──────────────┤     ├──────────────┤     ├──────────────────┤
│ id (PK)      │◄───┐│ id (PK)      │     │ id (PK)          │
│ id_externo   │    ││ producto_id  │────►│ nombre_comun     │
│ nombre       │    │ │ precio       │     │ producto_id (FK) │
│ supermercado │    │ │ precio_unid. │     └──────────────────┘
│ categoria    │    │ │ fecha_captura│
│ formato      │    │ └──────────────┘     ┌──────────────────┐
│ url          │    │                      │   favoritos      │
│ url_imagen   │    │                      ├──────────────────┤
│ fecha_creac. │    └──────────────────────│ producto_id (FK) │
│ fecha_actual.│                           │ fecha_creacion   │
└──────────────┘                           └──────────────────┘
```

Relaciones clave:
- `precios.producto_id` → `productos.id` (muchos precios por producto)
- `equivalencias.producto_id` → `productos.id` (muchos productos por grupo)
- `favoritos.producto_id` → `productos.id` (un favorito por producto)

## APIs de supermercados

### Mercadona

- **Base URL:** `https://tienda.mercadona.es/api/`
- **Autenticación:** Ninguna (API pública).
- **Flujo:** GET `/categories/` → lista de IDs → GET `/categories/{id}` por cada una.
- **Rate limit:** `time.sleep(1)` entre peticiones.

### Carrefour

- **Base URL:** `https://www.carrefour.es/cloud-api/`
- **Autenticación:** Cookie de sesión (header `Cookie`).
- **Flujo:** GET árbol de categorías → navegar 3 niveles → GET productos con paginación
  (offset de 24 en 24, parar cuando se repiten productos).
- **Rate limit:** `time.sleep(1)` entre peticiones.

### Dia

- **Base URL:** `https://www.dia.es/api/`
- **Autenticación:** Cookie de sesión (header `Cookie`).
- **Flujo:** GET menú → función recursiva para navegar children → extraer productos
  de cada nodo hoja.
- **Rate limit:** `time.sleep(1)` entre peticiones.

## Automatización

### GitHub Actions

El workflow `.github/workflows/scraper_diario.yml` ejecuta `main.py`
diariamente a las 7:00 AM (hora española):

1. Instala Python 3.11 y dependencias.
2. Crea `.env` desde los GitHub Secrets.
3. Ejecuta `python main.py`.
4. Hace commit automático de `database/supermercados.db` y los logs.

### Ejecución local

```bash
python main.py          # Scraping completo
streamlit run dashboard/app.py  # Dashboard
```

## Estructura de carpetas

```
supermarket-price-tracker/
├── .github/workflows/    # Automatización CI/CD
├── .devcontainer/        # Config para GitHub Codespaces
├── scraper/              # Scrapers de cada supermercado
├── database/             # SQLite: esquema, CRUD, archivo .db
├── matching/             # Equivalencias entre supermercados
├── dashboard/            # App web Streamlit
│   ├── pages/            # Subpáginas del dashboard
│   └── utils/            # Funciones auxiliares (gráficos)
├── export/               # Backups Excel
├── logs/                 # Logs de ejecución
├── docs/                 # Documentación del proyecto
└── tests/                # Tests unitarios
```
