# -*- coding: utf-8 -*-
"""Página del dashboard: Productos favoritos."""

import sys
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_DB_PATH = os.environ.get(
    "SUPERMARKET_DB_PATH",
    os.path.join(_PROJECT_ROOT, "database", "supermercados.db"),
)

import streamlit as st
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import grafico_historico_precio, COLORES_SUPERMERCADO

st.set_page_config(page_title="Favoritos", page_icon="⭐", layout="wide")
st.title("⭐ Productos favoritos")
st.markdown(
    "Tus productos marcados como favoritos para seguimiento rápido de precios."
)

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

# ── Añadir favorito ──────────────────────────────────────────────────────────
with st.expander("Añadir producto a favoritos"):
    col_b, col_f = st.columns([3, 1])
    with col_b:
        busqueda_fav = st.text_input(
            "Buscar producto:",
            placeholder="Ej: aceite de oliva, yogur, coca-cola...",
            key="buscar_fav",
        )
    with col_f:
        df_tmp = db.obtener_productos_con_precio_actual()
        opciones_super = ['Todos']
        if not df_tmp.empty:
            opciones_super += sorted(df_tmp['supermercado'].unique().tolist())
        filtro_fav = st.selectbox(
            "Supermercado:", opciones_super, key="filtro_fav",
        )

    if busqueda_fav:
        super_param = None if filtro_fav == 'Todos' else filtro_fav
        df_resultados = db.buscar_productos(
            nombre=busqueda_fav, supermercado=super_param, limite=30,
        )
        if not df_resultados.empty:
            for _, row in df_resultados.iterrows():
                col_nombre, col_super, col_precio, col_btn = st.columns(
                    [3, 1.2, 0.8, 0.5]
                )
                with col_nombre:
                    st.write(f"**{row['nombre']}**")
                    st.caption(row.get('formato', ''))
                with col_super:
                    color = COLORES_SUPERMERCADO.get(
                        row['supermercado'], '#95A5A6'
                    )
                    st.markdown(
                        f"<span style='color:{color};font-weight:bold'>"
                        f"{row['supermercado']}</span>",
                        unsafe_allow_html=True,
                    )
                with col_precio:
                    precio = row.get('precio')
                    if precio:
                        st.write(f"€{precio:.2f}")
                with col_btn:
                    if st.button("⭐", key=f"add_fav_{row['id']}"):
                        db.agregar_favorito(row['id'])
                        st.success(f"Añadido a favoritos.")
                        st.rerun()
        else:
            st.warning(f"No se encontraron productos con '{busqueda_fav}'.")

# ── Lista de favoritos ────────────────────────────────────────────────────────
st.markdown("---")
df_favoritos = db.obtener_favoritos()

if not df_favoritos.empty:
    st.subheader(f"Tus favoritos ({len(df_favoritos)})")

    for _, fav in df_favoritos.iterrows():
        with st.container():
            col_info, col_precio, col_btn = st.columns([3, 2, 0.5])

            with col_info:
                color = COLORES_SUPERMERCADO.get(
                    fav['supermercado'], '#95A5A6'
                )
                st.markdown(f"**{fav['nombre']}**")
                st.markdown(
                    f"<span style='color:{color}'>{fav['supermercado']}</span>"
                    f" · {fav.get('formato', '')}",
                    unsafe_allow_html=True,
                )

            with col_precio:
                if fav.get('precio'):
                    st.metric("Último precio", f"{fav['precio']:.2f} €")
                else:
                    st.write("Sin precio registrado")

            with col_btn:
                if st.button(
                    "🗑️", key=f"del_fav_{fav['id']}",
                    help="Quitar de favoritos",
                ):
                    db.eliminar_favorito(fav['id'])
                    st.rerun()

            # Gráfico histórico (solo si hay más de 1 punto)
            df_hist = db.obtener_historico_precios(fav['id'])
            if len(df_hist) > 1:
                st.plotly_chart(
                    grafico_historico_precio(df_hist, fav['nombre']),
                    use_container_width=True,
                    key=f"chart_fav_{fav['id']}",
                )

            st.markdown("---")
else:
    st.info(
        "No tienes productos favoritos. Usa el buscador de arriba "
        "para añadir productos de cualquier supermercado."
    )
