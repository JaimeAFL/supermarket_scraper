# Motor de normalización de productos

Documentación técnica del sistema de normalización implementado en `normalizer.py`. Explica el problema que resuelve, los métodos aplicados, la cobertura alcanzada y cómo extender el sistema.

## Problema

Los supermercados españoles nombran el mismo producto de formas muy distintas:

| Supermercado | Nombre del producto |
|---|---|
| Mercadona | `Leche entera Hacendado` |
| Carrefour | `Leche entera Carrefour brik 1 l.` |
| Dia | `Leche entera Dia Láctea pack 6 x 1 L` |
| Alcampo | `AUCHAN Leche entera de vaca 1 l. Producto Alcampo` |
| Eroski | `Leche entera del País Vasco EROSKI, brik 1 litro` |
| Consum | `Leche entera` (marca en campo separado `brand.name`) |

Esto genera dos problemas:

1. **Búsqueda con ruido:** buscar "leche" con `LIKE '%leche%'` devuelve 1.067 resultados que incluyen "café con leche", "chocolate con leche", "arroz con leche" y "galletas con leche". Solo 477 son productos lácteos.

2. **Categorías incompatibles:** cada supermercado usa su propia taxonomía. No se pueden comparar directamente entre cadenas.

## Solución: Método 1 + Método 2

La normalización combina dos técnicas que se ejecutan antes de guardar cada producto en la base de datos.

### Método 1: Reglas de posición por supermercado

Cada supermercado sigue un patrón de naming consistente. El normalizador aplica reglas específicas para extraer **tipo de producto**, **marca** y **formato**.

#### Alcampo: MARCA + tipo + formato

Alcampo siempre pone la marca en MAYÚSCULAS al inicio del nombre:

```
AUCHAN Leche entera de vaca 1 l. Producto Alcampo
^^^^^^                                              → marca
       ^^^^^^^^^^^^^^^^^^^^^^                       → tipo de producto
                              ^^^^                  → formato
                                   ^^^^^^^^^^^^^^^^ → sufijo (se descarta)
```

Se recorren las palabras desde el inicio mientras estén en MAYÚSCULAS. La primera palabra en minúsculas marca el fin de la marca y el inicio del tipo. Un regex elimina el formato del final.

**Fiabilidad:** 84% de los productos de Alcampo empiezan con marca en MAYÚSCULAS. El 16% restante son productos sin marca reconocida (herramientas, electrónica, bazar).

#### Eroski: tipo + MARCA + , formato

Eroski pone el tipo primero, la marca en MAYÚSCULAS al final de la frase principal, y el formato después de una coma:

```
Leche entera del País Vasco EROSKI, brik 1 litro
^^^^^^^^^^^^^^^^^^^^^^^^^^^^                      → tipo de producto
                             ^^^^^^               → marca
                                    ^^^^^^^^^^^^  → formato (después de coma)
```

Se parte por la primera coma (tipo+marca | formato). Después se recorren las palabras del bloque tipo+marca en orden inverso: las que están en MAYÚSCULAS son la marca.

**Fiabilidad:** 100% de los productos usan coma como separador de formato. Marca detectada en el 92,3%.

#### Mercadona / Carrefour / Dia: tipo + marca (por diccionario)

Estos tres supermercados no tienen un marcador visual consistente:

```
Mercadona:  Leche entera Hacendado
Carrefour:  Leche entera Carrefour brik 1 l.
Dia:        Leche entera Dia Láctea pack 6 x 1 L
```

Se busca la marca más larga del diccionario que coincida dentro del nombre. Todo lo que va antes de la marca es el tipo.

#### Consum: campos separados de la API

Consum devuelve la marca en un campo dedicado (`productData.brand.name`). No se aplica extracción por posición: el campo `brand` se usa directamente como marca, y el nombre completo se usa como tipo de producto.

#### Condis: campos separados de la API (API Empathy)

Condis usa el motor de búsqueda Empathy y también devuelve la marca en un campo dedicado (`brand`). Los nombres vienen en MAYÚSCULAS y se convierten a formato título antes de normalizar. No se aplica extracción por posición ni diccionario.

### Diccionario de marcas (`marcas.json`)

El diccionario contiene 1.480 marcas construidas de forma semi-automática:

1. **Auto-extracción de Alcampo (742 marcas):** secuencias iniciales en MAYÚSCULAS con ≥2 apariciones.
2. **Auto-extracción de Eroski (965 marcas):** secuencias en MAYÚSCULAS antes de la coma.
3. **Validación cruzada:** 261 marcas aparecen en ambas fuentes.
4. **Marcas manuales (~40):** marcas blancas multi-palabra no detectables automáticamente (e.g., "Bosque Verde", "Nuestra Alacena", "Central Lechera Asturiana").
5. **Filtrado de stop-words:** se excluyen palabras funcionales (DE, LA, CON, SIN, PARA, etc.).

El diccionario se ordena por longitud descendente para que las marcas multi-palabra matcheen antes que sus componentes ("CARREFOUR CLASSIC" antes que "CARREFOUR").

Para añadir una marca nueva, editar `marcas.json`:

```json
["...", "NUEVA MARCA", "..."]
```

El orden dentro del JSON no importa (se reordena por longitud al cargar). Las marcas se comparan en MAYÚSCULAS.

### Método 2: Taxonomía de categorías

Una vez extraído el tipo de producto, se clasifica en una categoría normalizada mediante coincidencia de prefijos sin acentos.

| # | Categoría | Ejemplos de prefijos |
|---|---|---|
| 1 | Lácteos | leche entera, yogur, queso, nata, mantequilla, natillas |
| 2 | Bebidas | agua mineral, refresco, zumo, bebida de, horchata |
| 3 | Cervezas | cerveza |
| 4 | Vinos y licores | vino, cava, sidra, ginebra, vodka, whisky |
| 5 | Cafés e infusiones | café, cápsulas de café, infusión, té, manzanilla |
| 6 | Panadería | pan, baguette, tostadas, hogaza, wrap |
| 7 | Galletas y bollería | galletas, magdalena, croissant, donut, bizcocho |
| 8 | Cereales y legumbres | arroz, cereal, avena, lentejas, garbanzos |
| 9 | Pasta | pasta, espagueti, macarron, fideos, lasaña |
| 10 | Harinas | harina, levadura, maicena |
| 11 | Conservas de pescado | atún, sardinas, mejillones, anchoas, bonito |
| 12 | Conservas vegetales | tomate frito, tomate triturado, aceitunas, espárragos |
| 13 | Aceites y vinagres | aceite de oliva, aceite de girasol, vinagre |
| 14 | Embutidos y fiambres | jamón, chorizo, salchichón, bacon, fuet |
| 15 | Carnes | pollo, ternera, cerdo, hamburguesa, solomillo |
| 16 | Pescados y mariscos | merluza, salmón, bacalao, gamba, langostino |
| 17 | Frutas y verduras | manzana, plátano, tomate, patata, lechuga, zanahoria |
| 18 | Congelados y preparados | pizza, croqueta, nuggets, empanadilla |
| 19 | Huevos | huevos |
| 20 | Salsas y condimentos | salsa, mayonesa, ketchup, caldo de, pimienta |
| 21 | Azúcar y edulcorantes | azúcar, edulcorante |
| 22 | Chocolates y cacao | chocolate, bombón, cacao soluble |
| 23 | Dulces y untables | mermelada, miel, crema de cacao |
| 24 | Snacks y frutos secos | patatas fritas, palomitas, frutos secos, pipas |
| 25 | Higiene personal | gel de ducha, champú, desodorante, dentífrico, colonia |
| 26 | Limpieza del hogar | detergente, lejía, lavavajillas, papel higiénico |
| 27 | Bebé | pañal, papilla, potito, leche de inicio |
| 28 | Mascotas | pienso, alimento para perro, arena para gato |

La taxonomía se evalúa en orden: el primer match gana. Esto resuelve ambigüedades como "Café con leche" → Cafés e infusiones (no Lácteos), "Leche de inicio" → Bebé.

El 55,8% de productos no recibe categoría normalizada: principalmente electrónica, bricolaje, ropa y bazar de Alcampo. Esto es intencionado: es mejor no categorizar que categorizar mal.

## Normalización de formato y precio unitario

Además del tipo y la marca, cada producto pasa por normalización de formato:

- **Conversiones de unidades:** ml → L, cl → L, g → kg
- **Extracción de cantidad:** packs, lavados, metros, unidades, docenas
- **Formatos crudos de Alcampo:** "1000ml", "500" (números solos = gramos)
- **Formatos de Eroski:** "1 litro", "500 g" (formato nativo, bien estructurado)
- **Formatos de Consum:** campo `productData.format` ("250 g", "1 L", etc.)

La función `calcular_precio_unitario(precio, formato_normalizado)` devuelve `(float, "€/L" | "€/kg" | "€/ud")` para comparación entre supermercados.

### Cobertura de formato por supermercado

| Supermercado | Cobertura formato | Cobertura precio unitario |
|---|---|---|
| Mercadona | 91% | 96% |
| Carrefour | 91% | 96% |
| Dia | 91% | 98% |
| Eroski | 91% | 100% |
| Alcampo | 72% | 72% |
| Consum | 95% | 99% |
| Condis | 92% | 98% |

Alcampo tiene cobertura menor porque mezcla alimentación con electrónica, bricolaje y ropa, categorías sin formato estándar.

## Resultado completo por producto

```python
normalizar_producto(
    "AUCHAN Leche entera de vaca 1 l. Producto Alcampo",
    "Alcampo"
)
# → {
#     "tipo_producto": "Leche entera de vaca",
#     "marca": "AUCHAN",
#     "nombre_normalizado": "leche entera de vaca",
#     "categoria_normalizada": "Lácteos",
# }

normalizar_producto(
    "Chocolate con leche Hacendado avellanas troceadas",
    "Mercadona"
)
# → {
#     "tipo_producto": "Chocolate con leche",
#     "marca": "Hacendado",
#     "nombre_normalizado": "chocolate con leche",
#     "categoria_normalizada": "Chocolates y cacao",
# }
```

## Cómo se usa en la búsqueda

Cuando el usuario busca "leche":

```sql
-- Prioridad 1: tipo de producto empieza por "leche"
SELECT * FROM productos WHERE nombre_normalizado LIKE 'leche%'
-- → 477 resultados: Leche entera, Leche desnatada, Leche condensada...

UNION ALL

-- Prioridad 2: nombre completo contiene "leche"
SELECT * FROM productos WHERE nombre LIKE '%leche%'
  AND id NOT IN (SELECT id FROM productos WHERE nombre_normalizado LIKE 'leche%')
-- → 590 resultados: Café con leche, Chocolate con leche...
```

El dashboard muestra los 477 directos primero. Los 590 secundarios van en un expander colapsado.

## Métricas de rendimiento

| Métrica | Valor |
|---|---|
| Productos totales | ~45.000 |
| Con marca extraída | ~72,6% |
| Con categoría normalizada | ~44,2% |
| Marcas en diccionario | 1.480 |
| Categorías definidas | 28 |
| Tiempo de normalización | ~3 seg (30.000 productos) |

### Precisión de búsqueda

| Búsqueda | Resultados LIKE | Resultados por tipo | Ruido eliminado |
|---|---|---|---|
| leche | 1.067 | 477 | 55% |
| café | 743 | 602 | 19% |
| yogur | 400 | 334 | 17% |
| cerveza | 559 | 538 | 4% |
| aceite | 865 | 347 | 60% |
| chocolate | 1.015 | 364 | 64% |

## Edge cases conocidos

1. **"Leche corporal Nivea":** empieza por "leche" pero es cosmética. Se podría resolver con lista de exclusión (tipo contiene "corporal", "capilar" → no es alimentación).
2. **"PULEVA Eco Leche desnatada":** "Eco" queda como parte del tipo en Alcampo. No afecta a la búsqueda porque "leche" sigue apareciendo.
3. **Marcas no reconocidas:** el 27,4% de productos no tiene marca detectada. Son principalmente marcas pequeñas con <2 apariciones o productos genéricos sin marca.

## Alternativas consideradas

| Alternativa | Pros | Contras | Decisión |
|---|---|---|---|
| EAN-13 | Identificador universal | No disponible en las APIs | Descartado |
| Full-Text Search (PostgreSQL) | Ranking por relevancia nativo | No resuelve "café con leche" | Insuficiente solo |
| Embeddings/NLP | Semántico, flexible | Excesivo para el tamaño del proyecto | Descartado |
| Reglas + taxonomía | Rápido, determinista, explicable | Requiere mantenimiento manual | **Elegido** |
