# -*- coding: utf-8 -*-
"""Dashboard principal de Supermarket Price Tracker."""

import sys, os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_DB_PATH = os.path.join(_PROJECT_ROOT, "database", "supermercados.db")
os.environ.setdefault("SUPERMARKET_DB_PATH", _DB_PATH)

import streamlit as st
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import (
    grafico_productos_por_supermercado,
    grafico_distribucion_precios_zoom,
    grafico_distribucion_precios_completa,
)

st.set_page_config(page_title="Supermarket Price Tracker", page_icon="",
                   layout="wide", initial_sidebar_state="expanded")

# ── Material Icons + CSS global ───────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Outlined"
      rel="stylesheet">
<style>
    .icon-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 4px;
    }
    .icon-header .material-icons-outlined {
        font-size: 28px;
        color: #5A6C7D;
    }
    .icon-header h2, .icon-header h3 {
        margin: 0;
        padding: 0;
    }
    .metric-row {
        display: flex;
        gap: 12px;
        margin: 16px 0 24px 0;
    }
    .metric-card {
        flex: 1;
        background: #FAFBFC;
        border: 1px solid #E8ECF0;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-card .metric-icon {
        font-size: 22px;
        color: #8B9DAF;
        margin-bottom: 4px;
    }
    .metric-card .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #1a1a1a;
        line-height: 1.2;
    }
    .metric-card .metric-label {
        font-size: 12px;
        color: #8B9DAF;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 2px;
    }
    .sidebar-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 20px;
        font-weight: 600;
        color: #1a1a1a;
    }
    .sidebar-title .material-icons-outlined {
        font-size: 24px;
        color: #5A6C7D;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────
st.sidebar.markdown(
    '<div class="sidebar-title">'
    '<span class="material-icons-outlined">shopping_cart</span>'
    'Price Tracker</div>', unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.caption(f"BD: `{os.path.basename(_DB_PATH)}`")

@st.cache_resource
def _init_db():
    inicializar_base_datos(_DB_PATH)

_init_db()
db = DatabaseManager(_DB_PATH)

if not os.path.exists(_DB_PATH):
    st.error(f"No se encontró la base de datos en:\n\n`{_DB_PATH}`")
    st.stop()

st.title("Supermarket Price Tracker")
st.markdown("Comparador de precios de supermercados españoles con histórico semanal.")

# ── Métricas en cards ─────────────────────────────────────────────────
stats = db.obtener_estadisticas()
cats = stats.get('productos_por_categoria', {})
dias = stats.get('dias_con_datos', 0)

metrics = [
    ("inventory_2",    f"{stats.get('total_productos', 0):,}",          "Productos"),
    ("sell",           f"{stats.get('total_registros_precios', 0):,}",  "Registros precio"),
    ("storefront",     str(stats.get('total_supermercados', 0)),        "Supermercados"),
    ("category",       str(len(cats)),                                   "Categorías"),
    ("calendar_month", str(dias),                                        "Días de datos"),
]

cards_html = '<div class="metric-row">'
for icon, value, label in metrics:
    cards_html += (
        f'<div class="metric-card">'
        f'<div class="metric-icon"><span class="material-icons-outlined">{icon}</span></div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div>'
        f'</div>'
    )
cards_html += '</div>'
st.markdown(cards_html, unsafe_allow_html=True)

if dias <= 1:
    st.info("Datos de un solo día. El histórico se construye ejecutando "
            "el scraper semanalmente.")

st.markdown("---")

# ── Productos por supermercado ────────────────────────────────────────
st.plotly_chart(grafico_productos_por_supermercado(stats),
                use_container_width=True)

# ── Distribución de precios ──────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div class="icon-header">'
    '<span class="material-icons-outlined">bar_chart</span>'
    '<h3>Distribución de precios</h3></div>', unsafe_allow_html=True)

supers_disponibles = list(stats.get('productos_por_supermercado', {}).keys())
if supers_disponibles:
    super_sel = st.selectbox("Supermercado:", supers_disponibles, key="dist_super")
    df_super = db.obtener_productos_con_precio_actual(supermercado=super_sel)
    st.plotly_chart(grafico_distribucion_precios_zoom(df_super, super_sel),
                    use_container_width=True)
    with st.expander("Ver distribución completa (incluye precios extremos)"):
        st.plotly_chart(grafico_distribucion_precios_completa(df_super, super_sel),
                        use_container_width=True)

# ── Resumen por supermercado ──────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div class="icon-header">'
    '<span class="material-icons-outlined">table_chart</span>'
    '<h3>Resumen por supermercado</h3></div>', unsafe_allow_html=True)

if stats.get('productos_por_supermercado'):
    datos_tabla = []
    for supermercado, total in stats['productos_por_supermercado'].items():
        df_s = db.obtener_productos_con_precio_actual(supermercado=supermercado)
        if not df_s.empty:
            datos_tabla.append({
                'Supermercado': supermercado, 'Productos': total,
                'Precio medio': f"{df_s['precio'].mean():.2f} €",
                'Mediana': f"{df_s['precio'].median():.2f} €",
                'Mínimo': f"{df_s['precio'].min():.2f} €",
                'Máximo': f"{df_s['precio'].max():.2f} €",
            })
    if datos_tabla:
        st.dataframe(pd.DataFrame(datos_tabla),
                     use_container_width=True, hide_index=True)

# ── Búsqueda rápida ──────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div class="icon-header">'
    '<span class="material-icons-outlined">search</span>'
    '<h3>Búsqueda rápida de productos</h3></div>', unsafe_allow_html=True)

col_b, col_s, col_c = st.columns([3, 1, 1])
with col_b:
    busqueda = st.text_input("Buscar:", placeholder="Ej: leche, café, aceite...",
                             key="busq_main")
with col_s:
    opciones_super = ['Todos'] + supers_disponibles
    filtro_super = st.selectbox("Supermercado:", opciones_super, key="filtro_busq")
with col_c:
    categorias = db.obtener_categorias()
    opciones_cat = ['Todas'] + [c[0] for c in categorias]
    filtro_cat = st.selectbox("Categoría:", opciones_cat, key="filtro_cat")

if busqueda:
    super_param = None if filtro_super == 'Todos' else filtro_super
    df_res = db.buscar_productos(nombre=busqueda, supermercado=super_param, limite=50)

    if not df_res.empty:
        if filtro_cat != 'Todas' and 'categoria_normalizada' in df_res.columns:
            df_res = df_res[df_res['categoria_normalizada'] == filtro_cat]

        if not df_res.empty:
            if 'prioridad' in df_res.columns:
                df_tipo = df_res[df_res['prioridad'] == 1]
                df_nombre = df_res[df_res['prioridad'] == 2]
            else:
                df_tipo = df_res
                df_nombre = pd.DataFrame()

            cols_mostrar = ['nombre', 'supermercado', 'precio', 'marca',
                            'categoria_normalizada', 'formato_normalizado']
            cols_mostrar = [c for c in cols_mostrar if c in df_res.columns]

            if not df_tipo.empty:
                st.caption(f"{len(df_tipo)} resultados directos (tipo = '{busqueda}')")
                st.dataframe(df_tipo[cols_mostrar],
                             use_container_width=True, hide_index=True)

            if not df_nombre.empty:
                with st.expander(f"Otros {len(df_nombre)} productos que mencionan '{busqueda}'"):
                    st.dataframe(df_nombre[cols_mostrar],
                                 use_container_width=True, hide_index=True)
        else:
            st.warning(f"No hay productos de categoría '{filtro_cat}' con '{busqueda}'.")
    else:
        st.warning(f"No se encontraron productos con '{busqueda}'.")

# ── Footer ────────────────────────────────────────────────────────────
st.markdown("---")
if stats.get('ultima_captura'):
    from datetime import datetime
    try:
        primera = datetime.fromisoformat(stats['primera_captura']).strftime('%d/%m/%Y %H:%M')
        ultima = datetime.fromisoformat(stats['ultima_captura']).strftime('%d/%m/%Y %H:%M')
        st.caption(f"Primera captura: {primera} · Última: {ultima}")
    except Exception:
        st.caption(f"Última captura: {stats['ultima_captura']}")
