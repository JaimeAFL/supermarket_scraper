# APIs y estrategia de extracción por supermercado

Resumen técnico actualizado de cómo extrae datos cada scraper (`scraper/*.py`).

## Mercadona (`scraper/mercadona.py`)

- **Fuente:** API pública de Mercadona.
- **Método:** `requests` (sin navegador).
- **Autenticación:** no requiere cookie.
- **Flujo:** obtiene categorías y recorre hojas para construir un DataFrame homogéneo.
- **Rendimiento esperado:** rápido (~30s).

## Carrefour (`scraper/carrefour.py`)

- **Fuente:** respuestas de red reales de `carrefour.es/search-api/query/v1/search`.
- **Método:** Playwright + parsing de respuestas interceptadas.
- **Autenticación:** no depende de una cookie manual en el flujo actual del scraper.
- **Estrategia:**
  - lanza Chromium,
  - navega búsquedas por términos,
  - intercepta respuestas JSON de la API de búsqueda,
  - normaliza campos (`display_name`, `active_price`, `product_id`, `image_path`, etc.).
- **Rendimiento esperado:** medio/alto (~15 min).

## Dia (`scraper/dia.py`)

- **Fuente:** API interna de Dia (`/api/v1/plp-insight` + `/api/v1/plp-back/reduced`).
- **Método:** `requests`.
- **Autenticación:** **requiere `COOKIE_DIA`** en runtime.
- **Cómo se obtiene la cookie:**
  - `main.py` y `run_scraper.py dia` invocan `scraper/cookie_manager.py`,
  - el gestor valida cookie existente y, si falla, intenta obtención automática con Playwright.
- **Rendimiento esperado:** rápido (~1 min).

## Alcampo (`scraper/alcampo.py`)

- **Fuente:** navegación web/API interna de Alcampo.
- **Método:** Playwright.
- **Autenticación:** no requiere cookie manual.
- **Nota:** usa `CODIGO_POSTAL` para contexto de tienda/precio.
- **Rendimiento esperado:** medio/alto (~17 min).

## Eroski (`scraper/eroski.py`)

- **Fuente:** web de supermercado Eroski.
- **Método:** Playwright + extracción por búsqueda y mapeo de categorías.
- **Autenticación:** no requiere cookie manual.
- **Estrategia:** construcción de mapa de categorías + búsqueda por términos + deduplicación por ID.
- **Rendimiento esperado:** alto (~62 min).

---

## Contrato común de salida

Todos los scrapers devuelven un `pd.DataFrame` con columnas normalizadas para poder importar en bloque:

- `Id`
- `Nombre`
- `Precio`
- `Precio_por_unidad`
- `Formato`
- `Categoria`
- `Supermercado`
- `Url`
- `Url_imagen`

Luego `DatabaseManager.guardar_productos()` aplica normalización semántica adicional (tipo, marca, categoría normalizada y formato normalizado) antes de persistir en SQLite.
