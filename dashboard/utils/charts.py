# -*- coding: utf-8 -*-
"""Funciones de visualización con Plotly para el dashboard."""

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
    fig = px.line(df, x=cf, y='precio',
                  title=f"Evolución de precio: {nombre_producto}",
                  labels={cf: 'Fecha', 'precio': 'Precio (€)'},
                  markers=True)
    fig.update_layout(hovermode='x unified', yaxis_tickprefix='€',
                      xaxis_tickformat='%d/%m/%Y', template='plotly_white')
    fig.update_traces(
        hovertemplate='Fecha: %{x|%d/%m/%Y}<br>Precio: €%{y:.2f}<extra></extra>')
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
            x=df_s[cf], y=df_s['precio'], name=s, mode='lines+markers',
            line=dict(color=color, width=2), marker=dict(size=6),
            hovertemplate=f'{s}<br>Precio: €%{{y:.2f}}<br>'
                          f'Fecha: %{{x|%d/%m/%Y}}<extra></extra>'))
    fig.update_layout(title="Comparativa de precios entre supermercados",
                      xaxis_title="Fecha", yaxis_title="Precio (€)",
                      yaxis_tickprefix='€', xaxis_tickformat='%d/%m/%Y',
                      hovermode='x unified', template='plotly_white',
                      legend=dict(orientation='h', yanchor='bottom', y=1.02,
                                  xanchor='right', x=1))
    return fig


def grafico_barras_precio_actual(df_productos):
    if df_productos.empty:
        return _grafico_vacio("No hay datos disponibles")
    df = df_productos.sort_values('precio')
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in df['supermercado']]
    fig = go.Figure(go.Bar(
        x=df['supermercado'], y=df['precio'], marker_color=colores,
        text=[f"€{p:.2f}" for p in df['precio']], textposition='auto',
        hovertemplate='%{x}<br>Precio: €%{y:.2f}<extra></extra>'))
    fig.update_layout(title="Precio actual por supermercado",
                      yaxis_title="Precio (€)", yaxis_tickprefix='€',
                      template='plotly_white')
    return fig


def grafico_comparador_precios(df, titulo="Comparativa de precios",
                               usar_precio_unitario=False):
    """Gráfico de barras horizontales con formato normalizado en etiquetas.

    Args:
        usar_precio_unitario: si True, usa columna 'precio_unitario' en vez de 'precio'
    """
    if df.empty:
        return _grafico_vacio("No hay datos")

    col_precio = 'precio_unitario' if usar_precio_unitario and 'precio_unitario' in df.columns else 'precio'
    df = df.dropna(subset=[col_precio]) if usar_precio_unitario else df
    if df.empty:
        return _grafico_vacio("No hay datos con precio unitario calculable")

    df = df.sort_values(col_precio)
    precio_min = df[col_precio].min()

    etiquetas = []
    for _, row in df.iterrows():
        fmt = _get_formato(row)
        precio_val = row[col_precio]
        # Mostrar unidad si es precio unitario
        if usar_precio_unitario and 'unidad_precio' in row.index:
            unidad_tag = f" {row['unidad_precio']}" if row.get('unidad_precio') else ""
        else:
            fmt_tag = f" ({fmt})" if fmt else ""
            unidad_tag = fmt_tag

        pct = ((precio_val - precio_min) / precio_min * 100) if precio_min > 0 else 0
        if pct == 0:
            etiquetas.append(f"€{precio_val:.2f}{unidad_tag} — el más barato")
        else:
            etiquetas.append(f"€{precio_val:.2f}{unidad_tag} (+{pct:.0f}%)")

    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in df['supermercado']]

    # Labels del eje Y: supermercado + formato
    labels = []
    for _, row in df.iterrows():
        fmt = _get_formato(row)
        if fmt:
            labels.append(f"{row['supermercado']}<br><sub>{fmt}</sub>")
        else:
            labels.append(row['supermercado'])

    unidad_eje = ""
    if usar_precio_unitario and 'unidad_precio' in df.columns:
        unidad_eje = df['unidad_precio'].dropna().iloc[0] if not df['unidad_precio'].dropna().empty else "€"
    else:
        unidad_eje = "€"

    fig = go.Figure(go.Bar(
        y=labels, x=df[col_precio], orientation='h', marker_color=colores,
        text=etiquetas, textposition='outside',
        hovertemplate='%{y}<br>Precio: €%{x:.2f}<extra></extra>'))
    fig.update_layout(title=titulo,
                      xaxis_title=f"Precio ({unidad_eje})",
                      xaxis_tickprefix="€",
                      template='plotly_white',
                      height=max(250, len(df) * 45 + 100),
                      margin=dict(r=180), yaxis=dict(automargin=True))
    return fig


def grafico_productos_por_supermercado(stats):
    datos = stats.get('productos_por_supermercado', {})
    if not datos:
        return _grafico_vacio("No hay productos registrados")
    supers = list(datos.keys())
    cantidades = list(datos.values())
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in supers]
    fig = go.Figure(go.Bar(
        y=supers, x=cantidades, orientation='h',
        marker_color=colores, text=cantidades, textposition='auto'))
    fig.update_layout(title="Productos por supermercado",
                      xaxis_title="Número de productos",
                      template='plotly_white', height=300)
    return fig


def grafico_distribucion_precios_zoom(df, supermercado=""):
    if df.empty or 'precio' not in df.columns:
        return _grafico_vacio("No hay datos de precios")
    color = COLORES_SUPERMERCADO.get(supermercado, '#3498DB')
    precios = df['precio'].dropna()
    if precios.empty:
        return _grafico_vacio("No hay datos de precios")
    p95 = float(np.percentile(precios, 95))
    mediana = float(np.median(precios))
    precios_zoom = precios[precios <= p95]
    total = len(precios)
    en_rango = len(precios_zoom)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=precios_zoom, nbinsx=50,
        marker_color=color, opacity=0.45,
        marker_line_color=color, marker_line_width=0.5,
        hovertemplate="Rango: %{x:.2f} €<br>Productos: %{y}<extra></extra>"))
    fig.add_vline(
        x=mediana, line_dash="dash", line_color="#1a1a1a", line_width=2.5,
        annotation_text=f"Mediana: {mediana:.2f} €",
        annotation_position="top right",
        annotation_font=dict(size=13, color="#1a1a1a", family="Arial Black"),
        annotation_bgcolor="rgba(255,255,255,0.85)",
        annotation_bordercolor="#1a1a1a", annotation_borderwidth=1)
    fig.update_layout(
        title=f"{supermercado} — 95% de productos (hasta {p95:.0f} €)",
        xaxis_title="Precio (€)", xaxis_tickprefix="€",
        yaxis_title="Número de productos",
        template='plotly_white', height=400,
        annotations=[dict(
            text=f"{en_rango:,} de {total:,} productos mostrados",
            xref="paper", yref="paper", x=0.98, y=0.95,
            showarrow=False, font=dict(size=11, color="gray"), xanchor="right")])
    return fig


def grafico_distribucion_precios_completa(df, supermercado=""):
    if df.empty or 'precio' not in df.columns:
        return _grafico_vacio("No hay datos de precios")
    color = COLORES_SUPERMERCADO.get(supermercado, '#3498DB')
    precios = df['precio'].dropna()
    if precios.empty:
        return _grafico_vacio("No hay datos de precios")
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=precios, nbinsx=80,
        marker_color=color, opacity=0.45,
        marker_line_color=color, marker_line_width=0.5,
        hovertemplate="Rango: %{x:.2f} €<br>Productos: %{y}<extra></extra>"))
    fig.update_layout(
        title=f"{supermercado} — Todos los precios (escala logarítmica)",
        xaxis_title="Precio (€)", xaxis_tickprefix="€",
        yaxis_title="Productos (escala log)", yaxis_type="log",
        template='plotly_white', height=400)
    return fig


def grafico_distribucion_precios(df, supermercado=""):
    return grafico_distribucion_precios_zoom(df, supermercado)


def _grafico_vacio(mensaje="Sin datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(size=16, color='gray'))
    fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False),
                      template='plotly_white', height=300)
    return fig
