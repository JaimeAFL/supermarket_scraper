# Supermarket Price Tracker

Comparador y rastreador de precios de supermercados en España. Extrae datos de las APIs internas de los principales supermercados, normaliza los productos con un motor NLP propio, almacena un histórico de precios en base de datos y ofrece un dashboard interactivo para comparar precios entre cadenas.

## Supermercados soportados

| Supermercado | Estado | Productos | Método | Autenticación |
|---|---|---|---|---|
| Mercadona | ✅ Funcional | ~4.300 | API REST pública | No requiere |
| Carrefour | ✅ Funcional | ~2.400 | API REST + Playwright | Cookie de sesión |
| Dia | ✅ Funcional | ~3.200 | API REST | Cookie automática (Playwright) |
| Alcampo | ✅ Funcional | ~10.000 | API REST + Playwright | No requiere |
| Eroski | ✅ Funcional | ~10.000 | Web scraping + Playwright | No requiere |

**Total: ~30.000 productos** con precios actualizados semanalmente.

## Tecnologías

**Extracción:** Python, Requests, Playwright, Pandas

**Normalización:** Motor NLP propio (reglas de posición + taxonomía de categorías), diccionario de 1.480 marcas auto-extraídas

**Base de datos:** SQLite con migración automática de esquema

**Dashboard:** Streamlit (multi-página), Plotly

**Automatización:** GitHub Actions con jobs paralelos (5 scrapers simultáneos)

**Matching:** RapidFuzz (similitud de texto) + búsqueda inteligente por tipo de producto

## Características principales

- **Búsqueda inteligente:** buscar "leche" devuelve solo lácteos, no "café con leche" ni "chocolate con leche". El motor extrae el tipo de producto y prioriza resultados por relevancia semántica.
- **Normalización cross-retailer:** cada producto se descompone en tipo, marca y formato independientemente de cómo lo nombre cada supermercado.
- **26 categorías normalizadas:** desde "Lácteos" hasta "Mascotas", asignadas automáticamente a partir del nombre del producto.
- **Comparador de precios:** tabla resumen con el más barato por supermercado y diferencias porcentuales.
- **Histórico de precios:** gráfico temporal por producto con evolución semanal.
- **Ejecución paralela:** cada scraper corre en un job independiente de GitHub Actions; si uno falla, los demás se guardan igualmente.

## Estructura del proyecto

```
supermarket-price-tracker/
├── .github/workflows/
│   └── scraper_semanal.yml       # CI/CD: 5 scrapers en paralelo + merge
├── scraper/
│   ├── mercadona.py              # API pública de Mercadona
│   ├── carrefour.py              # API de Carrefour (Playwright)
│   ├── dia.py                    # API de Dia (cookie automática)
│   ├── alcampo.py                # API de Alcampo (Playwright)
│   ├── eroski.py                 # Web scraping de Eroski (Playwright)
│   └── cookie_manager.py         # Gestión y verificación de cookies
├── database/
│   ├── init_db.py                # Schema + migración automática
│   └── database_db_manager.py    # CRUD con búsqueda inteligente
├── matching/
│   ├── normalizer.py             # Motor NLP: extracción tipo/marca/categoría
│   ├── marcas.json               # Diccionario de 1.480 marcas
│   └── product_matcher.py        # Matching cross-retailer con rapidfuzz
├── dashboard/
│   ├── app.py                    # Página principal + métricas + búsqueda
│   ├── pages/
│   │   ├── 1_Historico_precios.py
│   │   ├── 2_Comparador.py
│   │   └── 3_Favoritos.py
│   └── utils/
│       └── charts.py             # Gráficos Plotly (histogramas, líneas, barras)
├── main.py                       # Ejecución secuencial (todos los scrapers)
├── run_scraper.py                # Ejecución individual + export CSV
├── import_results.py             # Merge de CSVs paralelos → DB
├── requirements.txt
├── example.env
└── README.md
```

## Instalación

### Requisitos previos

- Python 3.9 o superior
- Git

### Pasos

1. Clona el repositorio:
```bash
git clone https://github.com/tu-usuario/supermarket-price-tracker.git
cd supermarket-price-tracker
```

2. Crea y activa un entorno virtual:
```bash
python -m venv venv

# Linux / Mac / Codespaces
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Instala Playwright (necesario para Carrefour, Dia, Alcampo y Eroski):
```bash
playwright install chromium
playwright install-deps chromium
```

5. Configura las cookies:
```bash
cp example.env .env
```
Edita el archivo `.env` con tus cookies reales. Consulta la guía en `docs/guia_env.md` para obtenerlas.

6. Ejecuta el scraper:
```bash
# Todos los supermercados (secuencial)
python main.py

# Un supermercado individual
python run_scraper.py mercadona
python run_scraper.py dia
```

7. Lanza el dashboard:
```bash
streamlit run dashboard/app.py
```

## Configuración de cookies

Mercadona, Alcampo y Eroski no necesitan cookies. Para Carrefour:

1. Abre la web del supermercado en el navegador.
2. Pulsa F12 para abrir las herramientas de desarrollador.
3. Ve a la pestaña Red (Network).
4. Recarga la página (F5).
5. Haz clic en cualquier petición y busca "Cookie" en los encabezados de solicitud.
6. Copia el valor completo y pégalo en tu archivo `.env`.

Dia obtiene su cookie automáticamente mediante Playwright.

### Codespaces / GitHub Actions

En lugar del archivo `.env`, configura las cookies como **Secrets** en tu repositorio de GitHub:

Settings > Secrets and variables > Actions > New repository secret

## Cómo funciona

### 1. Extracción
Cada scraper llama a la API interna del supermercado, obtiene el árbol de categorías y recorre cada una para extraer todos los productos con sus precios. Devuelve un DataFrame con columnas normalizadas (Id, Nombre, Precio, Formato, Supermercado...).

### 2. Normalización
Antes de guardar en la base de datos, cada producto pasa por el motor de normalización (`matching/normalizer.py`) que extrae:
- **Tipo de producto:** lo que el producto ES ("Leche entera", "Café molido")
- **Marca:** detectada por reglas de posición según el supermercado + diccionario de 1.480 marcas
- **Categoría normalizada:** clasificación automática en 26 categorías canónicas

### 3. Almacenamiento
Los datos se guardan en SQLite con upsert: si el producto ya existe se actualizan sus datos, y siempre se inserta un nuevo registro de precio con fecha. Esto construye el histórico automáticamente.

### 4. Búsqueda inteligente
Las búsquedas del dashboard van primero contra `tipo_producto` (resultados precisos) y después contra el nombre completo (resultados secundarios). Buscar "leche" devuelve primero los lácteos y relega "café con leche" a resultados secundarios.

### 5. Visualización
Dashboard Streamlit con 4 vistas: métricas generales, histórico de precios, comparador entre supermercados y favoritos.

## Ejecución automática (GitHub Actions)

El workflow ejecuta los 5 scrapers en **paralelo** como jobs independientes:

```
Job Mercadona (~30s)  ─┐
Job Carrefour (~15m)  ─┤
Job Dia       (~1m)   ─┼─→ Merge → DB → git commit
Job Alcampo   (~17m)  ─┤
Job Eroski    (~62m)  ─┘
```

Cada job exporta un CSV. El job final descarga todos los CSVs, los importa en la base de datos con normalización, y hace commit automático. Si un scraper falla, los demás se guardan igualmente.

Se ejecuta automáticamente cada lunes a las 7:00 AM (hora española). También se puede lanzar manualmente desde la pestaña Actions del repositorio.

## Roadmap

- [x] Scraper de Mercadona
- [x] Scraper de Carrefour
- [x] Scraper de Dia
- [x] Scraper de Alcampo
- [x] Scraper de Eroski
- [x] GitHub Actions para ejecución semanal
- [x] Jobs paralelos en CI/CD
- [x] Sistema de logging
- [x] Base de datos SQLite con histórico
- [x] Motor de normalización NLP (tipo + marca + categoría)
- [x] Diccionario de marcas auto-extraído (1.480 marcas)
- [x] 26 categorías normalizadas
- [x] Búsqueda inteligente por tipo de producto
- [x] Sistema de equivalencias entre productos
- [x] Dashboard con Streamlit
- [x] Gráficos de evolución de precios con Plotly
- [x] Comparador entre supermercados
- [x] Sistema de favoritos
- [ ] Alertas de bajadas de precio
- [ ] Exportación de informes a Excel/PDF
- [ ] API REST para consultas externas

## Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## Disclaimer

Este proyecto es exclusivamente educativo y de uso personal. Los datos extraídos son de acceso público. Consulta los términos de uso de cada supermercado antes de usar esta herramienta. Se recomienda usar pausas entre peticiones para no sobrecargar los servidores.
