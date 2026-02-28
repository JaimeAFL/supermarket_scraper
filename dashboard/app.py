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

st.set_page_config(page_title="Supermarket Price Tracker", page_icon="🛒",
                   layout="wide", initial_sidebar_state="expanded")

st.sidebar.title("🛒 Price Tracker")
st.sidebar.markdown("---")
st.sidebar.caption(f"BD: `{os.path.basename(_DB_PATH)}`")

@st.cache_resource
def _init_db():
    inicializar_base_datos(_DB_PATH)

_init_db()
db = DatabaseManager(_DB_PATH)

if not os.path.exists(_DB_PATH):
    st.error(f"⚠️ No se encontró la base de datos en:\n\n`{_DB_PATH}`")
    st.stop()

st.title("🛒 Supermarket Price Tracker")
st.markdown("Comparador de precios de supermercados españoles con histórico semanal.")

# ── Métricas ──────────────────────────────────────────────────────────
stats = db.obtener_estadisticas()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Productos", f"{stats.get('total_productos', 0):,}")
with col2:
    st.metric("Registros precio", f"{stats.get('total_registros_precios', 0):,}")
with col3:
    st.metric("Supermercados", stats.get('total_supermercados', 0))
with col4:
    cats = stats.get('productos_por_categoria', {})
    st.metric("Categorías", len(cats))
with col5:
    dias = stats.get('dias_con_datos', 0)
    st.metric("Días de datos", dias)

if dias <= 1:
    st.info("📊 Datos de un solo día. El histórico se construye ejecutando "
            "el scraper semanalmente.")

st.markdown("---")

# ── Productos por supermercado ────────────────────────────────────────
st.plotly_chart(grafico_productos_por_supermercado(stats),
                use_container_width=True)

# ── Distribución de precios ──────────────────────────────────────────
st.markdown("---")
st.subheader("Distribución de precios")

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
st.subheader("Resumen por supermercado")

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
st.subheader("🔍 Búsqueda rápida de productos")
st.caption("Busca por tipo de producto: 'leche' muestra solo lácteos, "
           "no 'café con leche'.")

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
        # Filtrar por categoría si se seleccionó
        if filtro_cat != 'Todas' and 'categoria_normalizada' in df_res.columns:
            df_res = df_res[df_res['categoria_normalizada'] == filtro_cat]

        if not df_res.empty:
            # Separar resultados primarios (tipo) y secundarios (nombre)
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
                st.caption(f"✅ {len(df_tipo)} resultados directos (tipo = '{busqueda}')")
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
