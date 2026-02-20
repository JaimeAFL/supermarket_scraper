# -*- coding: utf-8 -*-
"""Página del dashboard: Histórico de precios."""

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
import pandas as pd
from datetime import datetime
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import grafico_historico_precio

st.set_page_config(page_title="Histórico de precios", page_icon="📈", layout="wide")
st.title("📈 Histórico de precios")
st.markdown("Selecciona un producto para ver cómo ha evolucionado su precio.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

# ── Info sobre días de datos ──────────────────────────────────────────────────
stats = db.obtener_estadisticas()
dias = stats.get('dias_con_datos', 0)
if dias <= 1:
    st.info(
        "📊 Solo hay datos de **1 día**. El gráfico de evolución se "
        "construirá automáticamente a medida que el scraper se ejecute "
        "en distintos días."
    )

# ── Filtros ───────────────────────────────────────────────────────────────────
col_filtro1, col_filtro2 = st.columns(2)

with col_filtro1:
    df_todos = db.obtener_productos_con_precio_actual()
    supers = (
        ['Todos'] + sorted(df_todos['supermercado'].unique().tolist())
        if not df_todos.empty else ['Todos']
    )
    supermercado_sel = st.selectbox("Supermercado:", supers)

with col_filtro2:
    busqueda = st.text_input(
        "Buscar producto:",
        placeholder="Ej: leche entera, arroz, coca-cola...",
    )

# ── Búsqueda y selección ─────────────────────────────────────────────────────
if busqueda:
    super_filtro = None if supermercado_sel == 'Todos' else supermercado_sel
    df_resultados = db.buscar_productos(
        nombre=busqueda, supermercado=super_filtro, limite=50,
    )

    if not df_resultados.empty:
        opciones = {
            f"{row['nombre']} ({row['supermercado']}) · {row.get('formato', '')}": row['id']
            for _, row in df_resultados.iterrows()
        }

        seleccion = st.selectbox(
            f"Productos encontrados ({len(df_resultados)}):",
            list(opciones.keys()),
        )
        producto_id = opciones[seleccion]

        st.markdown("---")

        df_historico = db.obtener_historico_precios(producto_id)

        if not df_historico.empty:
            nombre_producto = seleccion.split(" (")[0]
            precio_actual = df_historico.iloc[-1]['precio']

            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if len(df_historico) > 1:
                    precio_anterior = df_historico.iloc[-2]['precio']
                    variacion = precio_actual - precio_anterior
                    st.metric(
                        "Precio actual",
                        f"{precio_actual:.2f} €",
                        f"{variacion:+.2f} €",
                    )
                else:
                    st.metric("Precio actual", f"{precio_actual:.2f} €")
            with col2:
                st.metric(
                    "Precio mínimo", f"{df_historico['precio'].min():.2f} €"
                )
            with col3:
                st.metric(
                    "Precio máximo", f"{df_historico['precio'].max():.2f} €"
                )
            with col4:
                st.metric("Registros", len(df_historico))

            # Gráfico
            if len(df_historico) > 1:
                st.plotly_chart(
                    grafico_historico_precio(df_historico, nombre_producto),
                    use_container_width=True,
                )
            else:
                st.markdown(
                    f"**Precio registrado:** €{precio_actual:.2f}"
                )
                try:
                    fecha = datetime.fromisoformat(
                        df_historico.iloc[0]['fecha_captura']
                    )
                    st.caption(f"Capturado el {fecha.strftime('%d/%m/%Y a las %H:%M')}")
                except Exception:
                    st.caption(
                        f"Fecha: {df_historico.iloc[0]['fecha_captura']}"
                    )
                st.info(
                    "Solo hay 1 punto de datos. El gráfico aparecerá "
                    "cuando haya capturas de más de un día."
                )

            # Tabla de datos
            with st.expander("Ver datos en tabla"):
                df_mostrar = df_historico.copy()
                df_mostrar['precio'] = df_mostrar['precio'].apply(
                    lambda x: f"{x:.2f} €"
                )
                try:
                    df_mostrar['fecha_captura'] = pd.to_datetime(
                        df_mostrar['fecha_captura']
                    ).dt.strftime('%d/%m/%Y %H:%M')
                except Exception:
                    pass
                st.dataframe(
                    df_mostrar[['fecha_captura', 'precio']].rename(
                        columns={'fecha_captura': 'Fecha', 'precio': 'Precio'}
                    ),
                    use_container_width=True, hide_index=True,
                )
        else:
            st.info("Este producto aún no tiene registros de precio.")
    else:
        st.warning(f"No se encontraron productos con '{busqueda}'.")
else:
    st.info("Escribe el nombre de un producto para empezar a buscar.")
