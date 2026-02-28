# Motor de normalización de productos

Documentación técnica del sistema de normalización NLP implementado en
`matching/normalizer.py`. Explica el problema, la solución, los métodos
usados, la cobertura alcanzada y cómo extender el sistema.

## Problema

Los supermercados españoles nombran el mismo producto de formas muy distintas:

| Supermercado | Nombre del producto |
|---|---|
| Mercadona | `Leche entera Hacendado` |
| Carrefour | `Leche entera Carrefour brik 1 l.` |
| Dia | `Leche entera Dia Láctea pack 6 x 1 L` |
| Alcampo | `AUCHAN Leche entera de vaca 1 l. Producto Alcampo` |
| Eroski | `Leche entera del País Vasco EROSKI, brik 1 litro` |

Esto genera dos problemas:

1. **Búsqueda con ruido:** buscar "leche" con `LIKE '%leche%'` devuelve
   1.067 resultados que incluyen "café con leche", "chocolate con leche",
   "arroz con leche" y "galletas con leche". Solo 477 son productos lácteos.

2. **Categorías incompatibles:** cada supermercado usa su propia taxonomía.
   Mercadona usa IDs numéricos (`112`, `115`), Dia usa rutas URL
   (`/charcuteria-y-quesos/jamon-cocido/c/L2001`), Alcampo usa texto
   descriptivo (`Agua, Soda y Gaseosas`), y Eroski usa nombres cortos
   (`Leche`, `Yogur`). No se pueden comparar directamente.

## Solución: Método 1 + Método 2

La normalización combina dos técnicas complementarias que se ejecutan
antes de guardar cada producto en la base de datos.

### Método 1: Reglas de posición por supermercado

Cada supermercado sigue un patrón de naming consistente. El normalizador
aplica reglas específicas según el supermercado para extraer tres campos:
**tipo de producto** (qué es), **marca** (quién lo fabrica) y **formato**
(peso/volumen/unidades).

#### Alcampo: MARCA + tipo + formato

Alcampo siempre pone la marca en MAYÚSCULAS al inicio del nombre:

```
AUCHAN Leche entera de vaca 1 l. Producto Alcampo
^^^^^^                                              → marca
       ^^^^^^^^^^^^^^^^^^^^^^                       → tipo de producto
                              ^^^^                  → formato
                                   ^^^^^^^^^^^^^^^^ → sufijo (se descarta)
```

**Implementación:** se recorren las palabras desde el inicio mientras estén
en MAYÚSCULAS. La primera palabra en minúsculas marca el fin de la marca
y el inicio del tipo. Un regex elimina el formato del final.

```python
def _extraer_alcampo(nombre):
    palabras = nombre.split()
    i = 0
    while i < len(palabras):
        c = palabras[i].strip('.,;:()[]"\'-')
        if c == c.upper() and len(c) > 0 and not c.isdigit():
            i += 1
        else:
            break
    marca = " ".join(palabras[:i])
    resto = " ".join(palabras[i:])
    tipo = _RE_FORMATO.sub('', resto)  # Quitar "1 l." del final
    return marca, tipo
```

**Fiabilidad:** 84% de los productos de Alcampo empiezan con marca en
MAYÚSCULAS. El 16% restante son productos sin marca reconocida
(herramientas, electrónica, bazar).

#### Eroski: tipo + MARCA + , formato

Eroski pone el tipo primero, la marca en MAYÚSCULAS al final de la frase
principal, y el formato después de una coma:

```
Leche entera del País Vasco EROSKI, brik 1 litro
^^^^^^^^^^^^^^^^^^^^^^^^^^^^                      → tipo de producto
                             ^^^^^^               → marca
                                    ^^^^^^^^^^^^  → formato (después de coma)
```

**Implementación:** se parte por la primera coma (tipo+marca | formato).
Después se recorren las palabras del bloque tipo+marca en orden inverso:
las que están en MAYÚSCULAS son la marca, el resto es el tipo.

**Fiabilidad:** 100% de los productos de Eroski usan coma como separador
de formato. La marca en MAYÚSCULAS se detecta en el 92,3% de los productos.

#### Mercadona / Carrefour / Dia: tipo + marca (por diccionario)

Estos tres supermercados no tienen un marcador visual consistente para la
marca. La marca puede ir en cualquier posición y en capitalización mixta:

```
Mercadona:  Leche entera Hacendado
Carrefour:  Leche entera Carrefour brik 1 l.
Dia:        Leche entera Dia Láctea pack 6 x 1 L
```

**Implementación:** se busca la marca más larga del diccionario que coincida
dentro del nombre. Todo lo que va antes de la marca es el tipo. Se verifica
que la coincidencia no sea subcadena de otra palabra (para evitar que "SPECIAL"
matchee dentro de "ESPECIAL").

```python
def _extraer_generico(nombre):
    nombre_upper = nombre.upper()
    for brand in _MARCAS_SORTED:  # Ordenadas por longitud desc
        idx = nombre_upper.find(brand.upper())
        if idx == -1:
            continue
        if idx > 0 and nombre_upper[idx - 1].isalpha():
            continue  # Es subcadena
        marca = nombre[idx:idx + len(brand)]
        tipo = nombre[:idx].strip()
        return marca, tipo
    return "", nombre  # Sin marca → todo es tipo
```

### Diccionario de marcas (`marcas.json`)

El diccionario contiene 1.480 marcas y se construyó de forma semi-automática:

1. **Auto-extracción de Alcampo (742 marcas):** como la marca siempre va en
   MAYÚSCULAS al inicio, se extrajeron todas las secuencias iniciales con ≥2
   apariciones.

2. **Auto-extracción de Eroski (965 marcas):** mismo principio, pero buscando
   la secuencia de MAYÚSCULAS antes de la coma.

3. **Validación cruzada:** 261 marcas aparecen en ambos supermercados,
   confirmando la calidad de la extracción.

4. **Marcas manuales (~40):** marcas blancas multi-palabra que no se detectan
   automáticamente (e.g., "Bosque Verde", "Nuestra Alacena", "El molino de Dia",
   "Carrefour El Mercado", "Central Lechera Asturiana").

5. **Filtrado de stop-words:** se excluyen palabras funcionales (DE, LA, CON,
   SIN, PARA, etc.) que aparecen en MAYÚSCULAS pero no son marcas.

El diccionario se ordena por longitud descendente para que las marcas
multi-palabra matcheen antes que sus componentes: "CARREFOUR CLASSIC"
matchea antes que "CARREFOUR".

#### Cómo ampliar el diccionario

Para añadir una marca nueva, editar `matching/marcas.json`:

```json
[
    "...",
    "NUEVA MARCA",
    "..."
]
```

El orden dentro del JSON no importa (se reordena por longitud al cargar).
Las marcas se comparan en MAYÚSCULAS, así que `"Nestlé"` matchea
`"NESTLÉ"` y `"nestlé"`.

### Método 2: Taxonomía de categorías

Una vez extraído el tipo de producto, se clasifica en una categoría
normalizada mediante coincidencia de prefijos sin acentos.

#### Tabla de categorías

| # | Categoría | Prefijos (ejemplos) |
|---|---|---|
| 1 | Lácteos | leche entera, leche semidesnatada, yogur, queso, nata, mantequilla, natillas |
| 2 | Bebidas | agua mineral, refresco, zumo, bebida de, limonada, horchata |
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

#### Resolución de ambigüedades

La taxonomía se evalúa en orden: el primer match gana. Esto resuelve
ambigüedades como:

- "Leche de inicio" → matchea "leche de inicio" en Bebé (antes que "leche"
  en Lácteos) porque Bebé va después pero con prefijos más específicos.
- "Café con leche" → matchea "café con leche" en Cafés e infusiones
  (no en Lácteos, porque el tipo empieza por "café").
- "Chocolate con leche" → matchea "chocolate" en Chocolates y cacao.

#### Productos sin categoría

El 55,8% de productos no recibe categoría normalizada. Son principalmente:

- Electrónica y electrodomésticos (Alcampo vende TVs, lavadoras, etc.)
- Bricolaje y jardín
- Ropa y calzado
- Juguetes
- Productos de bazar
- Alimentos con nombres que no empiezan por un prefijo reconocido

Esto es intencionado: es mejor no categorizar que categorizar mal.

## Resultado final

Cada producto pasa por la función `normalizar_producto()` y obtiene 4 campos:

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

Cuando el usuario busca "leche" en el dashboard:

```sql
-- Prioridad 1: tipo de producto empieza por "leche"
SELECT * FROM productos WHERE nombre_normalizado LIKE 'leche%'
-- → Leche entera, Leche desnatada, Leche condensada... (477 resultados)

UNION ALL

-- Prioridad 2: nombre completo contiene "leche"
SELECT * FROM productos WHERE nombre LIKE '%leche%'
  AND id NOT IN (resultados de prioridad 1)
-- → Café con leche, Chocolate con leche... (590 resultados)
```

El dashboard muestra primero los 477 resultados directos. Los 590
secundarios van en un expander colapsado "Otros productos que mencionan
leche".

## Métricas de rendimiento

| Métrica | Valor |
|---|---|
| Productos totales | 29.872 |
| Con marca extraída | 21.681 (72,6%) |
| Con categoría normalizada | 13.205 (44,2%) |
| Marcas en diccionario | 1.480 |
| Categorías definidas | 28 |
| Tiempo de normalización | ~3 seg (29.872 productos) |

### Precisión de búsqueda por término

| Búsqueda | Resultados SQL (`LIKE`) | Resultados por tipo | Ruido eliminado |
|---|---|---|---|
| leche | 1.067 | 477 | 55% |
| café | 743 | 602 | 19% |
| yogur | 400 | 334 | 17% |
| cerveza | 559 | 538 | 4% |
| aceite | 865 | 347 | 60% |
| chocolate | 1.015 | 364 | 64% |

"Cerveza" tiene poco ruido porque rara vez aparece como ingrediente
secundario. "Chocolate" y "aceite" tienen mucho ruido porque aparecen
frecuentemente en nombres compuestos ("galletas de chocolate",
"conservas en aceite").

## Edge cases conocidos

1. **"Leche corporal Nivea":** el tipo extraído empieza por "leche" pero
   es cosmética, no lácteo. Se podría resolver con una lista de exclusión
   (tipo contiene "corporal", "capilar" → no es alimentación).

2. **"PULEVA Eco Leche desnatada":** en Alcampo, "Eco" queda como parte
   del tipo ("Eco Leche desnatada") en vez de como sub-marca. No afecta
   a la búsqueda porque "leche" sigue estando al inicio del tipo.

3. **Marcas no reconocidas:** el 27,4% de productos no tiene marca
   detectada. Son principalmente marcas pequeñas con <2 apariciones
   (el umbral mínimo para auto-extracción) o productos genéricos sin marca.

## Alternativas consideradas

| Alternativa | Pros | Contras | Decisión |
|---|---|---|---|
| EAN-13 | Identificador universal | No disponible en las APIs | Descartado |
| SQLite FTS5 | Ranking por relevancia | No resuelve "café con leche" | Insuficiente solo |
| Embeddings/NLP | Semántico, flexible | Excesivo para el tamaño del proyecto | Descartado |
| Reglas + taxonomía | Rápido, determinista, explicable | Requiere mantenimiento manual | **Elegido** |
