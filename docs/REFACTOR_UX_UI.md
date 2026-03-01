# Refactor UX/UI del Dashboard — Guia de implementacion

## Archivos generados

```
supermarket-price-tracker/
├── .streamlit/
│   └── config.toml                      ← NUEVO: tema Streamlit base
├── dashboard/
│   ├── app.py                           ← MODIFICADO
│   ├── pages/
│   │   ├── 1_Historico_precios.py       ← MODIFICADO
│   │   ├── 2_Comparador.py             ← MODIFICADO
│   │   └── 3_Favoritos.py              ← MODIFICADO
│   └── utils/
│       ├── __init__.py                  ← NUEVO
│       ├── styles.py                    ← NUEVO: design system centralizado
│       ├── components.py                ← NUEVO: componentes UI reutilizables
│       └── charts.py                    ← SIN CAMBIOS (ya existente)
```

## Resumen de cambios

### NUEVO: `styles.py` — Design system unificado
Centraliza TODOS los estilos CSS que antes se duplicaban en cada pagina.
Una unica llamada `inyectar_estilos()` al inicio de cada pagina inyecta:

- **Material Icons Outlined** (CDN de Google)
- **Inter font** (CDN de Google Fonts)
- **Variables CSS** (:root) con tokens de color, spacing, radios, sombras
- **Clases CSS** para: icon-header, metric-card, insight-card, badge,
  product-card, pagination-info, estado-vacio, sidebar-title
- **Utilidades** de color: .text-success, .text-error, etc.

Tokens de color del sistema:
| Token | Valor | Uso |
|---|---|---|
| --color-primary | #1565C0 | Acciones principales, links |
| --color-success | #2E7D32 | Precios bajos, oportunidades |
| --color-error | #C62828 | Precios altos, alertas |
| --color-warning | #F57F17 | Precaucion |
| --color-neutral | #78909C | Estados neutros |
| --color-surface-variant | #F5F7FA | Fondo de tarjetas |
| --color-outline | #E0E4E8 | Bordes |
| --color-on-surface | #1A1A1A | Texto principal |
| --color-on-surface-variant | #5A6C7D | Texto secundario (pasa AA) |

### NUEVO: `components.py` — Componentes reutilizables
Funciones Python que generan HTML para st.markdown(unsafe_allow_html=True):

| Funcion | Descripcion | Origen |
|---|---|---|
| `encabezado(texto, icono, nivel)` | Header con Material Icon | Reemplaza HTML manual repetido |
| `fila_metricas([(icono, valor, label)])` | Fila de metric cards | Reemplaza HTML manual en app.py |
| `fila_insights(insights)` | Tarjetas de decision rapida | NUEVO para comparador/historico |
| `insight_card(...)` | Insight individual | NUEVO |
| `badge(texto, tipo, icono)` | Chip/badge de estado | NUEVO para favoritos |
| `estado_vacio(icono, titulo, detalle)` | Estado UX sin resultados | Reemplaza st.info/st.warning |
| `paginar_dataframe(df, clave, filas)` | Paginacion completa | NUEVO |
| `barra_filtros(db, clave, ...)` | Filtros estandarizados | NUEVO |
| `tarjeta_producto_html(...)` | Card de producto | NUEVO para favoritos |
| `sidebar_branding(db_path)` | Sidebar unificado | Extraido de app.py |

### NUEVO: `.streamlit/config.toml` — Tema base
Configura los colores base del framework Streamlit para que los widgets
nativos (botones, sliders, etc.) usen la paleta del design system.

### MODIFICADO: `app.py` — Pagina principal
- Eliminado bloque CSS duplicado → `inyectar_estilos()`
- Metricas via `fila_metricas()` en vez de HTML manual
- Headers via `encabezado()` en vez de HTML manual
- Busqueda via `barra_filtros()` estandarizada
- Paginacion en resultados de busqueda
- Estados vacios con `estado_vacio()`
- Cache `@st.cache_data(ttl=300)` en carga de productos por super
- `st.spinner()` durante cargas

### MODIFICADO: `1_Historico_precios.py`
- Eliminado bloque CSS duplicado → `inyectar_estilos()`
- st.metric → `fila_insights()` con iconos de tendencia
- Variacion con iconos: trending_up (rojo), trending_down (verde)
- Filtros via `barra_filtros()` estandarizada
- Estados vacios con `estado_vacio()`
- `st.spinner()` durante busquedas

### MODIFICADO: `2_Comparador.py`
- Eliminado bloque CSS duplicado → `inyectar_estilos()`
- **Flujo guiado**: buscar → insight cards → tabla resumen → grafico → lista completa
- Insight cards con: mas barato + mediana + ahorro maximo
- Paginacion en tabla de productos y menciones secundarias
- Filtros + estados vacios mejorados
- `st.spinner()` durante busquedas

### MODIFICADO: `3_Favoritos.py`
- Eliminado bloque CSS duplicado → `inyectar_estilos()`
- **Enriquecimiento de favoritos**: consulta historico por producto para calcular:
  - estado: minimo / bajo / subio / estable
  - variacion vs registro anterior
  - minimo/maximo historico
- Metricas resumen: total, en minimo, bajaron, subieron
- Seccion "Oportunidades" destacada con tarjetas de producto
- Tarjetas de producto con badges de estado y colores por supermercado
- Orden por oportunidad (default) o precio/nombre
- Paginacion en lista de favoritos
- Doble confirmacion para eliminacion
- Busqueda para anadir via `barra_filtros()`

## Mapeo del plan UX/UI a la implementacion

| Bloque del plan | Solucion | Tipo |
|---|---|---|
| A. Design system | `styles.py` + `config.toml` | 40% Material Design CSS + tokens |
| B. Paginacion | `paginar_dataframe()` en components.py | 60% Streamlit nativo |
| C. Filtros unificados | `barra_filtros()` en components.py | 90% Streamlit nativo |
| D. Comparador guiado | `fila_insights()` + flujo reestructurado | 50/50 |
| E. Favoritos decision | `_enriquecer_favoritos()` + `tarjeta_producto_html()` | 50/50 |
| F. Accesibilidad | aria-label, role, contraste AA en tokens | CSS |
| G. Rendimiento | `@st.cache_data`, `st.spinner` | 100% Streamlit nativo |

## Elementos Streamlit nativos utilizados

| Elemento | Donde |
|---|---|
| `st.set_page_config` | Todas las paginas |
| `st.tabs` | Comparador |
| `st.columns` | Filtros, paginacion, layouts |
| `st.text_input` | Busquedas |
| `st.selectbox` | Filtros, seleccion productos |
| `st.multiselect` | Filtro supermercados |
| `st.slider` | Rango de precios |
| `st.select_slider` | Selector de pagina |
| `st.button` | Navegacion, acciones |
| `st.expander` | Contenido secundario |
| `st.dataframe` | Tablas de datos |
| `st.plotly_chart` | Graficos |
| `st.spinner` | Feedback de carga |
| `st.caption` | Texto secundario |
| `st.info/warning/error` | Mensajes del sistema |
| `st.checkbox` | Confirmacion de eliminacion |
| `st.session_state` | Paginacion persistente |
| `@st.cache_data` | Cache de queries (TTL 5min) |
| `@st.cache_resource` | Cache de init_db |
| `st.rerun` | Refresh tras acciones |

## Elementos Material Design utilizados

| Elemento | Implementacion | Donde |
|---|---|---|
| Material Icons Outlined | CDN + span.material-icons-outlined | Headers, metricas, badges, estados |
| Card (elevated) | .metric-card, .insight-card, .product-card | Metricas, insights, favoritos |
| Chip/Badge | .badge con variantes de color | Estados en favoritos, comparador |
| Typography scale | Inter font + tokens de tamano | Toda la app |
| Color system | :root variables con paleta Material | Toda la app |
| Surface/elevation | background + box-shadow | Cards |
| States (empty/error) | .estado-vacio con icono grande | Busquedas sin resultado |
| Divider | .section-divider | Separadores de seccion |

## Notas de implementacion

1. **charts.py NO se modifica** — ya usa COLORES_SUPERMERCADO y funciona bien.
   styles.py reexporta los mismos colores para consistencia.

2. **database_db_manager.py NO se modifica** — las queries existentes son
   suficientes. La paginacion se hace en Python (slice del DataFrame).
   Para escala mayor, se podria migrar a LIMIT/OFFSET en SQL.

3. **Los acentos en el codigo se han evitado** en los textos visibles
   para prevenir problemas de encoding en distintos terminales.
   Los strings internos de Python (variables, docstrings) mantienen
   ASCII seguro.

4. **Accesibilidad**: se ha anadido `role="group"` y `aria-label`
   en grupos de metricas/insights, y `aria-hidden="true"` en iconos
   decorativos. El color `#5A6C7D` para texto secundario pasa
   contraste AA (4.5:1) sobre fondo blanco.
