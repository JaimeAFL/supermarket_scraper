# -*- coding: utf-8 -*-

"""
Funciones de visualización con Plotly para el dashboard.

Genera gráficos interactivos de evolución de precios, comparativas
entre supermercados y estadísticas generales.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


# Colores asignados a cada supermercado
COLORES_SUPERMERCADO = {
    'Mercadona': '#2D8C3C',     # Verde Mercadona
    'Carrefour': '#004E9A',     # Azul Carrefour
    'Dia': '#E30613',           # Rojo Dia
    'Alcampo': '#009639',       # Verde Alcampo
    'Eroski': '#FF6600',        # Naranja Eroski
}


def grafico_historico_precio(df, nombre_producto=""):
    """
    Gráfico de línea con la evolución temporal del precio de un producto.
    
    Args:
        df (pd.DataFrame): DataFrame con columnas 'precio' y 'fecha_captura'.
        nombre_producto (str): Nombre para el título.
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return _grafico_vacio("Sin datos de precio")

    df = df.copy()
    df['fecha_captura'] = pd.to_datetime(df['fecha_captura'])

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['fecha_captura'],
        y=df['precio'],
        mode='lines+markers',
        name='Precio',
        line=dict(color='#2D8C3C', width=2),
        marker=dict(size=6),
        hovertemplate='%{x|%d/%m/%Y}<br>%{y:.2f} €<extra></extra>'
    ))

    # Línea de precio medio
    precio_medio = df['precio'].mean()
    fig.add_hline(
        y=precio_medio,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Media: {precio_medio:.2f} €",
        annotation_position="top left"
    )

    fig.update_layout(
        title=f"Evolución de precio: {nombre_producto}",
        xaxis_title="Fecha",
        yaxis_title="Precio (€)",
        hovermode='x unified',
        template='plotly_white',
        height=400,
        margin=dict(l=50, r=20, t=50, b=40)
    )

    return fig


def grafico_comparativa_supermercados(df):
    """
    Gráfico de líneas superpuestas para comparar el mismo producto
    en distintos supermercados a lo largo del tiempo.
    
    Args:
        df (pd.DataFrame): DataFrame con columnas 'supermercado', 'precio', 'fecha_captura'.
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return _grafico_vacio("Sin datos para comparar")

    df = df.copy()
    df['fecha_captura'] = pd.to_datetime(df['fecha_captura'])

    fig = go.Figure()

    for supermercado in df['supermercado'].unique():
        df_super = df[df['supermercado'] == supermercado]
        color = COLORES_SUPERMERCADO.get(supermercado, '#888888')

        fig.add_trace(go.Scatter(
            x=df_super['fecha_captura'],
            y=df_super['precio'],
            mode='lines+markers',
            name=supermercado,
            line=dict(color=color, width=2),
            marker=dict(size=5),
            hovertemplate=f'{supermercado}<br>%{{x|%d/%m/%Y}}<br>%{{y:.2f}} €<extra></extra>'
        ))

    fig.update_layout(
        title="Comparativa de precios entre supermercados",
        xaxis_title="Fecha",
        yaxis_title="Precio (€)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=450,
        margin=dict(l=50, r=20, t=60, b=40)
    )

    return fig


def grafico_barras_precio_actual(df_productos):
    """
    Gráfico de barras horizontales comparando el precio actual
    de un producto en cada supermercado.
    
    Args:
        df_productos (pd.DataFrame): Con columnas 'supermercado' y 'precio'.
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df_productos.empty:
        return _grafico_vacio("Sin datos")

    df = df_productos.sort_values('precio', ascending=True)

    colores = [COLORES_SUPERMERCADO.get(s, '#888888') for s in df['supermercado']]

    fig = go.Figure(go.Bar(
        x=df['precio'],
        y=df['supermercado'],
        orientation='h',
        marker_color=colores,
        text=[f"{p:.2f} €" for p in df['precio']],
        textposition='outside',
        hovertemplate='%{y}: %{x:.2f} €<extra></extra>'
    ))

    fig.update_layout(
        title="Precio actual por supermercado",
        xaxis_title="Precio (€)",
        template='plotly_white',
        height=max(200, len(df) * 60),
        margin=dict(l=100, r=60, t=50, b=40)
    )

    return fig


def grafico_distribucion_precios(df, supermercado=""):
    """
    Histograma de la distribución de precios de un supermercado.
    
    Args:
        df (pd.DataFrame): Con columna 'precio'.
        supermercado (str): Nombre del supermercado para el título.
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return _grafico_vacio("Sin datos")

    color = COLORES_SUPERMERCADO.get(supermercado, '#2D8C3C')

    fig = px.histogram(
        df, x='precio', nbins=50,
        title=f"Distribución de precios: {supermercado}",
        labels={'precio': 'Precio (€)', 'count': 'Productos'},
        color_discrete_sequence=[color]
    )

    fig.update_layout(
        template='plotly_white',
        height=350,
        margin=dict(l=50, r=20, t=50, b=40)
    )

    return fig


def grafico_productos_por_supermercado(stats):
    """
    Gráfico de donut con la cantidad de productos por supermercado.
    
    Args:
        stats (dict): Diccionario de estadísticas con clave 'productos_por_supermercado'.
    
    Returns:
        plotly.graph_objects.Figure
    """
    data = stats.get('productos_por_supermercado', {})
    
    if not data:
        return _grafico_vacio("Sin datos")

    supermercados = list(data.keys())
    cantidades = list(data.values())
    colores = [COLORES_SUPERMERCADO.get(s, '#888888') for s in supermercados]

    fig = go.Figure(go.Pie(
        labels=supermercados,
        values=cantidades,
        hole=0.4,
        marker_colors=colores,
        textinfo='label+value',
        hovertemplate='%{label}: %{value} productos<extra></extra>'
    ))

    fig.update_layout(
        title="Productos por supermercado",
        template='plotly_white',
        height=350,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


def _grafico_vacio(mensaje="Sin datos disponibles"):
    """Devuelve un gráfico vacío con un mensaje centrado."""
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color="gray")
    )
    fig.update_layout(
        template='plotly_white',
        height=300,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )
    return fig
