# -*- coding: utf-8 -*-
"""Funciones de visualizacion con Plotly para el dashboard."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

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
    fig.update_layout(
        **_LAYOUT_BASE,
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
    fig.update_layout(
        **_LAYOUT_BASE,
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


def grafico_distribucion_precios_zoom(df, supermercado=""):
    """Distribucion de precios (percentil 95) con diseno limpio sin duplicados."""
    if df.empty or 'precio' not in df.columns:
        return _grafico_vacio("No hay datos de precios")
    color = COLORES_SUPERMERCADO.get(supermercado, '#3498DB')
    precios = df['precio'].dropna()
    if precios.empty:
        return _grafico_vacio("No hay datos de precios")

    p95 = float(np.percentile(precios, 95))
    mediana = float(np.median(precios))
    media = float(np.mean(precios))
    precios_zoom = precios[precios <= p95]
    total = len(precios)
    en_rango = len(precios_zoom)

    fig = go.Figure()

    # Histograma principal (una sola traza para evitar elementos duplicados)
    fig.add_trace(go.Histogram(
        x=precios_zoom, nbinsx=min(45, max(20, int(np.sqrt(en_rango) * 2))),
        marker_color=color, opacity=0.55,
        marker_line_color='rgba(255,255,255,0.4)',
        marker_line_width=0.8,
        hovertemplate=(
            "Rango: <b>%{x:.2f} EUR</b><br>"
            "Productos: <b>%{y}</b>"
            "<extra></extra>"),
    ))

    # Lineas guia unicas
    fig.add_vline(
        x=mediana, line_dash="dash", line_color="#1A1A1A",
        line_width=2,
        annotation_text=f"Mediana: {mediana:.2f} EUR",
        annotation_position="top",
        annotation_font=dict(size=12, color="#1A1A1A",
                             family="Inter"),
        annotation_bgcolor="rgba(255,255,255,0.9)",
        annotation_bordercolor="#C4CDD5",
        annotation_borderwidth=1,
        annotation_borderpad=4,
    )

    fig.add_vline(
        x=media, line_dash="dot", line_color="#607D8B",
        line_width=1.8,
        annotation_text=f"Media: {media:.2f} EUR",
        annotation_position="top left",
        annotation_font=dict(size=11, color="#546E7A"),
        annotation_bgcolor="rgba(255,255,255,0.85)",
        annotation_bordercolor="#CFD8DC",
        annotation_borderwidth=1,
    )

    fig.update_layout(
        **_LAYOUT_BASE,
        title=(f"{supermercado} — 95% de productos "
               f"(hasta {p95:.0f} EUR)"),
        xaxis_title="Precio (EUR)", xaxis_tickprefix="EUR ",
        yaxis_title="Numero de productos",
        height=420,
        bargap=0.05,
    )

    # Contador de productos en una unica etiqueta (evita duplicados)
    fig.add_annotation(
        text=(
            f"<span style='color:{color}; font-weight:700'>{en_rango:,}</span>"
            " de "
            f"<span style='color:{color}; font-weight:700'>{total:,}</span>"
            " productos"
        ),
        xref="paper", yref="paper", x=0.98, y=0.95,
        showarrow=False,
        font=dict(size=12, color="#5A6C7D", family="Inter"),
        xanchor="right",
        bordercolor="rgba(0,0,0,0)", borderwidth=0,
        bgcolor="rgba(0,0,0,0)",
    )
    return fig


def grafico_distribucion_precios_completa(df, supermercado=""):
    """Distribucion completa de precios (escala logaritmica)."""
    if df.empty or 'precio' not in df.columns:
        return _grafico_vacio("No hay datos de precios")
    color = COLORES_SUPERMERCADO.get(supermercado, '#3498DB')
    precios = df['precio'].dropna()
    if precios.empty:
        return _grafico_vacio("No hay datos de precios")

    mediana = float(np.median(precios))
    media = float(np.mean(precios))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=precios, nbinsx=min(70, max(30, int(np.sqrt(len(precios)) * 2))),
        marker_color=color, opacity=0.55,
        marker_line_color='rgba(255,255,255,0.4)',
        marker_line_width=0.8,
        hovertemplate=(
            "Rango: <b>%{x:.2f} EUR</b><br>"
            "Productos: <b>%{y}</b>"
            "<extra></extra>"),
    ))

    fig.add_vline(
        x=mediana, line_dash="dash", line_color="#1A1A1A",
        line_width=2,
        annotation_text=f"Mediana: {mediana:.2f} EUR",
        annotation_position="top",
        annotation_font=dict(size=12, color="#1A1A1A",
                             family="Inter"),
        annotation_bgcolor="rgba(255,255,255,0.9)",
        annotation_bordercolor="#C4CDD5",
        annotation_borderwidth=1,
        annotation_borderpad=4,
    )

    fig.add_vline(
        x=media, line_dash="dot", line_color="#607D8B",
        line_width=1.8,
        annotation_text=f"Media: {media:.2f} EUR",
        annotation_position="top left",
        annotation_font=dict(size=11, color="#546E7A"),
        annotation_bgcolor="rgba(255,255,255,0.85)",
        annotation_bordercolor="#CFD8DC",
        annotation_borderwidth=1,
    )

    fig.update_layout(
        **_LAYOUT_BASE,
        title=(f"{supermercado} — Todos los precios "
               "(escala logaritmica)"),
        xaxis_title="Precio (EUR)", xaxis_tickprefix="EUR ",
        yaxis_title="Productos (escala log)", yaxis_type="log",
        height=420,
        bargap=0.05,
    )
    return fig


def grafico_distribucion_precios(df, supermercado=""):
    return grafico_distribucion_precios_zoom(df, supermercado)


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
