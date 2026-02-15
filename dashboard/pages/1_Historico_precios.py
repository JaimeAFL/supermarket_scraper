# -*- coding: utf-8 -*-

"""
Página del dashboard: Histórico de precios.

Permite seleccionar un producto y ver su evolución de precio
a lo largo del tiempo con un gráfico interactivo.
"""

import sys
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
import pandas as pd
from database.db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import grafico_historico_precio


st.title("📈 Histórico de precios")
st.markdown("Selecciona un producto para ver cómo ha evolucionado su precio.")


# =============================================================================
# CONEXIÓN
# =============================================================================
inicializar_base_datos()
db = DatabaseManager()


# =============================================================================
# FILTROS
# =============================================================================
col_filtro1, col_filtro2 = st.columns(2)

with col_filtro1:
    df_todos = db.obtener_productos_con_precio_actual()
    supermercados = ['Todos'] + sorted(df_todos['supermercado'].unique().tolist()) if not df_todos.empty else ['Todos']

    supermercado_sel = st.selectbox("Supermercado:", supermercados)

with col_filtro2:
    busqueda = st.text_input("Buscar producto:", placeholder="Ej: leche entera, arroz...")


# =============================================================================
# BÚSQUEDA Y SELECCIÓN
# =============================================================================
if busqueda:
    super_filtro = None if supermercado_sel == 'Todos' else supermercado_sel
    df_resultados = db.buscar_productos(nombre=busqueda, supermercado=super_filtro, limite=30)

    if not df_resultados.empty:
        opciones = {
            f"{row['nombre']} ({row['supermercado']}) - {row['formato']}": row['id']
            for _, row in df_resultados.iterrows()
        }

        seleccion = st.selectbox(
            f"Productos encontrados ({len(df_resultados)}):",
            list(opciones.keys())
        )

        producto_id = opciones[seleccion]

        st.markdown("---")

        df_historico = db.obtener_historico_precios(producto_id)

        if not df_historico.empty:
            nombre_producto = seleccion.split(" (")[0]
            precio_actual = df_historico.iloc[-1]['precio']
            precio_anterior = df_historico.iloc[-2]['precio'] if len(df_historico) > 1 else precio_actual
            variacion = precio_actual - precio_anterior
            num_registros = len(df_historico)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Precio actual", f"{precio_actual:.2f} €", f"{variacion:+.2f} €")
            with col2:
                st.metric("Precio mínimo", f"{df_historico['precio'].min():.2f} €")
            with col3:
                st.metric("Precio máximo", f"{df_historico['precio'].max():.2f} €")
            with col4:
                st.metric("Registros", num_registros)

            st.plotly_chart(
                grafico_historico_precio(df_historico, nombre_producto),
                use_container_width=True
            )

            with st.expander("Ver datos en tabla"):
                df_mostrar = df_historico.copy()
                df_mostrar['precio'] = df_mostrar['precio'].apply(lambda x: f"{x:.2f} €")
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        else:
            st.info("Este producto aún no tiene registros de precio históricos.")
    else:
        st.warning(f"No se encontraron productos con '{busqueda}'.")
else:
    st.info("Escribe el nombre de un producto para empezar a buscar.")
