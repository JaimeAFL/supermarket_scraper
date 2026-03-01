# -*- coding: utf-8 -*-
"""Página: Favoritos."""

import sys, os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_DB_PATH = os.environ.get("SUPERMARKET_DB_PATH",
                          os.path.join(_PROJECT_ROOT, "database", "supermercados.db"))

import streamlit as st
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos

st.set_page_config(page_title="Favoritos", page_icon="⭐", layout="wide")
st.title("Mis Favoritos")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

# ── Lista de favoritos actuales ──────────────────────────────────────
df_favs = db.obtener_favoritos()

if not df_favs.empty:
    st.subheader(f"Tienes {len(df_favs)} producto(s) en favoritos")

    cols = [c for c in ['nombre', 'supermercado', 'precio', 'marca',
                        'categoria_normalizada', 'formato', 'fecha_agregado']
            if c in df_favs.columns]
    st.dataframe(df_favs[cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    opciones_elim = {
        f"{row['nombre']} ({row['supermercado']})": row['id']
        for _, row in df_favs.iterrows()
    }
    fav_eliminar = st.selectbox("Eliminar favorito:", list(opciones_elim.keys()),
                                key="fav_eliminar")
    if st.button("🗑️ Eliminar", key="fav_btn_elim"):
        db.eliminar_favorito(opciones_elim[fav_eliminar])
        st.success("Eliminado.")
        st.rerun()
else:
    st.info("No tienes productos en favoritos. Busca un producto y añádelo.")

# ── Añadir favorito ──────────────────────────────────────────────────
st.markdown("---")
st.subheader("Añadir producto a favoritos")
st.caption("La búsqueda prioriza el tipo de producto.")

col_b, col_s = st.columns([3, 1])
with col_b:
    busqueda_fav = st.text_input("Buscar producto:",
                                 placeholder="Ej: leche, yogur, cerveza...",
                                 key="fav_busqueda")
with col_s:
    df_todos = db.obtener_productos_con_precio_actual()
    supers = (['Todos'] + sorted(df_todos['supermercado'].unique().tolist())
              if not df_todos.empty else ['Todos'])
    filtro_fav = st.selectbox("Supermercado:", supers, key="fav_filtro")

if busqueda_fav:
    super_param = None if filtro_fav == 'Todos' else filtro_fav
    df_res = db.buscar_productos(nombre=busqueda_fav, supermercado=super_param,
                                 limite=30)

    if not df_res.empty:
        # Excluir los que ya son favoritos
        ids_fav = set(df_favs['id'].tolist()) if not df_favs.empty else set()
        df_res = df_res[~df_res['id'].isin(ids_fav)]

        if df_res.empty:
            st.info("Todos los resultados ya están en favoritos.")
        else:
            opciones_add = {
                f"{row['nombre']} ({row['supermercado']}) - "
                f"{row.get('precio', '?')}€": row['id']
                for _, row in df_res.iterrows()
            }
            fav_agregar = st.selectbox(
                f"Productos encontrados ({len(df_res)}):",
                list(opciones_add.keys()), key="fav_agregar")

            if st.button("⭐ Añadir a favoritos", key="fav_btn_add"):
                db.agregar_favorito(opciones_add[fav_agregar])
                st.success("Añadido a favoritos.")
                st.rerun()
    else:
        st.warning(f"No se encontraron productos con '{busqueda_fav}'.")
