# -*- coding: utf-8 -*-
"""Página del dashboard: Productos favoritos."""

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
from dashboard.utils.charts import grafico_historico_precio

st.title("⭐ Productos favoritos")
st.markdown("Tus productos marcados como favoritos para seguimiento rápido de precios.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

# =============================================================================
# AÑADIR FAVORITO
# =============================================================================
with st.expander("Añadir producto a favoritos"):
    busqueda_fav = st.text_input(
        "Buscar producto:",
        placeholder="Ej: aceite de oliva, yogur...",
        key="buscar_fav",
    )

    if busqueda_fav:
        df_resultados = db.buscar_productos(nombre=busqueda_fav, limite=15)
        if not df_resultados.empty:
            for _, row in df_resultados.iterrows():
                col_nombre, col_btn = st.columns([4, 1])
                with col_nombre:
                    st.write(f"**{row['nombre']}** ({row['supermercado']}) - {row['formato']}")
                with col_btn:
                    if st.button("⭐", key=f"add_fav_{row['id']}"):
                        db.agregar_favorito(row['id'])
                        st.success(f"'{row['nombre']}' añadido a favoritos.")
                        st.rerun()
        else:
            st.warning(f"No se encontraron productos con '{busqueda_fav}'.")

# =============================================================================
# LISTA DE FAVORITOS
# =============================================================================
st.markdown("---")
df_favoritos = db.obtener_favoritos()

if not df_favoritos.empty:
    st.subheader(f"Tus favoritos ({len(df_favoritos)})")

    for _, fav in df_favoritos.iterrows():
        with st.container():
            col_info, col_precio, col_btn = st.columns([3, 2, 1])

            with col_info:
                st.markdown(f"**{fav['nombre']}**")
                st.caption(f"{fav['supermercado']} · {fav['formato']}")

            with col_precio:
                if fav.get('precio'):
                    st.metric("Último precio", f"{fav['precio']:.2f} €")
                else:
                    st.write("Sin precio registrado")

            with col_btn:
                if st.button("🗑️", key=f"del_fav_{fav['id']}", help="Quitar de favoritos"):
                    db.eliminar_favorito(fav['id'])
                    st.rerun()

            df_hist = db.obtener_historico_precios(fav['id'])
            if len(df_hist) > 1:
                st.plotly_chart(
                    grafico_historico_precio(df_hist, fav['nombre']),
                    use_container_width=True,
                    key=f"chart_fav_{fav['id']}",
                )

            st.markdown("---")
else:
    st.info("No tienes productos favoritos. Usa el buscador de arriba para añadir.")
