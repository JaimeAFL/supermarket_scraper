# -*- coding: utf-8 -*-
"""Funciones de visualización con Plotly para el dashboard."""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    """Devuelve el nombre de la columna de fecha que exista en el DF."""
    for c in ('fecha_captura', 'fecha'):
        if c in df.columns:
            return c
    return None


# ── Histórico de precio ──────────────────────────────────────────────────────

def grafico_historico_precio(df_historico, nombre_producto=""):
    if df_historico.empty:
        return _grafico_vacio("No hay datos de precios disponibles")

    df = df_historico.copy()
    cf = _col_fecha(df)
    if cf is None:
        return _grafico_vacio("Columna de fecha no encontrada")

    df[cf] = pd.to_datetime(df[cf])

    fig = px.line(
        df, x=cf, y='precio',
        title=f"Evolución de precio: {nombre_producto}",
        labels={cf: 'Fecha', 'precio': 'Precio (€)'},
        markers=True,
    )
    fig.update_layout(
        hovermode='x unified',
        yaxis_tickprefix='€',
        xaxis_tickformat='%d/%m/%Y',
        template='plotly_white',
    )
    fig.update_traces(
        hovertemplate='Fecha: %{x|%d/%m/%Y}<br>Precio: €%{y:.2f}<extra></extra>'
    )
    return fig


# ── Comparativa supermercados (histórico) ─────────────────────────────────────

def grafico_comparativa_supermercados(df_historico_equiv):
    if df_historico_equiv.empty:
        return _grafico_vacio("No hay datos para comparar")

    df = df_historico_equiv.copy()
    cf = _col_fecha(df)
    if cf is None:
        return _grafico_vacio("Columna de fecha no encontrada")
    df[cf] = pd.to_datetime(df[cf])

    fig = go.Figure()
    for supermercado in df['supermercado'].unique():
        df_s = df[df['supermercado'] == supermercado]
        color = COLORES_SUPERMERCADO.get(supermercado, '#95A5A6')
        fig.add_trace(go.Scatter(
            x=df_s[cf], y=df_s['precio'],
            name=supermercado, mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(size=6),
            hovertemplate=(
                f'{supermercado}<br>'
                'Precio: €%{y:.2f}<br>'
                'Fecha: %{x|%d/%m/%Y}<extra></extra>'
            ),
        ))
    fig.update_layout(
        title="Comparativa de precios entre supermercados",
        xaxis_title="Fecha", yaxis_title="Precio (€)",
        yaxis_tickprefix='€',
        xaxis_tickformat='%d/%m/%Y',
        hovermode='x unified', template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='right', x=1),
    )
    return fig


# ── Barras precio actual (comparador) ────────────────────────────────────────

def grafico_barras_precio_actual(df_productos):
    if df_productos.empty:
        return _grafico_vacio("No hay datos disponibles")

    df = df_productos.sort_values('precio')
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in df['supermercado']]

    fig = go.Figure(go.Bar(
        x=df['supermercado'], y=df['precio'],
        marker_color=colores,
        text=[f"€{p:.2f}" for p in df['precio']],
        textposition='auto',
        hovertemplate='%{x}<br>Precio: €%{y:.2f}<extra></extra>',
    ))
    fig.update_layout(
        title="Precio actual por supermercado",
        yaxis_title="Precio (€)", yaxis_tickprefix='€',
        template='plotly_white',
    )
    return fig


def grafico_comparador_precios(df, titulo="Comparativa de precios"):
    """Barras horizontales agrupadas por super con etiqueta de precio y %."""
    if df.empty:
        return _grafico_vacio("No hay datos")

    df = df.sort_values('precio')
    precio_min = df['precio'].min()

    etiquetas = []
    for _, row in df.iterrows():
        pct = ((row['precio'] - precio_min) / precio_min * 100) if precio_min > 0 else 0
        if pct == 0:
            etiquetas.append(f"€{row['precio']:.2f} (el más barato)")
        else:
            etiquetas.append(f"€{row['precio']:.2f} (+{pct:.0f}%)")

    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in df['supermercado']]
    labels = [f"{row['supermercado']}<br><sub>{row.get('formato','')}</sub>"
              for _, row in df.iterrows()]

    fig = go.Figure(go.Bar(
        y=labels, x=df['precio'],
        orientation='h', marker_color=colores,
        text=etiquetas, textposition='outside',
        hovertemplate='%{y}<br>Precio: €%{x:.2f}<extra></extra>',
    ))
    fig.update_layout(
        title=titulo,
        xaxis_title="Precio (€)", xaxis_tickprefix="€",
        template='plotly_white',
        height=max(250, len(df) * 45 + 100),
        margin=dict(r=120),
        yaxis=dict(automargin=True),
    )
    return fig


# ── Productos por supermercado ────────────────────────────────────────────────

def grafico_productos_por_supermercado(stats):
    datos = stats.get('productos_por_supermercado', {})
    if not datos:
        return _grafico_vacio("No hay productos registrados")

    supers = list(datos.keys())
    cantidades = list(datos.values())
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in supers]

    fig = go.Figure(go.Bar(
        y=supers, x=cantidades, orientation='h',
        marker_color=colores,
        text=cantidades,
        textposition='inside',
        textfont=dict(color="white"),
    ))
    
    fig.update_layout(
        title="Productos por supermercado",
        xaxis_title="Número de productos",
        template='plotly_white', height=300,
    )
    return fig


# ── Distribución de precios (2 gráficos separados) ───────────────────────────

def grafico_distribucion_precios_zoom(df, supermercado=""):
    """Histograma zoom al percentil 95 donde se concentra la mayoría."""
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
        marker_color=color, opacity=0.25,
        marker_line_color="#FFFFFF", marker_line_width=1,
        hovertemplate="Rango: %{x:.2f} €<br>Productos: %{y}<extra></extra>",
    ))
    fig.add_vline(
        x=mediana, line_dash="dash", line_color="#000000", line_width=1,
        annotation_text=f"Mediana: {mediana:.2f} €",
        annotation_position="top right",
        annotation_font=dict(size=13, color="#1a1a1a", family="Arial Black"),
        annotation_bgcolor="rgba(255,255,255,0.85)",
        annotation_borderwidth=0,
    )
    fig.update_layout(
        title=f"{supermercado} — 95% de productos (hasta {p95:.0f} €)",
        xaxis_title="Precio (€)", xaxis_tickprefix="€",
        yaxis_title="Número de productos",
        template='plotly_white', height=400,
        annotations=[dict(
        text=(
            f"<span style='color:{color}'>{en_rango:,}</span> "
            f"de "
            f"<span style='color:{color}'>{total:,}</span> "
            f"productos mostrados"),
            xref="paper", yref="paper", x=0.98, y=0.95,
            showarrow=False, font=dict(size=11, color="gray"),
            xanchor="right",
        )],
    )
    return fig


def grafico_distribucion_precios_completa(df, supermercado=""):
    """Histograma con todos los precios en escala log para ver extremos."""
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
        hovertemplate="Rango: %{x:.2f} €<br>Productos: %{y}<extra></extra>",
    ))
    fig.update_layout(
        title=f"{supermercado} — Todos los precios (escala logarítmica)",
        xaxis_title="Precio (€)", xaxis_tickprefix="€",
        yaxis_title="Productos (escala log)", yaxis_type="log",
        template='plotly_white', height=400,
    )
    return fig


# Versión legacy (por si alguna página antigua la llama)
def grafico_distribucion_precios(df, supermercado=""):
    return grafico_distribucion_precios_zoom(df, supermercado)


# ── Gráfico vacío ────────────────────────────────────────────────────────────

def _grafico_vacio(mensaje="Sin datos disponibles"):
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=16, color='gray'),
    )
    fig.update_layout(
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        template='plotly_white', height=300,
    )
    return fig
