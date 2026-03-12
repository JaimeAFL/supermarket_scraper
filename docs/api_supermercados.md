# APIs y estrategia de extracción por supermercado

Resumen técnico de cómo extrae datos cada scraper. Todos devuelven un `pd.DataFrame` con el mismo contrato de columnas para poder importar en bloque.

---

## Contrato común de salida

| Columna | Tipo | Descripción |
|---|---|---|
| `Id` | str | ID del producto en el supermercado |
| `Nombre` | str | Nombre del producto |
| `Precio` | float | Precio actual en euros |
| `Precio_por_unidad` | float | Precio por kg/L según el supermercado |
| `Formato` | str | Peso, volumen o unidades en formato original |
| `Categoria` | str | Categoría original del supermercado |
| `Supermercado` | str | Nombre de la cadena |
| `Url` | str | URL del producto (normalizada a columna `Url`, no `URL`) |
| `Url_imagen` | str | URL de la imagen |

`DatabaseManager.guardar_productos()` aplica normalización semántica adicional (tipo, marca, categoría normalizada, formato normalizado y precio unitario calculado) antes de persistir en SQLite.

Si `Url` llega vacía, `guardar_productos()` construye una URL de fallback a partir de `id_externo` + el patrón de URL conocido para cada supermercado.

---

## Mercadona (`mercadona.py`)

- **Fuente:** API pública de Mercadona.
- **Método:** `requests` (sin Playwright).
- **Autenticación:** ninguna.
- **Flujo:**
  1. `GET https://tienda.mercadona.es/api/categories/` → lista de IDs de categoría.
  2. `GET https://tienda.mercadona.es/api/categories/{id}/` → productos de cada categoría.
  3. `time.sleep(1)` entre peticiones.
- **Formato:** Mercadona devuelve precios ya en €/kg o €/L. El campo `format` solo indica unidad ("L", "kg") sin cantidad.
- **Tiempo estimado:** ~30 segundos · ~4.300 productos.

---

## Carrefour (`carrefour.py`)

- **Fuente:** API de búsqueda interna `carrefour.es/search-api/query/v1/search`.
- **Método:** Playwright + interceptación de respuestas XHR.
- **Autenticación:** no requiere cookie manual en el flujo actual.
- **Flags de Chromium:** `--disable-dev-shm-usage`, `--no-sandbox`, `--disable-gpu`. **No se usa `--single-process`** (rompe la interceptación de respuestas via `page.on("response")`).
- **Flujo:**
  1. Lanza Chromium con Playwright.
  2. Navega búsquedas por términos de categoría.
  3. Intercepta respuestas JSON de la API de búsqueda.
  4. Normaliza campos: `display_name`, `active_price`, `product_id`, `image_path`.
- **Formato:** el formato del producto está embebido en el nombre, no en un campo separado. Se extrae por regex en la normalización.
- **`COOKIE_CARREFOUR`:** se mantiene en `.env` como fallback opcional para flujos manuales de verificación; el scraper principal no depende de ella.
- **Tiempo estimado:** ~15 minutos · ~2.400 productos.

---

## Dia (`dia.py`)

- **Fuente:** API interna de Dia.
  - Menú de categorías: `/api/v1/plp-insight`
  - Productos por categoría: `/api/v1/plp-back/reduced`
- **Método:** `requests`.
- **Autenticación:** requiere `COOKIE_DIA` en runtime.
- **Obtención automática de la cookie:**
  - `main.py` y `run_scraper.py dia` invocan `cookie_manager.py` antes del scraper.
  - El gestor valida la cookie existente (GET de prueba). Si falla o no existe, lanza Playwright para obtenerla automáticamente.
  - `COOKIE_DIA` en `.env` actúa como fallback si la obtención automática falla.
- **Flujo:**
  1. Navegación recursiva del árbol de categorías.
  2. GET de productos en cada nodo hoja con paginación.
  3. `time.sleep(1)` entre peticiones.
- **Tiempo estimado:** ~1 minuto · ~3.200 productos.

---

## Alcampo (`alcampo.py`)

- **Fuente:** API interna de Alcampo (interceptada vía Playwright).
- **Método:** Playwright + interceptación de respuestas XHR.
- **Autenticación:** no requiere cookie manual.
- **Flags de Chromium:** `--disable-dev-shm-usage`, `--no-sandbox`, `--disable-gpu`. **No se usa `--single-process`**.
- **Flujo:**
  1. Navega el árbol de categorías de Alcampo.
  2. Intercepta las llamadas a la API interna de productos.
  3. Extrae y normaliza campos.
- **Formato:** mezcla de formatos crudos: "1000ml", "500" (números solos = gramos), texto libre. La cobertura de normalización de formato es del 72% (el resto son productos no alimentarios sin formato estándar).
- **`CODIGO_POSTAL`:** se usa para contexto de tienda y precios.
- **Tiempo estimado:** ~17 minutos · ~10.000 productos.

---

## Eroski (`eroski.py`)

- **Fuente:** web de `supermercado.eroski.es`.
- **Método:** Playwright + extracción DOM + paginación por scroll.
- **Autenticación:** no requiere cookie manual.
- **Flags de Chromium:** `--disable-dev-shm-usage`, `--no-sandbox`, `--disable-gpu`. **No se usa `--single-process`**.
- **Flujo:**
  1. Construye mapa de categorías navegando la web.
  2. Por cada categoría, pagina con scroll infinito.
  3. Extrae productos del DOM y deduplica por ID.
- **Formato:** el mejor nativo del proyecto: "1 litro", "500 g". Cobertura de normalización de formato ~100%.
- **Gestión de memoria:** Eroski es el scraper más pesado. Si el proceso de Chromium queda huérfano tras un fallo, `_matar_chromium_huerfano()` en `main.py` lo limpia antes del siguiente scraper.
- **Tiempo estimado:** ~62 minutos · ~10.000 productos.

---

## Consum (`consum.py`)

- **Fuente:** API REST pública de Consum.
- **Método:** `requests` (sin Playwright).
- **Autenticación:** ninguna. Sin cookies. Sin headers especiales.
- **Endpoint:** `GET https://tienda.consum.es/api/rest/V1.0/catalog/product?offset={N}&limit=100`
  - `limit=100` es el máximo real de la API (valores mayores devuelven igualmente 100).
  - Paginación por `offset`: se incrementa de 100 en 100 hasta que `hasMore` sea `false`.
- **Flujo:**
  1. Primera petición con `offset=0` para obtener `totalCount`.
  2. Bucle de paginación hasta cubrir todos los productos.
  3. Normalización de campos: `productData.name`, `productData.brand.name`, `priceData.prices`, `productData.format`, `productData.url`, `productData.imageURL`.
- **Precio:** se usa `OFFER_PRICE` si existe, si no `PRICE`. Ambos vienen en `centAmount` (valor real en euros, no centimos).
- **Formato:** campo `productData.format` con texto como "250 g", "1 L", "6 x 1 L". Cobertura ~95%.
- **Marca:** campo dedicado `productData.brand.name`. No requiere extracción por posición ni diccionario.
- **Tiempo estimado:** ~2 minutos · ~9.100 productos.

---

## Condis (`condis.py`) — en integración

- **Fuente:** API de búsqueda Empathy (`api.empathy.co`), el motor de catálogo que usa Condis en su tienda online.
- **Método:** `requests` (sin Playwright, sin autenticación, sin cookies).
- **Autenticación:** ninguna. Headers estándar de navegador son suficientes.
- **Endpoints:**
  - Categorías: se extraen del HTML de la página principal `https://compraonline.condis.es/` con regex (`c\d+__cat\d+`). Hay ~93 categorías.
  - Productos por categoría:
    ```
    GET https://api.empathy.co/search/v1/query/condis/browse
        ?lang=es&rows=100&start={offset}&store=718
        &browseField=parentCategory&browseValue={categoryId}
    ```
  - `rows=100` es el máximo práctico. Paginación por `start` hasta que `start >= catalog.numFound`.
- **Respuesta JSON relevante:**
  ```json
  {
    "catalog": {
      "numFound": 259,
      "content": [{
        "id": "704048",
        "description": "LECHE CONDIS SEMIDESNATADA 1 L",
        "brand": "CONDIS",
        "price": { "current": 0.91, "regular": 1.10 },
        "pum": "0,91€/Litro",
        "category": ["Bebidas", "Leche", "Leche semidesnatada"],
        "images": ["/images/catalog/large/704048.jpg"],
        "url": "/leche-condis-semidesnatada-1-l/p/704048/es_ES"
      }]
    }
  }
  ```
- **Precio:** se usa `price.current` (ya aplica descuentos). Si `price.current < price.regular` hay oferta activa.
- **Precio unitario:** campo `pum` en texto libre ("0,91€/Litro", "2,40€/kg"). Se extrae el valor numérico con regex.
- **Formato:** embebido en el nombre del producto en mayúsculas ("LECHE ASTURIANA 1 L", "YOGUR 500 G"). `_extraer_formato_de_nombre()` lo extrae y normaliza.
- **Marca:** campo dedicado `brand` en la respuesta. No requiere extracción por posición ni diccionario.
- **Categoría:** lista ordenada de lo más general a lo más específico (`["Bebidas", "Leche", "Leche semidesnatada"]`). Se usa el último elemento (el más específico).
- **Nombres en mayúsculas:** Condis devuelve todos los nombres en MAYÚSCULAS. Se convierten a formato título (`str.title()`) antes de guardar.
- **Pausa entre peticiones:** 0.3 segundos (más agresivo que otros scrapers al ser API pura sin riesgo de bloqueo Playwright).
- **Cobertura estimada:** ~5.800 productos únicos (~7.300 brutos antes de deduplicar solapamiento entre categorías).
- **Tiempo estimado:** ~4–6 minutos.
- **Estado:** scraper implementado y funcional. Pendiente de añadir a `run_scraper.py` y `main.py`.

---

## Notas comunes de implementación

### Flags de Chromium

Todos los scrapers que usan Playwright arrancan Chromium con estos tres flags y **solo estos**:

```python
args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
```

El flag `--single-process` está **expresamente prohibido**: provoca que `page.on("response")` falle silenciosamente y el scraper devuelva 0 productos sin lanzar ningún error.

### Limpieza de procesos huérfanos

`main.py` llama a `_matar_chromium_huerfano()` antes de la ejecución, después de obtener cookies, y en el bloque `finally` de cada scraper. Esto evita que un crash de Chromium consuma RAM y bloquee scrapers posteriores.

### Naming de columnas

La columna de URL se llama `Url` (con mayúscula inicial) en todos los scrapers y en `guardar_productos()`. Usar `URL` (todo mayúsculas) provoca que la URL se descarte silenciosamente al guardar en la base de datos.
