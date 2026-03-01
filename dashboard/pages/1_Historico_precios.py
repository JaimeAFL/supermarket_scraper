# -*- coding: utf-8 -*-
"""Página: Histórico de precios."""

import sys, os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_DB_PATH = os.environ.get("SUPERMARKET_DB_PATH",
                          os.path.join(_PROJECT_ROOT, "database", "supermercados.db"))

import streamlit as st
import pandas as pd
from datetime import datetime
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import grafico_historico_precio

st.set_page_config(page_title="Histórico de precios", page_icon="", layout="wide")

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
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="icon-header">'
    '<span class="material-icons-outlined">trending_up</span>'
    '<h2>Histórico de precios</h2></div>', unsafe_allow_html=True)
st.markdown("Selecciona un producto para ver cómo ha evolucionado su precio.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

stats = db.obtener_estadisticas()
dias = stats.get('dias_con_datos', 0)
if dias <= 1:
    st.info("Solo hay datos de **1 día**. El gráfico aparecerá cuando "
            "el scraper se ejecute en distintos días.")

col_f1, col_f2 = st.columns(2)
with col_f1:
    df_todos = db.obtener_productos_con_precio_actual()
    supers = (['Todos'] + sorted(df_todos['supermercado'].unique().tolist())
              if not df_todos.empty else ['Todos'])
    super_sel = st.selectbox("Supermercado:", supers)

with col_f2:
    busqueda = st.text_input("Buscar producto:",
                             placeholder="Ej: leche entera, arroz, café...")

if busqueda:
    super_filtro = None if super_sel == 'Todos' else super_sel
    df_res = db.buscar_productos(nombre=busqueda, supermercado=super_filtro, limite=50)

    if not df_res.empty:
        def _label(row):
            cat = row.get('categoria_normalizada', '')
            cat_tag = f" [{cat}]" if cat else ""
            return f"{row['nombre']} ({row['supermercado']}){cat_tag}"

        opciones = {_label(row): row['id'] for _, row in df_res.iterrows()}
        seleccion = st.selectbox(f"Productos encontrados ({len(df_res)}):",
                                 list(opciones.keys()))
        producto_id = opciones[seleccion]

        st.markdown("---")
        df_hist = db.obtener_historico_precios(producto_id)

        if not df_hist.empty:
            nombre_prod = seleccion.split(" (")[0]
            precio_actual = df_hist.iloc[-1]['precio']

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if len(df_hist) > 1:
                    var = precio_actual - df_hist.iloc[-2]['precio']
                    st.metric("Precio actual", f"{precio_actual:.2f} €",
                              f"{var:+.2f} €")
                else:
                    st.metric("Precio actual", f"{precio_actual:.2f} €")
            with col2:
                st.metric("Mínimo", f"{df_hist['precio'].min():.2f} €")
            with col3:
                st.metric("Máximo", f"{df_hist['precio'].max():.2f} €")
            with col4:
                st.metric("Registros", len(df_hist))

            if len(df_hist) > 1:
                st.plotly_chart(grafico_historico_precio(df_hist, nombre_prod),
                                use_container_width=True)
            else:
                st.markdown(f"**Precio registrado:** {precio_actual:.2f} €")
                try:
                    fecha = datetime.fromisoformat(df_hist.iloc[0]['fecha_captura'])
                    st.caption(f"Capturado el {fecha.strftime('%d/%m/%Y a las %H:%M')}")
                except Exception:
                    pass
                st.info("Solo hay 1 punto de datos. El gráfico aparecerá "
                        "cuando haya capturas de más de un día.")

            with st.expander("Ver datos en tabla"):
                df_m = df_hist.copy()
                df_m['precio'] = df_m['precio'].apply(lambda x: f"{x:.2f} €")
                try:
                    df_m['fecha_captura'] = pd.to_datetime(
                        df_m['fecha_captura']).dt.strftime('%d/%m/%Y %H:%M')
                except Exception:
                    pass
                st.dataframe(
                    df_m[['fecha_captura', 'precio']].rename(
                        columns={'fecha_captura': 'Fecha', 'precio': 'Precio'}),
                    use_container_width=True, hide_index=True)
        else:
            st.info("Este producto no tiene registros de precio.")
    else:
        st.warning(f"No se encontraron productos con '{busqueda}'.")
else:
    st.info("Escribe el nombre de un producto para empezar.")
