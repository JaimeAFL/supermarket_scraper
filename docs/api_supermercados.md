# APIs de supermercados: Reverse Engineering

Documentación técnica del proceso de reverse engineering realizado sobre
las APIs internas de los 5 supermercados. Incluye endpoints, headers,
paginación, estructura de respuesta y estrategias de mitigación de bloqueo.

## Metodología de descubrimiento

Para cada supermercado, el proceso fue:

1. Abrir la web del supermercado con DevTools (F12) → pestaña Network.
2. Navegar por categorías y productos observando las peticiones XHR/Fetch.
3. Identificar los endpoints que devuelven datos estructurados (JSON).
4. Reproducir las peticiones con `requests` o `playwright` desde Python.
5. Mapear los campos de la respuesta al DataFrame normalizado del proyecto.

---

## Mercadona

### Descubrimiento

Mercadona tiene la API más limpia de los cinco. Al navegar
`tienda.mercadona.es`, todas las peticiones de datos van a `/api/`
y devuelven JSON sin autenticación.

### Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/categories/` | GET | Lista de categorías raíz |
| `/api/categories/{id}/` | GET | Productos de una categoría |

### Headers

```
User-Agent: Mozilla/5.0 (...)
Accept: application/json
```

No requiere cookies, tokens ni autenticación de ningún tipo.

### Estructura de respuesta

```json
// GET /api/categories/
[
    {"id": 112, "name": "Aceite, especias y salsas", "order": 1},
    {"id": 113, "name": "Arroz, legumbres y pasta", "order": 2},
    ...
]

// GET /api/categories/112/
{
    "categories": [
        {
            "name": "Aceite de oliva",
            "products": [
                {
                    "id": "4241",
                    "display_name": "Aceite de oliva 0,4º Hacendado",
                    "price_instructions": {
                        "unit_price": 5.95,
                        "reference_format": "0,75 L",
                        "unit_size": "7,93 €/L"
                    },
                    "thumbnail": "https://..."
                }
            ]
        }
    ]
}
```

### Mapeo a DataFrame

| Campo API | Columna DataFrame |
|---|---|
| `id` | Id |
| `display_name` | Nombre |
| `price_instructions.unit_price` | Precio |
| `price_instructions.unit_size` | Precio_unidad |
| `price_instructions.reference_format` | Formato |
| `categories[].name` | Categoria |
| — | URL (no disponible) |
| `thumbnail` | URL_imagen |

### Rate limiting

`time.sleep(1)` entre categorías. Nunca se ha observado bloqueo.
Tiempo total: ~30 segundos para ~4.300 productos.

### Notas

- La API no requiere código postal ni geolocalización.
- Los precios son los mismos para toda España (política de Mercadona).
- Las URLs de producto no existen (Mercadona no tiene fichas web
  individuales accesibles).

---

## Carrefour

### Descubrimiento

Carrefour usa una Cloud API (`/cloud-api/`) que requiere cookie de sesión.
Sin la cookie, las peticiones devuelven 401. La cookie se obtiene
navegando la web con un navegador normal y se configura vía `.env`.

### Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/cloud-api/categories-v2` | GET | Árbol de categorías (3 niveles) |
| `/cloud-api/plp-food-search/v2` | GET | Productos de una categoría |

### Headers

```
User-Agent: Mozilla/5.0 (...)
Accept: application/json
Cookie: <cookie_de_sesion>
```

La cookie contiene la sesión del usuario, incluyendo el código postal
que determina qué tienda/almacén sirve los precios.

### Paginación

El endpoint de productos usa offset-based pagination:

```
/cloud-api/plp-food-search/v2?category_id=L3_CAT001&offset=0&limit=24
/cloud-api/plp-food-search/v2?category_id=L3_CAT001&offset=24&limit=24
/cloud-api/plp-food-search/v2?category_id=L3_CAT001&offset=48&limit=24
```

**Criterio de parada:** cuando los productos devueltos ya se han visto
en páginas anteriores (se detectan duplicados por ID). Carrefour no
devuelve un campo `total_count` fiable.

### Estructura de respuesta

```json
{
    "content": [
        {
            "display_name": "Leche entera Carrefour brik 1 l.",
            "product_id": "R-521006992",
            "active_price": {"price": 0.79},
            "unit_price": {"unit": "L", "price": 0.79},
            "image_path": "/imgprod/...",
            "product_url": "/supermercado/leche-entera.../R-521006992/p"
        }
    ]
}
```

### Navegación de categorías

El árbol tiene 3 niveles. El scraper navega recursivamente:

```
Nivel 1: Alimentación
  Nivel 2: Lácteos
    Nivel 3: Leche          ← se extraen productos aquí
    Nivel 3: Yogures         ← se extraen productos aquí
  Nivel 2: Panadería
    Nivel 3: Pan de molde
    ...
```

Solo se extraen productos del nivel 3 (hojas del árbol).

### Rate limiting

`time.sleep(1)` entre peticiones. La cookie caduca cada ~24h.
Tiempo total: ~15 minutos para ~2.400 productos.

### Notas

- Los precios varían según código postal.
- El ID del producto (`R-521006992`) aparece en la URL pública,
  lo que permite construir links directos.
- Algunos productos tienen IDs que parecen EAN-13 (13 dígitos) pero
  son productos no alimentarios (libros, juguetes) — coincidencia numérica.

---

## Dia

### Descubrimiento

Dia expone una API REST que requiere cookie de sesión. La diferencia
clave con Carrefour es que la cookie de Dia se puede obtener
**automáticamente** con Playwright: basta con navegar a la web,
aceptar el código postal, y extraer la cookie de la respuesta.

### Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/navigation/menu` | GET | Árbol de categorías completo |
| `/api/categories/{slug}/products` | GET | Productos de una categoría |

### Obtención automática de cookies

```python
# Flujo implementado en cookie_manager.py:
# 1. Playwright abre https://www.dia.es
# 2. Acepta cookies del banner
# 3. Introduce el código postal
# 4. Extrae la cookie de sesión del navegador
# 5. Valida la cookie con una petición de prueba
```

Esto elimina la necesidad de que el usuario obtenga la cookie manualmente.

### Estructura del menú

```json
// GET /api/navigation/menu
{
    "children": [
        {
            "name": "Charcutería y quesos",
            "slug": "/charcuteria-y-quesos",
            "children": [
                {
                    "name": "Jamón cocido",
                    "slug": "/charcuteria-y-quesos/jamon-cocido/c/L2001",
                    "children": []
                }
            ]
        }
    ]
}
```

El scraper recorre el árbol recursivamente hasta llegar a los nodos
hoja (sin `children`) y extrae productos de cada uno.

### Mapeo a DataFrame

| Campo API | Columna DataFrame |
|---|---|
| `id` | Id |
| `display_name` | Nombre |
| `prices.price` | Precio |
| `prices.unit_price` | Precio_unidad |
| `pack_size` o `weight` | Formato |
| slug de la categoría padre | Categoria |
| `https://www.dia.es/.../p/{id}` | URL |
| `image_url` | URL_imagen |

### Rate limiting

`time.sleep(1)` entre categorías. Tiempo total: ~1 minuto para ~3.200
productos (la API es muy rápida).

---

## Alcampo

### Descubrimiento

Alcampo tiene una API interna accesible tras navegar la web con
Playwright. A diferencia de los anteriores, no requiere cookie manual
— Playwright maneja la sesión automáticamente.

### Estrategia de extracción

1. Playwright abre la web de Alcampo y acepta cookies.
2. Se navega a cada categoría del supermercado online.
3. Se interceptan las peticiones XHR que devuelven los productos
   en formato JSON.
4. Se extrae la información de cada producto de la respuesta JSON.

### Estructura de producto

```json
{
    "productId": "21477",
    "name": "AUCHAN Leche entera de vaca 1 l. Producto Alcampo",
    "price": {"current": {"amount": 0.69}},
    "unitPrice": {"amount": 0.69, "unit": "l"},
    "brand": {"name": "AUCHAN"},
    "images": [{"url": "https://..."}]
}
```

### Particularidades

- Los nombres de Alcampo son los más largos de los 5 supermercados
  (media de ~60 caracteres vs ~30 en Mercadona).
- La marca siempre va al inicio en MAYÚSCULAS, lo que facilitó
  la auto-extracción del diccionario de marcas.
- "Producto Alcampo" o "Producto Económico Alcampo" aparece como
  sufijo en los productos de marca blanca.
- Alcampo vende productos no alimentarios (electrónica, bricolaje,
  ropa) que representan ~15% del catálogo.

### Rate limiting

`time.sleep(1)` entre peticiones. Tiempo total: ~17 minutos para
~10.000 productos.

---

## Eroski

### Descubrimiento

Eroski es el supermercado más complejo de scrapear. No tiene una API
REST limpia — los productos se cargan dinámicamente en la web mediante
JavaScript. El scraper usa Playwright para simular búsquedas por
términos clave.

### Estrategia de extracción

A diferencia de los otros scrapers (que navegan por categorías),
Eroski usa **búsqueda por términos**:

```python
TERMINOS_BUSQUEDA = [
    "leche", "yogur", "queso", "huevos", "mantequilla", "nata",
    "frutas", "verduras", "ensalada", "patatas", "carne", "pollo",
    "pescado", "marisco", "jamón", "chorizo", "pan", "bollería",
    "galletas", "cereales", "arroz", "pasta", "legumbres", "aceite",
    "café", "té", "cerveza", "vino", "refresco", "agua",
    "chocolate", "snacks", "congelados", "pizza", "conservas",
    "detergente", "lejía", "papel", "gel", "champú", "pañales",
    ...
]
```

Para cada término:
1. Playwright escribe el término en el buscador de Eroski.
2. Hace scroll hasta que no aparecen más productos (infinite scroll).
3. Extrae los datos de cada producto del DOM.
4. Deduplica contra productos ya vistos.

### Estructura del DOM

```html
<div class="product-card">
    <h3 class="product-title">Leche entera EROSKI, brik 1 litro</h3>
    <span class="product-price">0,79 €</span>
    <span class="unit-price">0,79 €/litro</span>
    <img src="https://..." />
</div>
```

### Particularidades

- El naming de Eroski es el más consistente: `tipo + MARCA + , formato`.
  Esto lo hizo la fuente principal para auto-extraer marcas.
- La búsqueda por términos puede perder productos con nombres poco
  convencionales (e.g., "txakoli" si no está en la lista de términos).
- Es el scraper más lento (~62 min) por depender de renderizado web
  y scroll dinámico.
- El navegador puede cerrarse si una búsqueda tarda demasiado
  (`TargetClosedError`), lo que requiere manejo de errores robusto.

### Rate limiting

Implícito por la velocidad de Playwright. No se añade sleep adicional
porque el scroll y el renderizado ya introducen pausas naturales.
Tiempo total: ~62 minutos para ~10.000 productos.

---

## Tabla comparativa

| | Mercadona | Carrefour | Dia | Alcampo | Eroski |
|---|---|---|---|---|---|
| **Método** | API REST | API REST | API REST | API + Playwright | Web scraping |
| **Auth** | Ninguna | Cookie manual | Cookie automática | Sesión Playwright | Ninguna |
| **Paginación** | Por categoría | Offset 24 | Por categoría | Por categoría | Infinite scroll |
| **Productos** | ~4.300 | ~2.400 | ~3.200 | ~10.000 | ~10.000 |
| **Tiempo** | 30 seg | 15 min | 1 min | 17 min | 62 min |
| **URLs producto** | No | Sí | Sí | No | No |
| **Naming** | tipo + marca | tipo + marca + formato | tipo + marca + formato | MARCA + tipo + formato | tipo + MARCA + , formato |
| **Fiabilidad** | Alta | Media (cookie caduca) | Alta (cookie auto) | Alta | Media (scroll timeout) |

## Consideraciones éticas y legales

- Todas las APIs son de acceso público (se acceden desde el navegador
  de cualquier usuario).
- Se respeta un `time.sleep(1)` entre peticiones para no sobrecargar
  los servidores.
- Los datos extraídos son precios públicos que cualquier consumidor
  puede ver en la web.
- El proyecto es de uso educativo y personal.
- Se recomienda revisar los términos de servicio de cada supermercado.
