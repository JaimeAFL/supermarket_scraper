# -*- coding: utf-8 -*-
"""
Dashboard principal de Supermarket Price Tracker.

Ejecutar desde la raíz del proyecto con:
    streamlit run dashboard/app.py
"""

import sys
import os

# Añadir raíz del proyecto al path ANTES de los imports del proyecto
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── Ruta absoluta a la BD ─────────────────────────────────────────────────────
# Se calcula a partir de este archivo, no del CWD, para que funcione siempre.
_DB_PATH = os.path.join(_PROJECT_ROOT, "database", "supermercados.db")
os.environ.setdefault("SUPERMARKET_DB_PATH", _DB_PATH)
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import (
    grafico_productos_por_supermercado,
    grafico_distribucion_precios,
)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
st.set_page_config(
    page_title="Supermarket Price Tracker",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.title("🛒 Price Tracker")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "Datos actualizados diariamente vía "
    "[GitHub Actions](https://github.com/tu-usuario/supermarket-price-tracker/actions)."
)
st.sidebar.caption(f"BD: `{_DB_PATH}`")

# =============================================================================
# CONEXIÓN A BASE DE DATOS
# =============================================================================
@st.cache_resource
def _init_db():
    inicializar_base_datos(_DB_PATH)

_init_db()
db = DatabaseManager(_DB_PATH)

# Verificación rápida al arrancar
if not os.path.exists(_DB_PATH):
    st.error(
        f"⚠️ No se encontró la base de datos en:\n\n`{_DB_PATH}`\n\n"
        "Ejecuta primero:\n```\npython import_excel_to_db.py\n```"
    )
    st.stop()

# =============================================================================
# PÁGINA PRINCIPAL
# =============================================================================
st.title("🛒 Supermarket Price Tracker")
st.markdown("Comparador de precios de supermercados españoles con histórico diario.")

# --- Métricas principales ---
stats = db.obtener_estadisticas()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Productos", f"{stats.get('total_productos', 0):,}")
with col2:
    st.metric("Registros de precio", f"{stats.get('total_registros_precios', 0):,}")
with col3:
    st.metric("Supermercados", stats.get('total_supermercados', 0))
with col4:
    st.metric("Equivalencias", stats.get('total_equivalencias', 0))

st.markdown("---")

# --- Gráficos resumen ---
col_izq, col_der = st.columns(2)

with col_izq:
    st.plotly_chart(
        grafico_productos_por_supermercado(stats),
        use_container_width=True
    )

with col_der:
    supermercados_disponibles = list(stats.get('productos_por_supermercado', {}).keys())
    if supermercados_disponibles:
        super_seleccionado = st.selectbox("Distribución de precios de:", supermercados_disponibles)
        df_super = db.obtener_productos_con_precio_actual(supermercado=super_seleccionado)
        st.plotly_chart(
            grafico_distribucion_precios(df_super, super_seleccionado),
            use_container_width=True
        )
    else:
        st.info("Ejecuta `python import_excel_to_db.py` para cargar los datos.")

# --- Tabla resumen por supermercado ---
st.markdown("---")
st.subheader("Resumen por supermercado")

if stats.get('productos_por_supermercado'):
    datos_tabla = []
    for supermercado, total in stats['productos_por_supermercado'].items():
        df_super = db.obtener_productos_con_precio_actual(supermercado=supermercado)
        if not df_super.empty:
            datos_tabla.append({
                'Supermercado': supermercado,
                'Productos': total,
                'Precio medio': f"{df_super['precio'].mean():.2f} €",
                'Precio mínimo': f"{df_super['precio'].min():.2f} €",
                'Precio máximo': f"{df_super['precio'].max():.2f} €",
            })
    if datos_tabla:
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)
else:
    st.info("No hay datos. Ejecuta `python import_excel_to_db.py` primero.")

# --- Búsqueda rápida ---
st.markdown("---")
st.subheader("Búsqueda rápida de productos")
busqueda = st.text_input("Buscar producto por nombre:", placeholder="Ej: leche, coca-cola, pan...")

if busqueda:
    df_resultados = db.buscar_productos(nombre=busqueda, limite=20)
    if not df_resultados.empty:
        st.dataframe(
            df_resultados[['nombre', 'supermercado', 'categoria', 'formato']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning(f"No se encontraron productos con '{busqueda}'.")

# --- Info de última captura ---
st.markdown("---")
if stats.get('ultima_captura'):
    st.caption(
        f"Primera captura: {stats['primera_captura']} | "
        f"Última captura: {stats['ultima_captura']}"
    )
else:
    st.caption("Sin capturas de precios registradas.")
