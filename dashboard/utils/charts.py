# -*- coding: utf-8 -*-

"""
Funciones de visualización con Plotly para el dashboard.
Usadas por las distintas páginas del dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


# Paleta de colores consistente para cada supermercado
COLORES_SUPERMERCADO = {
    'Mercadona': '#2ECC71',     # Verde
    'Carrefour': '#3498DB',     # Azul
    'Dia': '#E74C3C',           # Rojo
    'Alcampo': '#F39C12',       # Naranja
    'Eroski': '#9B59B6',        # Morado
}


def grafico_historico_precio(df_historico, nombre_producto=""):
    """
    Gráfico de línea con la evolución temporal del precio de un producto.

    Args:
        df_historico (pd.DataFrame): Con columnas: precio, fecha_captura.
        nombre_producto (str): Nombre para el título.

    Returns:
        plotly.graph_objects.Figure
    """
    if df_historico.empty:
        return _grafico_vacio("No hay datos de precios disponibles")

    df = df_historico.copy()
    df['fecha_captura'] = pd.to_datetime(df['fecha_captura'])

    fig = px.line(
        df,
        x='fecha_captura',
        y='precio',
        title=f"Evolución de precio: {nombre_producto}",
        labels={'fecha_captura': 'Fecha', 'precio': 'Precio (€)'},
        markers=True,
    )

    fig.update_layout(
        hovermode='x unified',
        yaxis_tickprefix='€',
        template='plotly_white',
    )

    return fig


def grafico_comparativa_supermercados(df_historico_equiv):
    """
    Gráfico de líneas superpuestas comparando el precio de un mismo
    producto en distintos supermercados.

    Args:
        df_historico_equiv (pd.DataFrame): Con columnas: supermercado, precio, fecha_captura.

    Returns:
        plotly.graph_objects.Figure
    """
    if df_historico_equiv.empty:
        return _grafico_vacio("No hay datos para comparar")

    df = df_historico_equiv.copy()
    df['fecha_captura'] = pd.to_datetime(df['fecha_captura'])

    fig = go.Figure()

    for supermercado in df['supermercado'].unique():
        df_super = df[df['supermercado'] == supermercado]
        color = COLORES_SUPERMERCADO.get(supermercado, '#95A5A6')

        fig.add_trace(go.Scatter(
            x=df_super['fecha_captura'],
            y=df_super['precio'],
            name=supermercado,
            mode='lines+markers',
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
        xaxis_title="Fecha",
        yaxis_title="Precio (€)",
        yaxis_tickprefix='€',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )

    return fig


def grafico_barras_precio_actual(df_productos):
    """
    Gráfico de barras comparando el precio actual de un producto
    entre supermercados.

    Args:
        df_productos (pd.DataFrame): Con columnas: supermercado, precio.

    Returns:
        plotly.graph_objects.Figure
    """
    if df_productos.empty:
        return _grafico_vacio("No hay datos disponibles")

    df = df_productos.sort_values('precio')
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in df['supermercado']]

    fig = go.Figure(go.Bar(
        x=df['supermercado'],
        y=df['precio'],
        marker_color=colores,
        text=[f"€{p:.2f}" for p in df['precio']],
        textposition='auto',
        hovertemplate='%{x}<br>Precio: €%{y:.2f}<extra></extra>',
    ))

    fig.update_layout(
        title="Precio actual por supermercado",
        yaxis_title="Precio (€)",
        yaxis_tickprefix='€',
        template='plotly_white',
    )

    return fig


def grafico_productos_por_supermercado(stats):
    """
    Gráfico de barras horizontal con el número de productos por supermercado.

    Args:
        stats (dict): Diccionario de estadísticas con 'productos_por_supermercado'.

    Returns:
        plotly.graph_objects.Figure
    """
    datos = stats.get('productos_por_supermercado', {})

    if not datos:
        return _grafico_vacio("No hay productos registrados")

    supermercados = list(datos.keys())
    cantidades = list(datos.values())
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in supermercados]

    fig = go.Figure(go.Bar(
        y=supermercados,
        x=cantidades,
        orientation='h',
        marker_color=colores,
        text=cantidades,
        textposition='auto',
    ))

    fig.update_layout(
        title="Productos por supermercado",
        xaxis_title="Número de productos",
        template='plotly_white',
        height=300,
    )

    return fig


def grafico_distribucion_precios(df, supermercado=""):
    """
    Histograma de distribución de precios de un supermercado.

    Args:
        df (pd.DataFrame): Con columna 'precio'.
        supermercado (str): Nombre del supermercado para el título.

    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return _grafico_vacio("No hay datos de precios")

    color = COLORES_SUPERMERCADO.get(supermercado, '#3498DB')

    fig = px.histogram(
        df,
        x='precio',
        nbins=50,
        title=f"Distribución de precios: {supermercado}",
        labels={'precio': 'Precio (€)', 'count': 'Productos'},
        color_discrete_sequence=[color],
    )

    fig.update_layout(
        xaxis_tickprefix='€',
        template='plotly_white',
        height=300,
    )

    return fig


def _grafico_vacio(mensaje="Sin datos disponibles"):
    """Crea un gráfico vacío con un mensaje centrado."""
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color='gray'),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        template='plotly_white',
        height=300,
    )
    return fig
