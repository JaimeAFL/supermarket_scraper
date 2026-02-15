# -*- coding: utf-8 -*-

"""
Dashboard principal de Supermarket Price Tracker.

Ejecutar con:
    streamlit run dashboard/app.py

Página principal con resumen general y estadísticas.
Las subpáginas en dashboard/pages/ se descubren automáticamente.
"""

import sys
import os
import streamlit as st
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import (
    grafico_productos_por_supermercado,
    grafico_distribucion_precios,
)

# Añadir raíz del proyecto al path para que los imports funcionen
# tanto en local como en Streamlit Cloud
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# =============================================================================
# CONFIGURACIÓN DE LA PÁGINA (solo aquí, nunca en las subpáginas)
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
    "Datos actualizados diariamente vía [GitHub Actions]"
    "(https://github.com/tu-usuario/supermarket-price-tracker/actions)."
)


# =============================================================================
# CONEXIÓN A BASE DE DATOS
# =============================================================================
inicializar_base_datos()
db = DatabaseManager()


# =============================================================================
# PÁGINA PRINCIPAL
# =============================================================================
st.title("🛒 Supermarket Price Tracker")
st.markdown("Comparador de precios de supermercados españoles con histórico diario.")

# --- Métricas principales ---
stats = db.obtener_estadisticas()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Productos", f"{stats['total_productos']:,}")
with col2:
    st.metric("Registros de precio", f"{stats['total_registros_precios']:,}")
with col3:
    st.metric("Supermercados", stats['total_supermercados'])
with col4:
    st.metric("Equivalencias", stats['total_equivalencias'])

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
        super_seleccionado = st.selectbox(
            "Distribución de precios de:",
            supermercados_disponibles
        )
        df_super = db.obtener_productos_con_precio_actual(supermercado=super_seleccionado)
        st.plotly_chart(
            grafico_distribucion_precios(df_super, super_seleccionado),
            use_container_width=True
        )
    else:
        st.info("Ejecuta el scraper primero para ver datos aquí.")

# --- Tabla resumen por supermercado ---
st.markdown("---")
st.subheader("Resumen por supermercado")

if stats['productos_por_supermercado']:
    datos_tabla = []
    for supermercado, total in stats['productos_por_supermercado'].items():
        df_super = db.obtener_productos_con_precio_actual(supermercado=supermercado)
        if not df_super.empty:
            datos_tabla.append({
                'Supermercado': supermercado,
                'Productos': total,
                'Precio medio': f"{df_super['precio'].mean():.2f} €",
                'Precio mínimo': f"{df_super['precio'].min():.2f} €",
                'Precio máximo': f"{df_super['precio'].max():.2f} €"
            })

    if datos_tabla:
        st.dataframe(
            pd.DataFrame(datos_tabla),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info(
        "No hay datos todavía. Ejecuta el scraper con `python main.py` "
        "para empezar a recopilar precios."
    )

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
if stats['ultima_captura']:
    st.caption(f"Primera captura: {stats['primera_captura']} | Última captura: {stats['ultima_captura']}")
else:
    st.caption("Sin capturas de precios registradas.")
