# Guía de estilos visuales del dashboard

Esta guía define la base visual del proyecto: tokens de diseño, convenciones de gráficos Plotly y reglas de componentes CSS. Su objetivo es mantener consistencia visual en todas las páginas del dashboard.

> **Nota:** los gráficos del dashboard están implementados con **Plotly** (vía `charts.py`), no con ApexCharts. Los tokens de diseño y principios de esta guía son aplicables a ambas librerías. El archivo `apexcharts_style_demo.html` existe como referencia visual alternativa.

---

## 1. Principios visuales

- Legibilidad por encima de decoración.
- Máximo contraste en datos clave (mediana, precio más barato, variación porcentual).
- Colores semánticos consistentes:
  - **Verde:** ahorro / precio más bajo
  - **Ámbar:** atención / precio medio
  - **Rojo:** sobreprecio / precio más alto
- Márgenes amplios para etiquetas externas: los gráficos de barras horizontales necesitan espacio a la derecha para mostrar el precio y el diferencial porcentual sin truncar.
- Sin emojis en ningún elemento de la UI.
- Iconos: **Material Icons Outlined** via CDN de Google (`material-icons-outlined`).

---

## 2. Tokens de diseño

### Colores del sistema

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#F7F9FC` | Fondo de página |
| `--surface` | `#FFFFFF` | Tarjetas y paneles |
| `--text` | `#1F2937` | Texto principal |
| `--muted` | `#6B7280` | Texto secundario, subtítulos |
| `--border` | `#E5E7EB` | Bordes de tarjetas |
| `--primary` | `#2F80ED` | Acento principal |
| `--success` | `#27AE60` | Verde: ahorro, más barato |
| `--warning` | `#F2C94C` | Ámbar: atención |
| `--danger` | `#EB5757` | Rojo: sobreprecio |

### Colores fijos por supermercado

Estos colores son inmutables y se aplican en todos los gráficos, tarjetas y etiquetas donde aparezca el nombre de la cadena:

| Supermercado | Color |
|---|---|
| Mercadona | `#2ECC71` |
| Carrefour | `#3498DB` |
| Dia | `#E74C3C` |
| Eroski | `#9B59B6` |
| Alcampo | `#F39C12` |
| Consum | `#E67E22` |
| Condis | `#C0392B` |

### Tipografía

- Familia: `Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif`
- Títulos: weight 600
- Texto y ejes: weight 400–500

### Espaciado y radios

- Grid base: 8px
- Padding tarjetas: 16px / 20px
- Radius tarjetas: 12px
- Radius labels y etiquetas: 8px

---

## 3. Convenciones para gráficos (Plotly)

### Histogramas de distribución de precios

- Opacidad de barras: `0.45` (evita saturación visual).
- Grid horizontal sutil, sin grid vertical.
- Línea de mediana: color negro, `dash="dash"`, sin caja/borde en la anotación.
- Línea de media: color gris, `dash="dot"`.
- Anotaciones de mediana/media: texto sin `bgcolor` ni `bordercolor`.
- Intervalo del eje X: múltiplos de 5€.

### Gráficos de evolución temporal (histórico)

- Línea suave (`line_shape="spline"`).
- Marcadores visibles en cada punto de dato.
- Formato de fecha en eje X: `%d/%m/%Y` (no ISO 8601).
- Hover: `%{y:.2f} €` + fecha en formato corto.
- Si solo hay un punto de datos: mostrar precio estático con `st.caption`, no intentar trazar línea.

### Gráficos de barras horizontales (comparador)

- Barras ordenadas por precio ascendente (más barato arriba).
- Etiquetas fuera de la barra, a la derecha: `"€X.XX (el más barato)"` / `"€X.XX (+Y%)"`.
- Margen derecho amplio (`margin_r` mínimo 120px) para que las etiquetas no se corten.
- Texto dentro de la barra en blanco si la barra es suficientemente larga.
- Color de barra según supermercado (usar tabla de colores fijos).

### Tooltips

- Fondo oscuro (`template="plotly_dark"` o fondo manual `#1F2937`).
- Texto claro, formato monoespaciado para precios.

### Leyenda

- Posición: superior izquierda.
- Tamaño de fuente: 12px.
- Sin borde.

---

## 4. Configuración base recomendada (Plotly)

```python
import plotly.graph_objects as go

def layout_base(titulo=""):
    return dict(
        title=dict(text=titulo, font=dict(size=14, color="#1F2937")),
        font=dict(
            family="Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            size=12,
            color="#1F2937"
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        xaxis=dict(
            gridcolor="#EEF2F7",
            gridwidth=1,
            showline=False,
        ),
        yaxis=dict(
            gridcolor="#EEF2F7",
            gridwidth=1,
            showgrid=True,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=12),
        ),
        margin=dict(l=60, r=120, t=60, b=60),
        hoverlabel=dict(
            bgcolor="#1F2937",
            font_color="#FFFFFF",
            font_size=12,
        ),
    )
```

---

## 5. Métricas (tarjetas KPI)

Las métricas del dashboard **no usan `st.metric`** de Streamlit. Se implementan como tarjetas CSS personalizadas en `styles.py` con la estructura:

```html
<div class="metric-card">
  <span class="material-icons-outlined">shopping_cart</span>
  <div class="metric-value">4.321</div>
  <div class="metric-label">Productos</div>
</div>
```

Estilos clave:
- Fondo `#FFFFFF`, borde `1px solid #E5E7EB`, radio `12px`.
- Valor: fuente 24px, weight 600, color `#1F2937`.
- Etiqueta: fuente 13px, color `#6B7280`.
- Icono: `color: #2F80ED`, tamaño 20px.

---

## 6. Demo visual

El archivo `apexcharts_style_demo.html` contiene una demo estática con:

- Histograma de distribución de precios con intervalos de 5€.
- Líneas de mediana y media con etiquetas sin número dentro de la gráfica.
- Tarjetas KPI inferiores con mediana, media y cobertura de productos.

Abrir directamente en el navegador (no requiere servidor).

---

## 7. Checklist antes de añadir un nuevo gráfico

- [ ] Usa los colores de supermercado de la tabla fija (no los colores por defecto de Plotly).
- [ ] Las fechas se muestran en formato `dd/mm/yyyy`, no ISO.
- [ ] Las anotaciones de mediana/media no tienen caja ni borde.
- [ ] El margen derecho es suficiente para etiquetas externas.
- [ ] El gráfico maneja correctamente el caso de 0 o 1 punto de datos.
- [ ] No hay emojis en etiquetas, tooltips ni títulos.
- [ ] El texto dentro de barras de colores oscuros es blanco.
