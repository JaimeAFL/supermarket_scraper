# -*- coding: utf-8 -*-
"""Página del dashboard: Comparador de supermercados."""

import sys
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_DB_PATH = os.environ.get(
    "SUPERMARKET_DB_PATH",
    os.path.join(_PROJECT_ROOT, "database", "supermercados.db")
)

import streamlit as st
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from matching.product_matcher import ProductMatcher
from dashboard.utils.charts import (
    grafico_comparativa_supermercados,
    grafico_barras_precio_actual,
)

st.title("⚖️ Comparador de supermercados")
st.markdown("Compara el precio del mismo producto en distintos supermercados.")

inicializar_base_datos(_DB_PATH)
db      = DatabaseManager(_DB_PATH)
matcher = ProductMatcher(db)

tab1, tab2, tab3 = st.tabs([
    "Equivalencias guardadas",
    "Buscar equivalencias",
    "Auto-detectar equivalencias",
])

# --- PESTAÑA 1 ---
with tab1:
    grupos = db.listar_grupos_equivalencia()
    if grupos:
        grupo_sel = st.selectbox("Selecciona un grupo de equivalencia:", grupos)
        if grupo_sel:
            df_equiv = db.obtener_equivalencias(grupo_sel)
            if not df_equiv.empty:
                st.subheader(f"Precio actual: {grupo_sel}")
                st.plotly_chart(grafico_barras_precio_actual(df_equiv), use_container_width=True)

                st.subheader("Evolución temporal comparada")
                df_hist = db.obtener_historico_equivalencia(grupo_sel)
                st.plotly_chart(grafico_comparativa_supermercados(df_hist), use_container_width=True)

                with st.expander("Ver detalle"):
                    st.dataframe(
                        df_equiv[['nombre', 'supermercado', 'formato', 'precio']],
                        use_container_width=True,
                        hide_index=True,
                    )
    else:
        st.info("No hay equivalencias guardadas. Usa 'Buscar equivalencias' para crear algunas.")

# --- PESTAÑA 2 ---
with tab2:
    col_busq, col_umbral = st.columns([3, 1])
    with col_busq:
        texto_busqueda = st.text_input(
            "Producto a buscar:",
            placeholder="Ej: Coca-Cola Zero 2L",
            key="busqueda_equiv",
        )
    with col_umbral:
        umbral = st.slider("Umbral similitud:", 50, 100, 70, key="umbral_equiv")

    if texto_busqueda:
        df_similares = matcher.buscar_equivalencias_auto(texto_busqueda, umbral=umbral)
        if not df_similares.empty:
            st.success(f"Se encontraron {len(df_similares)} productos similares:")
            st.dataframe(
                df_similares[['nombre', 'supermercado', 'precio', 'puntuacion']],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")
            nombre_grupo = st.text_input("Nombre para el grupo:", value=texto_busqueda, key="nombre_grupo_nuevo")
            ids_seleccionados = st.multiselect(
                "Selecciona los productos equivalentes:",
                options=df_similares['id'].tolist(),
                format_func=lambda x: (
                    df_similares[df_similares['id'] == x].iloc[0]['nombre']
                    + f" ({df_similares[df_similares['id'] == x].iloc[0]['supermercado']})"
                ),
                default=df_similares['id'].tolist(),
            )

            if st.button("Guardar equivalencia", key="btn_guardar_equiv"):
                if ids_seleccionados and nombre_grupo:
                    matcher.crear_equivalencia_manual(nombre_grupo, ids_seleccionados)
                    st.success(f"Equivalencia '{nombre_grupo}' guardada.")
                    st.rerun()
                else:
                    st.warning("Selecciona al menos un producto y escribe un nombre.")
        else:
            st.warning(f"No se encontraron similares a '{texto_busqueda}' con umbral {umbral}.")

# --- PESTAÑA 3 ---
with tab3:
    umbral_auto = st.slider("Umbral para auto-detección:", 70, 100, 85, key="umbral_auto")
    if st.button("Ejecutar auto-detección", key="btn_auto"):
        with st.spinner("Buscando equivalencias automáticas..."):
            creadas = matcher.auto_crear_equivalencias(umbral=umbral_auto)
        if creadas > 0:
            st.success(f"Se crearon {creadas} equivalencias automáticas.")
            st.rerun()
        else:
            st.info("No se encontraron nuevas equivalencias con ese umbral.")
