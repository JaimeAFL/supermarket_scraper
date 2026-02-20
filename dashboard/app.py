# -*- coding: utf-8 -*-
"""Dashboard principal de Supermarket Price Tracker."""

import sys
import os

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

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Supermarket Price Tracker",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🛒 Price Tracker")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "Datos actualizados diariamente vía "
    "[GitHub Actions](https://github.com/tu-usuario/supermarket-price-tracker/actions)."
)
st.sidebar.caption(f"BD: `{os.path.basename(_DB_PATH)}`")

# ── BD ────────────────────────────────────────────────────────────────────────
@st.cache_resource
def _init_db():
    inicializar_base_datos(_DB_PATH)

_init_db()
db = DatabaseManager(_DB_PATH)

if not os.path.exists(_DB_PATH):
    st.error(f"⚠️ No se encontró la base de datos en:\n\n`{_DB_PATH}`")
    st.stop()

# ── Título ────────────────────────────────────────────────────────────────────
st.title("🛒 Supermarket Price Tracker")
st.markdown("Comparador de precios de supermercados españoles con histórico diario.")

# ── Métricas ──────────────────────────────────────────────────────────────────
stats = db.obtener_estadisticas()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Productos", f"{stats.get('total_productos', 0):,}")
with col2:
    st.metric("Registros de precio", f"{stats.get('total_registros_precios', 0):,}")
with col3:
    st.metric("Supermercados", stats.get('total_supermercados', 0))
with col4:
    st.metric("Equivalencias", stats.get('total_equivalencias', 0))
with col5:
    dias = stats.get('dias_con_datos', 0)
    st.metric("Días de datos", dias)

if dias <= 1:
    st.info(
        "📊 **Histórico:** Actualmente tienes datos de un solo día. "
        "El histórico de precios se construye ejecutando el scraper diariamente. "
        "Cada ejecución añade un nuevo registro de precio por producto."
    )

st.markdown("---")

# ── Productos por supermercado ────────────────────────────────────────────────
st.plotly_chart(
    grafico_productos_por_supermercado(stats),
    use_container_width=True,
)

# ── Distribución de precios ──────────────────────────────────────────────────
st.markdown("---")
st.subheader("Distribución de precios")

supermercados_disponibles = list(
    stats.get('productos_por_supermercado', {}).keys()
)
if supermercados_disponibles:
    super_sel = st.selectbox(
        "Selecciona supermercado:",
        supermercados_disponibles,
        key="dist_super",
    )
    df_super = db.obtener_productos_con_precio_actual(supermercado=super_sel)

    # Gráfico 1: Zoom al 95% (fila completa)
    st.plotly_chart(
        grafico_distribucion_precios_zoom(df_super, super_sel),
        use_container_width=True,
    )

    # Gráfico 2: Completo con escala log (fila completa)
    with st.expander("Ver distribución completa (incluye precios extremos)"):
        st.plotly_chart(
            grafico_distribucion_precios_completa(df_super, super_sel),
            use_container_width=True,
        )
else:
    st.info("No hay datos disponibles.")

# ── Tabla resumen por supermercado ────────────────────────────────────────────
st.markdown("---")
st.subheader("Resumen por supermercado")

if stats.get('productos_por_supermercado'):
    datos_tabla = []
    for supermercado, total in stats['productos_por_supermercado'].items():
        df_s = db.obtener_productos_con_precio_actual(supermercado=supermercado)
        if not df_s.empty:
            datos_tabla.append({
                'Supermercado': supermercado,
                'Productos': total,
                'Precio medio': f"{df_s['precio'].mean():.2f} €",
                'Mediana': f"{df_s['precio'].median():.2f} €",
                'Precio mínimo': f"{df_s['precio'].min():.2f} €",
                'Precio máximo': f"{df_s['precio'].max():.2f} €",
            })
    if datos_tabla:
        st.dataframe(
            pd.DataFrame(datos_tabla),
            use_container_width=True, hide_index=True,
        )

# ── Búsqueda rápida ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Búsqueda rápida de productos")

col_busq, col_filtro = st.columns([3, 1])
with col_busq:
    busqueda = st.text_input(
        "Buscar producto por nombre:",
        placeholder="Ej: leche, coca-cola, pan...",
    )
with col_filtro:
    opciones_super = ['Todos'] + supermercados_disponibles
    filtro_super = st.selectbox("Supermercado:", opciones_super, key="filtro_busq")

if busqueda:
    super_param = None if filtro_super == 'Todos' else filtro_super
    df_resultados = db.buscar_productos(
        nombre=busqueda, supermercado=super_param, limite=50,
    )
    if not df_resultados.empty:
        st.caption(f"{len(df_resultados)} productos encontrados")
        # Colorear por supermercado
        st.dataframe(
            df_resultados[['nombre', 'supermercado', 'precio', 'formato', 'categoria']],
            use_container_width=True, hide_index=True,
        )
    else:
        st.warning(f"No se encontraron productos con '{busqueda}'.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
if stats.get('ultima_captura'):
    from datetime import datetime
    try:
        primera = datetime.fromisoformat(stats['primera_captura']).strftime('%d/%m/%Y %H:%M')
        ultima = datetime.fromisoformat(stats['ultima_captura']).strftime('%d/%m/%Y %H:%M')
        st.caption(f"Primera captura: {primera} · Última captura: {ultima}")
    except Exception:
        st.caption(
            f"Primera captura: {stats['primera_captura']} · "
            f"Última captura: {stats['ultima_captura']}"
        )
else:
    st.caption("Sin capturas de precios registradas.")
