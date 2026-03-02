# -*- coding: utf-8 -*-
"""Funciones de visualizacion con Plotly para el dashboard."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
import uuid

COLORES_SUPERMERCADO = {
    'Mercadona': '#2ECC71',
    'Carrefour': '#3498DB',
    'Dia':       '#E74C3C',
    'Alcampo':   '#F39C12',
    'Eroski':    '#9B59B6',
}

# Estilo comun para todas las graficas
_LAYOUT_BASE = dict(
    template='plotly_white',
    font=dict(family="Inter, Segoe UI, Roboto, sans-serif", size=13),
    title_font=dict(size=16, color="#1A1A1A"),
    hoverlabel=dict(
        bgcolor="white",
        font_size=13,
        font_family="Inter, Segoe UI, Roboto, sans-serif",
        bordercolor="#E0E4E8",
    ),
    margin=dict(l=60, r=40, t=60, b=50),
)


def _col_fecha(df):
    for c in ('fecha_captura', 'fecha'):
        if c in df.columns:
            return c
    return None


def _get_formato(row):
    """Obtiene el formato normalizado o el original como fallback."""
    fmt = row.get('formato_normalizado', '') or row.get('formato', '') or ''
    return fmt.strip()


def grafico_historico_precio(df_historico, nombre_producto=""):
    if df_historico.empty:
        return _grafico_vacio("No hay datos de precios disponibles")
    df = df_historico.copy()
    cf = _col_fecha(df)
    if cf is None:
        return _grafico_vacio("Columna de fecha no encontrada")
    df[cf] = pd.to_datetime(df[cf])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[cf], y=df['precio'],
        mode='lines+markers',
        line=dict(color='#1565C0', width=2.5, shape='spline'),
        marker=dict(size=8, color='#1565C0',
                    line=dict(width=2, color='white')),
        fill='tozeroy',
        fillcolor='rgba(21, 101, 192, 0.08)',
        hovertemplate=(
            '<b>%{x|%d/%m/%Y}</b><br>'
            'Precio: <b>%{y:.2f} EUR</b>'
            '<extra></extra>'),
    ))
    layout_zoom = {**_LAYOUT_BASE, 'margin': dict(l=70, r=30, t=70, b=85)}
    fig.update_layout(
        **layout_zoom,
        title=f"Evolucion de precio: {nombre_producto}",
        xaxis_title="Fecha", yaxis_title="Precio (EUR)",
        yaxis_tickprefix="EUR ", xaxis_tickformat='%d/%m/%Y',
        hovermode='x unified',
        height=400,
    )
    return fig


def grafico_comparativa_supermercados(df_historico_equiv):
    if df_historico_equiv.empty:
        return _grafico_vacio("No hay datos para comparar")
    df = df_historico_equiv.copy()
    cf = _col_fecha(df)
    if cf is None:
        return _grafico_vacio("Columna de fecha no encontrada")
    df[cf] = pd.to_datetime(df[cf])

    fig = go.Figure()
    for s in df['supermercado'].unique():
        df_s = df[df['supermercado'] == s]
        color = COLORES_SUPERMERCADO.get(s, '#95A5A6')
        fig.add_trace(go.Scatter(
            x=df_s[cf], y=df_s['precio'], name=s,
            mode='lines+markers',
            line=dict(color=color, width=2.5, shape='spline'),
            marker=dict(size=7, line=dict(width=1.5, color='white')),
            hovertemplate=(
                f'<b>{s}</b><br>'
                'Precio: <b>%{y:.2f} EUR</b><br>'
                '%{x|%d/%m/%Y}'
                '<extra></extra>'),
        ))
    layout_full = {**_LAYOUT_BASE, 'margin': dict(l=70, r=30, t=70, b=85)}
    fig.update_layout(
        **layout_full,
        title="Comparativa de precios entre supermercados",
        xaxis_title="Fecha", yaxis_title="Precio (EUR)",
        yaxis_tickprefix="EUR ", xaxis_tickformat='%d/%m/%Y',
        hovermode='x unified',
        height=420,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            font=dict(size=12),
        ),
    )
    return fig


def grafico_barras_precio_actual(df_productos):
    if df_productos.empty:
        return _grafico_vacio("No hay datos disponibles")
    df = df_productos.sort_values('precio')
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6')
               for s in df['supermercado']]
    fig = go.Figure(go.Bar(
        x=df['supermercado'], y=df['precio'], marker_color=colores,
        text=[f"EUR {p:.2f}" for p in df['precio']],
        textposition='auto',
        hovertemplate='%{x}<br>Precio: EUR %{y:.2f}<extra></extra>'))
    fig.update_layout(
        **_LAYOUT_BASE,
        title="Precio actual por supermercado",
        yaxis_title="Precio (EUR)", yaxis_tickprefix="EUR ",
    )
    return fig


def grafico_comparador_precios(df, titulo="Comparativa de precios",
                               usar_precio_unitario=False):
    """Grafico de barras horizontales con formato normalizado en etiquetas.

    Se mantiene en charts.py para reutilizacion, aunque el comparador
    ya no lo invoca directamente.
    """
    if df.empty:
        return _grafico_vacio("No hay datos")

    col_precio = ('precio_unitario'
                  if usar_precio_unitario
                  and 'precio_unitario' in df.columns
                  else 'precio')
    df = df.dropna(subset=[col_precio]) if usar_precio_unitario else df
    if df.empty:
        return _grafico_vacio("No hay datos con precio unitario calculable")

    df = df.sort_values(col_precio)
    precio_min = df[col_precio].min()

    etiquetas = []
    for _, row in df.iterrows():
        fmt = _get_formato(row)
        precio_val = row[col_precio]
        if usar_precio_unitario and 'unidad_precio' in row.index:
            unidad_tag = (f" {row['unidad_precio']}"
                          if row.get('unidad_precio') else "")
        else:
            fmt_tag = f" ({fmt})" if fmt else ""
            unidad_tag = fmt_tag

        pct = (((precio_val - precio_min) / precio_min * 100)
               if precio_min > 0 else 0)
        if pct == 0:
            etiquetas.append(
                f"EUR {precio_val:.2f}{unidad_tag} — el mas barato")
        else:
            etiquetas.append(
                f"EUR {precio_val:.2f}{unidad_tag} (+{pct:.0f}%)")

    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6')
               for s in df['supermercado']]

    labels = []
    for _, row in df.iterrows():
        fmt = _get_formato(row)
        if fmt:
            labels.append(
                f"{row['supermercado']}<br><sub>{fmt}</sub>")
        else:
            labels.append(row['supermercado'])

    unidad_eje = ""
    if usar_precio_unitario and 'unidad_precio' in df.columns:
        unidad_eje = (df['unidad_precio'].dropna().iloc[0]
                      if not df['unidad_precio'].dropna().empty
                      else "EUR")
    else:
        unidad_eje = "EUR"

    fig = go.Figure(go.Bar(
        y=labels, x=df[col_precio], orientation='h',
        marker_color=colores,
        text=etiquetas, textposition='outside',
        hovertemplate='%{y}<br>Precio: EUR %{x:.2f}<extra></extra>'))
    fig.update_layout(
        **_LAYOUT_BASE,
        title=titulo,
        xaxis_title=f"Precio ({unidad_eje})",
        xaxis_tickprefix="EUR ",
        height=max(250, len(df) * 55 + 100),
        margin=dict(r=280, l=60, t=60, b=50),
        yaxis=dict(automargin=True),
    )
    return fig


def grafico_productos_por_supermercado(stats):
    datos = stats.get('productos_por_supermercado', {})
    if not datos:
        return _grafico_vacio("No hay productos registrados")

    # Ordenar de mayor a menor para mejor lectura visual
    datos_ord = dict(sorted(datos.items(), key=lambda x: x[1]))
    supers = list(datos_ord.keys())
    cantidades = list(datos_ord.values())
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in supers]

    fig = go.Figure(go.Bar(
        y=supers, x=cantidades, orientation='h',
        marker_color=colores,
        marker_line_color='rgba(255,255,255,0.6)',
        marker_line_width=1,
        text=cantidades,
        textposition='inside',
        textfont=dict(color='white', size=14, family="Inter"),
        hovertemplate='<b>%{y}</b><br>Productos: %{x:,}<extra></extra>',
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        title="Productos por supermercado",
        xaxis_title="Numero de productos",
        height=300,
    )
    return fig




def apex_productos_por_supermercado_html(stats):
    """HTML embebible con ApexCharts para productos por supermercado."""
    datos = stats.get('productos_por_supermercado', {})
    if not datos:
        return "<div style='padding:12px;color:#78909C'>No hay productos registrados</div>"

    datos_ord = dict(sorted(datos.items(), key=lambda x: x[1], reverse=True))
    supers = list(datos_ord.keys())
    cantidades = [int(v) for v in datos_ord.values()]
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in supers]

    chart_id = f"apex-prod-{uuid.uuid4().hex[:8]}"
    payload = {
        "supers": supers,
        "cantidades": cantidades,
        "colores": colores,
        "max_val": max(cantidades) if cantidades else 0,
        "tick_step": 2000,
    }

    return f"""
<div style="font-family:Inter,Segoe UI,Roboto,sans-serif;">
  <div id="{chart_id}" style="height:340px;"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
<script>
  const d = {json.dumps(payload)};
  const options = {{
    chart: {{ type: 'bar', height: 340, toolbar: {{ show: false }}, fontFamily: 'Inter, Segoe UI, Roboto, sans-serif' }},
    title: {{ text: 'productos por supermercado', align: 'left', style: {{ fontSize: '18px', fontWeight: 600, color: '#111827' }} }},
    series: [{{ name: 'Productos', data: d.cantidades }}],
    colors: d.colores,
    plotOptions: {{
      bar: {{
        horizontal: true,
        borderRadius: 3,
        distributed: true,
        dataLabels: {{ position: 'right' }}
      }}
    }},
    dataLabels: {{
      enabled: true,
      formatter: (v) => new Intl.NumberFormat('es-ES').format(v),
      style: {{ fontSize: '14px', fontWeight: 600, colors: ['#FFFFFF'] }},
      textAnchor: 'end',
      offsetX: -22,
      dropShadow: {{ enabled: false }}
    }},
    xaxis: {{
      categories: d.supers,
      min: 0,
      max: Math.max(d.tick_step, Math.ceil(d.max_val / d.tick_step) * d.tick_step),
      tickAmount: Math.max(1, Math.ceil(Math.max(d.tick_step, Math.ceil(d.max_val / d.tick_step) * d.tick_step) / d.tick_step)),
      labels: {{ formatter: (v) => `${{Math.round(v)}}` }}
    }},
    yaxis: {{ labels: {{ style: {{ colors: '#4B5563' }} }} }},
    grid: {{ borderColor: '#EEF2F7', strokeDashArray: 4, padding: {{ left: 0, right: 8 }} }},
    tooltip: {{
      theme: 'dark',
      y: {{ formatter: (v) => `${{new Intl.NumberFormat('es-ES').format(v)}} productos` }}
    }},
    legend: {{ show: false }}
  }};
  new ApexCharts(document.querySelector('#{chart_id}'), options).render();
</script>
"""

def grafico_distribucion_precios_zoom(df, supermercado=""):
    """Distribucion de precios (percentil 95) estilo dashboard de referencia."""
    if df.empty or 'precio' not in df.columns:
        return _grafico_vacio("No hay datos de precios")

    color = COLORES_SUPERMERCADO.get(supermercado, '#95A5A6')
    precios = df['precio'].dropna().astype(float)
    if precios.empty:
        return _grafico_vacio("No hay datos de precios")

    p95 = float(np.percentile(precios, 95))
    mediana = float(np.median(precios))
    media = float(np.mean(precios))
    precios_zoom = precios[precios <= p95]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=precios_zoom,
        xbins=dict(start=0, end=max(5, np.ceil(p95 / 5) * 5), size=5),
        marker_color=color,
        opacity=0.85,
        marker_line_color='rgba(255,255,255,0.55)',
        marker_line_width=1,
        hovertemplate=(
            "Rango (inicio): <b>%{x:.0f} EUR</b><br>"
            "Productos: <b>%{y}</b><extra></extra>"
        ),
    ))

    fig.add_vline(x=mediana, line_dash='dash', line_color='#1A1A1A', line_width=1.6)
    fig.add_vline(x=media, line_dash='dot', line_color='#607D8B', line_width=1.6)

    fig.add_annotation(
        x=mediana, y=1.02, xref='x', yref='paper',
        text=f"Mediana: {mediana:.2f} EUR",
        showarrow=False,
        bgcolor='rgba(255,255,255,0.92)',
        bordercolor='#C4CDD5', borderwidth=1, borderpad=3,
        font=dict(size=12, color='#2C3E50'),
    )
    fig.add_annotation(
        x=media, y=1.02, xref='x', yref='paper',
        text=f"Media: {media:.2f} EUR",
        showarrow=False,
        bgcolor='rgba(255,255,255,0.92)',
        bordercolor='#CFD8DC', borderwidth=1, borderpad=3,
        font=dict(size=12, color='#607D8B'),
    )

    fig.update_layout(
        **_LAYOUT_BASE,
        title=f"{supermercado} — 95% de productos",
        xaxis=dict(dtick=5, tickprefix=''),
        yaxis=dict(gridcolor='#E8EDF3'),
        xaxis_title='<b>Precio en €</b>',
        yaxis_title='<b>Número de productos</b>',
        height=520,
        bargap=0.08,
    )
    return fig


def grafico_distribucion_precios_completa(df, supermercado=""):
    """Distribucion completa de precios."""
    if df.empty or 'precio' not in df.columns:
        return _grafico_vacio("No hay datos de precios")
    color = COLORES_SUPERMERCADO.get(supermercado, '#95A5A6')
    precios = df['precio'].dropna().astype(float)
    if precios.empty:
        return _grafico_vacio("No hay datos de precios")

    mediana = float(np.median(precios))
    media = float(np.mean(precios))
    max_v = float(precios.max())

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=precios,
        xbins=dict(start=0, end=max(5, np.ceil(max_v / 5) * 5), size=5),
        marker_color=color,
        opacity=0.85,
        marker_line_color='rgba(255,255,255,0.55)',
        marker_line_width=1,
        hovertemplate="Rango (inicio): <b>%{x:.0f} EUR</b><br>Productos: <b>%{y}</b><extra></extra>",
    ))

    fig.add_vline(x=mediana, line_dash='dash', line_color='#1A1A1A', line_width=1.6)
    fig.add_vline(x=media, line_dash='dot', line_color='#607D8B', line_width=1.6)
    fig.add_annotation(x=mediana, y=1.02, xref='x', yref='paper', text=f"Mediana: {mediana:.2f} EUR", showarrow=False,
                       bgcolor='rgba(255,255,255,0.92)', bordercolor='#C4CDD5', borderwidth=1, borderpad=3,
                       font=dict(size=12, color='#2C3E50'))
    fig.add_annotation(x=media, y=1.02, xref='x', yref='paper', text=f"Media: {media:.2f} EUR", showarrow=False,
                       bgcolor='rgba(255,255,255,0.92)', bordercolor='#CFD8DC', borderwidth=1, borderpad=3,
                       font=dict(size=12, color='#607D8B'))

    fig.update_layout(
        **_LAYOUT_BASE,
        title=f"{supermercado} — Distribución completa",
        xaxis=dict(dtick=5, tickprefix=''),
        xaxis_title='<b>Precio en €</b>',
        yaxis_title='<b>Número de productos</b>',
        height=520,
        bargap=0.08,
    )
    return fig


def grafico_distribucion_precios(df, supermercado=""):
    return grafico_distribucion_precios_zoom(df, supermercado)



def apex_distribucion_precios_html(df, supermercado="", completa=False):
    """Devuelve HTML embebible con ApexCharts para distribucion de precios."""
    if df.empty or 'precio' not in df.columns:
        return "<div style='padding:12px;color:#78909C'>No hay datos de precios</div>"

    precios = df['precio'].dropna().astype(float)
    if precios.empty:
        return "<div style='padding:12px;color:#78909C'>No hay datos de precios</div>"

    color = COLORES_SUPERMERCADO.get(supermercado, '#95A5A6')
    mediana = float(np.median(precios))
    media = float(np.mean(precios))

    if completa:
        precios_plot = precios
        subtitulo = f"{supermercado} — Distribucion completa"
    else:
        p95 = float(np.percentile(precios, 95))
        precios_plot = precios[precios <= p95]
        subtitulo = f"{supermercado} — 95% de productos (hasta {p95:.0f} EUR)"

    max_val = float(precios_plot.max()) if not precios_plot.empty else float(precios.max())
    tick_max = int(max(5, np.ceil(max_val / 5.0) * 5))
    bins = np.arange(0, tick_max + 5, 5)
    counts, edges = np.histogram(precios_plot, bins=bins)
    categorias = [str(int(e)) for e in edges[:-1]]

    def _snap(v):
        return str(int(round(v / 5.0) * 5))

    mediana_tick = _snap(mediana)
    media_tick = _snap(media)

    chart_id = f"apex-dist-{uuid.uuid4().hex[:8]}"
    payload = {
        "categories": categorias,
        "counts": [int(c) for c in counts.tolist()],
        "color": color,
        "mediana_tick": mediana_tick,
        "media_tick": media_tick,
    }

    return f"""
<div style="font-family:Inter,Segoe UI,Roboto,sans-serif;">
  <div style="font-weight:600;font-size:18px;margin:0 0 6px 0;">{subtitulo}</div>

  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:8px 0 12px 0;">
    <div style="border:1px solid #D7DEE6;background:#FFFFFF;border-radius:12px;padding:12px 14px;">
      <div style="font-size:12px;letter-spacing:.02em;color:#5A6C7D;text-transform:uppercase;font-weight:600;">Mediana</div>
      <div style="font-size:34px;line-height:1.1;font-weight:700;color:#111827;margin-top:4px;">{mediana:.2f} €</div>
    </div>
    <div style="border:1px solid #D7DEE6;background:#FFFFFF;border-radius:12px;padding:12px 14px;">
      <div style="font-size:12px;letter-spacing:.02em;color:#5A6C7D;text-transform:uppercase;font-weight:600;">Media</div>
      <div style="font-size:34px;line-height:1.1;font-weight:700;color:#111827;margin-top:4px;">{media:.2f} €</div>
    </div>
  </div>

  <div style="display:flex;justify-content:flex-end;margin:0 0 8px 0;">
    <div style="border:1px solid #CFD8DC;background:rgba(255,255,255,.88);padding:6px 10px;border-radius:6px;color:#5A6C7D;font-size:12px;">
      <span style='color:{color};font-weight:700'>{len(precios_plot):,}</span> de <span style='color:{color};font-weight:700'>{len(precios):,}</span> productos
    </div>
  </div>

  <div id="{chart_id}" style="height:420px;"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
<script>
  const d = {json.dumps(payload)};
  const options = {{
    chart: {{ type: 'bar', height: 420, toolbar: {{ show: false }}, fontFamily: 'Inter, Segoe UI, Roboto, sans-serif' }},
    series: [{{ name: 'Productos', data: d.counts }}],
    colors: [d.color],
    plotOptions: {{ bar: {{ borderRadius: 3, columnWidth: '92%' }} }},
    dataLabels: {{ enabled: false }},
    xaxis: {{
      categories: d.categories,
      tickAmount: Math.max(2, d.categories.length-1),
      labels: {{ formatter: (v) => `${{v}}` }},
      title: {{ text: 'Precio en €', style: {{ fontSize: '20px', fontWeight: 700, color: '#111827' }} }}
    }},
    yaxis: {{
      title: {{ text: 'Numero de productos', style: {{ fontSize: '20px', fontWeight: 700, color: '#111827' }} }}
    }},
    grid: {{ borderColor: '#EEF2F7', strokeDashArray: 4, padding: {{ left: 0, right: 8 }} }},
    tooltip: {{
      theme: 'dark',
      x: {{ formatter: (v) => `${{v}} - ${{Number(v)+5}}` }},
      y: {{ formatter: (v) => `${{v}} productos` }}
    }},
    annotations: {{
      xaxis: [
        {{ x: d.mediana_tick, borderColor: '#1A1A1A', strokeDashArray: 5, label: {{ text: 'Mediana', orientation: 'horizontal', style: {{ background: '#FFFFFF', color: '#1A1A1A', borderColor: '#C4CDD5' }} }} }},
        {{ x: d.media_tick, borderColor: '#607D8B', strokeDashArray: 2, label: {{ text: 'Media', orientation: 'horizontal', style: {{ background: '#FFFFFF', color: '#546E7A', borderColor: '#CFD8DC' }} }} }}
      ]
    }}
  }};
  new ApexCharts(document.querySelector('#{chart_id}'), options).render();
</script>
"""

def _grafico_vacio(mensaje="Sin datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color='#78909C', family="Inter"))
    fig.update_layout(
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        template='plotly_white', height=300,
        margin=dict(l=40, r=40, t=40, b=40),
    )
    return fig
