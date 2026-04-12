# Supermarket Price Tracker

Herramienta que extrae los catálogos completos de los principales supermercados españoles, normaliza los productos automáticamente y ofrece un dashboard interactivo para comparar precios, ver su evolución semanal, guardar favoritos, gestionar listas de la compra reutilizables y calcular la ruta óptima entre tiendas.

---
## Enlace a la aplicación

https://supermarketscraper-fwx9ryfjofnhpu2jyq6bnt.streamlit.app/

---

## ¿Qué hace esta aplicación?

Cada semana, de forma automática, la aplicación:

1. **Extrae** todos los productos y precios de 7 supermercados
2. **Normaliza** cada producto: detecta la marca, extrae el tipo de producto ("leche entera", "café molido") y calcula el precio por litro o por kilo para poder comparar de verdad
3. **Guarda** todo en una base de datos con histórico — así puedes ver si el precio de tu yogur favorito ha subido
4. **Actualiza** el dashboard, donde puedes buscar cualquier producto y ver al instante dónde está más barato
5. **Gestiona listas de la compra** reutilizables (semanal, barbacoa, cumpleaños...) con exportación a PDF y email
6. **Informa sobre costes de envío** de cada supermercado y calcula cuánto falta para envío gratis
7. **Calcula la ruta óptima** entre las tiendas físicas donde comprar, usando OpenStreetMap y OSRM sin API key
8. **Expone una API REST** con 25 endpoints para consultas externas (FastAPI + SlowAPI), con Swagger UI y ReDoc incluidos

---

## Cómo funciona internamente

### 1. Extracción

Cada scraper llama a la API interna o al sitio web del supermercado, recorre todas las categorías y devuelve un DataFrame con columnas normalizadas: `Id`, `Nombre`, `Precio`, `Formato`, `Supermercado`, `Url`, `Url_imagen`.

Los scrapers de Consum y Condis son completamente API-based (solo `requests`), lo que los hace más rápidos y estables que los que necesitan Playwright.

### 2. Normalización

Antes de guardar, cada producto pasa por `normalizer.py`:

- Detecta el **tipo de producto** ("leche semidesnatada") separándolo de la marca y del formato
- Identifica la **marca** por reglas de posición según el supermercado o por diccionario
- Asigna una **categoría normalizada** de entre 28 categorías canónicas
- Calcula el **precio unitario** (€/L, €/kg, €/ud) a partir del formato

### 3. Almacenamiento

Upsert en PostgreSQL: si el producto ya existe (por id externo + supermercado) se actualiza; siempre se añade un nuevo registro de precio con la fecha de hoy. Esto construye el histórico automáticamente sin intervención manual. La base de datos está alojada en Aiden y no se almacena en el repositorio.

### 4. Visualización

Dashboard Streamlit con 6 vistas:

- **Principal**: métricas globales, buscador, distribución de precios por categoría
- **Histórico**: evolución semanal del precio de cualquier producto
- **Comparador**: tabla con el precio más barato por supermercado y diferencias porcentuales
- **Favoritos**: lista guardada con seguimiento de precios
- **Cesta**: selección de productos con desglose de envíos, exportación por email y ruta óptima entre tiendas
- **Listas**: listas de la compra reutilizables con etiquetas, exportación a PDF/email y carga directa en cesta

---

## Supermercados

| Supermercado | Estado | Productos | Método de extracción | Autenticación |
|---|---|---|---|---|
| Mercadona | ✅ Funcional | ~4.300 | API REST pública | No requiere |
| Carrefour | ✅ Funcional | ~2.400 | API REST + Playwright | Cookie de sesión |
| Dia | ✅ Funcional | ~3.200 | API REST | Cookie automática |
| Alcampo | ✅ Funcional | ~10.000 | API REST + Playwright | No requiere |
| Eroski | ✅ Funcional | ~10.000 | Web scraping + Playwright | No requiere |
| Consum | ✅ Funcional | ~9.100 | API REST pública | No requiere |
| Condis | ✅ Funcional | ~5.800 | API REST pública (Empathy) | No requiere |

**Total: ~45.000 productos** con precios actualizados cada semana.

---

## Roadmap

- [x] Scrapers: Mercadona, Carrefour, Dia, Alcampo, Eroski
- [x] Scrapers: Consum, Condis
- [x] Motor de normalización NLP (tipo + marca + categoría + precio unitario)
- [x] Diccionario de 1.480 marcas
- [x] 28 categorías normalizadas
- [x] Búsqueda inteligente por tipo de producto
- [x] Base de datos PostgreSQL con histórico automático
- [x] Dashboard Streamlit (6 páginas)
- [x] Comparador por precio unitario (€/L, €/kg)
- [x] Sistema de favoritos
- [x] Cesta de la compra con exportación por email y PDF
- [x] GitHub Actions con jobs paralelos
- [x] Sistema de logging por ejecución
- [x] Gestión de procesos Chromium huérfanos
- [x] Timeouts configurables por scraper
- [x] Migración de SQLite a PostgreSQL (Aiden)
- [x] Listas de la compra reutilizables con etiquetas
- [x] Información de costes de envío por supermercado
- [x] Ruta óptima entre tiendas (Nominatim + Overpass + OSRM)
- [x] API REST para consultas externas (FastAPI, 25 endpoints, Swagger UI)

---

## Estructura del proyecto

```
supermarket_scraper/
├── .github/workflows/
│   └── scraper_semanal.yml       # CI/CD: scrapers en paralelo + merge a PostgreSQL
├── api/
│   ├── main.py                   # App FastAPI + CORS + rate limiter (SlowAPI)
│   ├── dependencies.py           # Conexión DB + autenticación API key
│   ├── schemas.py                # Modelos Pydantic de request/response
│   └── routers/
│       ├── productos.py          # GET /api/v1/productos (lista, búsqueda, detalle)
│       ├── precios.py            # GET /api/v1/productos/{id}/precios (histórico)
│       ├── comparador.py         # GET /api/v1/comparar, /alternativa
│       ├── favoritos.py          # GET / POST / DELETE /api/v1/favoritos
│       ├── listas.py             # CRUD completo /api/v1/listas
│       ├── envios.py             # GET /api/v1/envios
│       ├── estadisticas.py       # GET /api/v1/estadisticas, /categorias
│       └── rutas.py              # POST /api/v1/rutas/* (geocodificar, cercanos, optimizar)
├── scraper/
│   ├── mercadona.py              # API pública (~4.300 productos)
│   ├── carrefour.py              # API directa (~2.400 productos)
│   ├── dia.py                    # API REST, cookie automática vía Playwright
│   ├── alcampo.py                # API + Playwright (~10.000 productos)
│   ├── eroski.py                 # Web scraping + Playwright, scroll infinito
│   ├── consum.py                 # API REST pública, paginación offset/limit
│   ├── condis.py                 # API Empathy, browse por categorías (~93)
│   └── cookie_manager.py         # Gestión y verificación de cookies
├── database/
│   ├── init_db.py                # Schema + migración automática de columnas
│   └── database_db_manager.py    # CRUD, búsqueda inteligente, upsert
├── matching/
│   ├── normalizer.py             # Motor NLP: tipo / marca / categoría / precio unitario
│   ├── marcas.json               # Diccionario de 1.480 marcas
│   └── product_matcher.py        # Matching cross-retailer con RapidFuzz
├── dashboard/
│   ├── app.py                    # Dashboard principal + métricas + búsqueda
│   ├── pages/
│   │   ├── 1_Historico_precios.py        # Evolución de precio por producto
│   │   ├── 2_Comparador.py               # Comparador por precio unitario entre supermercados
│   │   ├── 3_Favoritos.py                # Lista de favoritos con alertas
│   │   ├── 4_Cesta.py                    # Cesta con envíos, exportación email/PDF y ruta óptima
│   │   └── 5_Listas.py                   # Listas reutilizables con etiquetas y exportación
│   └── utils/
│       ├── components.py                 # Helpers compartidos del dashboard
│       ├── charts.py                     # Gráficos Plotly (histogramas, líneas, barras)
│       ├── styles.py                     # Estilos CSS del dashboard
│       └── export.py                     # Generación de enlaces email y PDF
│
├── routing.py                    # Geocodificación, búsqueda de tiendas y ruta óptima
├── tests/
│   ├── test_mercadona.py         # Tests scraper Mercadona
│   ├── test_carrefour.py         # Tests scraper Carrefour
│   ├── test_dia.py               # Tests scraper Dia
│   ├── test_alcampo.py           # Tests scraper Alcampo
│   ├── test_eroski.py            # Tests scraper Eroski
│   ├── test_consum.py            # Tests scraper Consum
│   ├── test_condis.py            # Tests scraper Condis
│   ├── test_db.py                # Tests capa de base de datos
│   ├── test_normalizer.py        # Tests motor de normalización
│   ├── test_listas.py            # Tests listas y envíos (24 tests)
│   └── test_routing.py           # Tests routing con mocks de APIs externas (19 tests)
├── main.py                       # Orquestador principal (todos los scrapers)
├── run_scraper.py                # Ejecución individual + export CSV para CI/CD
├── import_results.py             # Merge de CSVs paralelos → base de datos
├── requirements.txt
├── example.env
└── README.md
```

---

## Tecnologías

| Área | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Extracción | Requests + Playwright (Chromium headless) |
| Base de datos | PostgreSQL (Aiden) |
| Dashboard | Streamlit (multi-página) + Plotly |
| API REST | FastAPI + SlowAPI (rate limiter) + uvicorn |
| Normalización | Motor NLP propio (reglas + taxonomía) |
| Matching | RapidFuzz (similitud de texto) |
| Mapas y rutas | Folium + streamlit-folium |
| Geocodificación | Nominatim (OpenStreetMap, sin API key) |
| Búsqueda de tiendas | Overpass API (OpenStreetMap, sin API key) |
| Optimización de ruta | OSRM demo server (TSP /trip, sin API key) |
| Automatización | GitHub Actions (ejecución paralela semanal) |
| Tests | pytest (tests unitarios con mocks para todos los módulos) |

---

## Características técnicas destacadas

### Motor de normalización NLP propio

Cada supermercado nombra los productos de forma distinta. "Leche Semidesnatada Hacendado 1L", "LECHE S/D 1LT HACENDADO" y "Hacendado Leche semidesnatada 1 litro" son el mismo producto. El motor los unifica:

- **Extracción de tipo de producto**: separa el tipo ("leche semidesnatada") de la marca y el formato mediante reglas de posición específicas por supermercado (Alcampo pone la marca al principio en MAYÚSCULAS; Eroski al final; Mercadona/Carrefour/Dia al final por diccionario).
- **Diccionario de 1.480 marcas** auto-extraídas de los datos reales de cada supermercado y completadas manualmente.
- **28 categorías normalizadas** asignadas automáticamente: Lácteos, Bebidas, Cafés e infusiones, Mascotas, etc.
- **Precio unitario calculado**: convierte cualquier formato (500ml, 1 litro, 250g, 6×33cl...) a €/L o €/kg para que la comparación sea siempre justa.

### Búsqueda inteligente

Buscar "leche" devuelve solo lácteos, no "café con leche" ni "chocolate con leche". La búsqueda funciona en dos niveles con `UNION ALL`: primero busca en `tipo_producto` (resultados exactos), luego en el nombre completo (menciones secundarias). Esto reduce el ruido en un 55% respecto a una búsqueda por texto plano.

### Fiabilidad del scraping

Los scrapers de Playwright (Carrefour, Alcampo, Eroski) son los más propensos a fallar por timeouts o procesos Chromium huérfanos. Se implementaron varias soluciones:

- **Limpieza automática de procesos huérfanos** (`pkill`) antes de cada scraper
- **`gc.collect()`** entre scrapers para liberar RAM (crítico en Codespaces con 4GB)
- **Timeout duro por scraper** con `ProcessPoolExecutor` y configuración por variable de entorno
- **Orden de ejecución estratégico**: API-based primero (Mercadona, Dia, Consum, Condis), Playwright después (Carrefour, Alcampo, Eroski)
- **El flag `--single-process` de Chromium rompe la interceptación de red** — documentado y evitado; solo se usan `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`

### Base de datos con histórico automático

Upsert por `(id_externo, supermercado)`: si el producto ya existe se actualizan sus datos; siempre se inserta un nuevo registro de precio con fecha. La base de datos es PostgreSQL alojada en Aiden: persiste independientemente del pipeline de CI/CD y no se versiona en el repositorio.

### API REST con FastAPI

Todos los datos son accesibles mediante una API REST con 25 endpoints agrupados en 8 módulos:

- **`/api/v1/productos`** — lista, búsqueda inteligente y detalle de producto.
- **`/api/v1/productos/{id}/precios`** — histórico de precios de un producto.
- **`/api/v1/comparar`** — comparador por precio unitario entre supermercados.
- **`/api/v1/favoritos`** — gestión de la lista de seguimiento.
- **`/api/v1/listas`** — CRUD completo de listas de la compra reutilizables.
- **`/api/v1/envios`** — costes de envío por supermercado.
- **`/api/v1/estadisticas`** — métricas globales y categorías disponibles.
- **`/api/v1/rutas`** — geocodificación, búsqueda de tiendas y optimización de ruta.

Incluye rate limiting (60 req/min por IP), CORS configurable y autenticación opcional por API key. Swagger UI disponible en `/docs` y ReDoc en `/redoc`.

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### CI/CD con jobs paralelos

Los scrapers corren en paralelo como jobs independientes en GitHub Actions. Si uno falla, los demás se guardan igualmente. El job de merge importa todos los CSVs directamente a PostgreSQL sin hacer commit de base de datos al repositorio.

El `workflow_dispatch` permite elegir qué scrapers ejecutar al lanzar manualmente (campo `scrapers`: `mercadona,carrefour` o `todos`).

```
Job Mercadona (~30s)   ─┐
Job Carrefour (~15m)   ─┤
Job Dia       (~1m)    ─┤
Job Alcampo   (~17m)   ─┼─→ Merge → PostgreSQL (Aiden)
Job Eroski    (~62m)   ─┤
Job Consum    (~5m)    ─┤
Job Condis    (~6m)    ─┘
```

---

## Instalación

### Requisitos previos

- Python 3.9 o superior
- Git
- Acceso a la instancia PostgreSQL (variable `DATABASE_URL`)

### Pasos

**1. Clona el repositorio:**
```bash
git clone https://github.com/tu-usuario/supermarket_scraper.git
cd supermarket_scraper
```

**2. Crea y activa un entorno virtual:**
```bash
python -m venv venv

# Linux / Mac / Codespaces
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Instala las dependencias:**
```bash
pip install -r requirements.txt
```

**4. Instala Playwright** (necesario para Carrefour, Dia, Alcampo y Eroski):
```bash
playwright install chromium
playwright install-deps chromium
```

**5. Configura las variables de entorno:**
```bash
cp example.env .env
```
Edita el archivo `.env` y añade tu `DATABASE_URL`. Consulta `docs/guia_env.md` para las instrucciones detalladas.

**6. Inicializa la base de datos:**
```bash
python database/init_db.py
```

**7. Ejecuta los scrapers:**
```bash
# Todos los supermercados
python main.py

# Un supermercado individual
python run_scraper.py mercadona
python run_scraper.py consum
python run_scraper.py condis
```

**8. Lanza el dashboard:**
```bash
streamlit run dashboard/app.py
```

---

## Configuración de cookies

La mayoría de scrapers no necesitan configuración:

- **Mercadona, Alcampo, Eroski, Consum, Condis**: sin cookies, sin autenticación.
- **Dia**: `COOKIE_DIA` se obtiene automáticamente con Playwright desde `cookie_manager.py`.
- **Carrefour**: el scraper usa Playwright con interceptación de red. `COOKIE_CARREFOUR` se mantiene como fallback.

### En GitHub Actions / Codespaces

Configura las variables como Secrets en tu repositorio:

`Settings → Secrets and variables → Actions → New repository secret`

---

## Ejecución automática

El workflow de GitHub Actions se dispara cada lunes a las 7:00 AM (hora española) y también puede lanzarse manualmente desde la pestaña Actions.

Cada scraper corre como job independiente con `continue-on-error: true`. El job final descarga todos los CSVs e importa los datos directamente en PostgreSQL con normalización completa.

---

## Documentación adicional

- `docs/arquitectura.md`: arquitectura técnica, flujo de datos y API REST
- `docs/api_supermercados.md`: estrategia de extracción por supermercado
- `docs/normalizacion.md`: motor de normalización (tipo, marca, formato, categoría)
- `docs/ci_cd.md`: pipeline semanal en GitHub Actions con selección manual
- `docs/guia_env.md`: configuración de variables de entorno
- `docs/CHANGELOG.md`: historial de cambios versión a versión
- Swagger UI interactivo: `http://localhost:8000/docs` (con la API en marcha)

---

## Licencia

MIT. Consulta el archivo `LICENSE` para más detalles.

## Disclaimer

Proyecto educativo y de uso personal. Los datos extraídos son de acceso público. Consulta los términos de uso de cada supermercado antes de usar esta herramienta. Se recomienda usar pausas entre peticiones para no sobrecargar los servidores.
