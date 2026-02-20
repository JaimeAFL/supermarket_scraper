# -*- coding: utf-8 -*-
"""Página del dashboard: Comparador de supermercados."""

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
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import (
    grafico_comparador_precios,
    grafico_comparativa_supermercados,
    grafico_barras_precio_actual,
    COLORES_SUPERMERCADO,
)

st.set_page_config(page_title="Comparador", page_icon="⚖️", layout="wide")
st.title("⚖️ Comparador de supermercados")
st.markdown("Compara precios del mismo producto entre supermercados.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

tab1, tab2 = st.tabs(["🔍 Comparar precios", "💾 Equivalencias guardadas"])

# =============================================================================
# TAB 1 — Comparar precios (búsqueda directa)
# =============================================================================
with tab1:
    busqueda = st.text_input(
        "Buscar producto:",
        placeholder="Ej: coca-cola, leche entera, aceite oliva...",
        key="comparador_busqueda",
    )

    if busqueda:
        df = db.buscar_para_comparar(busqueda, limite_por_super=25)

        if df.empty:
            st.warning(f"No se encontraron productos con '{busqueda}'.")
        else:
            # ── Resumen por supermercado ───────────────────────────────────
            st.markdown("---")
            st.subheader(f"Resultados para «{busqueda}»")

            resumen = (
                df.groupby('supermercado')['precio']
                .agg(['count', 'min', 'median', 'max'])
                .reset_index()
            )
            resumen.columns = [
                'Supermercado', 'Productos', 'Más barato', 'Mediana', 'Más caro',
            ]

            # Precio mínimo global (el super más barato)
            idx_min = resumen['Más barato'].idxmin()
            super_barato = resumen.loc[idx_min, 'Supermercado']
            precio_min_global = resumen['Más barato'].min()

            # Añadir columna de diferencia %
            resumen['vs más barato'] = resumen['Más barato'].apply(
                lambda x: (
                    "⭐ Más barato"
                    if x == precio_min_global
                    else f"+{((x - precio_min_global) / precio_min_global * 100):.0f}%"
                )
            )
            resumen['Más barato'] = resumen['Más barato'].apply(
                lambda x: f"€{x:.2f}"
            )
            resumen['Mediana'] = resumen['Mediana'].apply(
                lambda x: f"€{x:.2f}"
            )
            resumen['Más caro'] = resumen['Más caro'].apply(
                lambda x: f"€{x:.2f}"
            )

            st.dataframe(resumen, use_container_width=True, hide_index=True)

            # ── Gráfico: producto más barato de cada super ────────────────
            st.markdown("---")
            st.subheader("Producto más barato por supermercado")
            st.caption(
                "Se compara el producto de menor precio de cada supermercado"
            )

            df_baratos = (
                df.sort_values('precio')
                .groupby('supermercado')
                .first()
                .reset_index()
            )
            st.plotly_chart(
                grafico_comparador_precios(
                    df_baratos,
                    f"Precio más bajo de «{busqueda}» por supermercado",
                ),
                use_container_width=True,
            )

            # ── Tabla completa con filtros ─────────────────────────────────
            st.markdown("---")
            st.subheader("Todos los productos encontrados")

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                supers_disponibles = sorted(df['supermercado'].unique())
                supers_sel = st.multiselect(
                    "Filtrar supermercados:",
                    supers_disponibles,
                    default=supers_disponibles,
                    key="comp_filtro_super",
                )
            with col_f2:
                rango = st.slider(
                    "Rango de precios (€):",
                    float(df['precio'].min()),
                    float(df['precio'].max()),
                    (float(df['precio'].min()), float(df['precio'].max())),
                    key="comp_filtro_precio",
                )

            df_filtrado = df[
                (df['supermercado'].isin(supers_sel))
                & (df['precio'] >= rango[0])
                & (df['precio'] <= rango[1])
            ].sort_values('precio')

            if not df_filtrado.empty:
                # Columna de % vs más barato
                p_min = df_filtrado['precio'].min()
                df_mostrar = df_filtrado[
                    ['nombre', 'supermercado', 'precio', 'formato']
                ].copy()
                df_mostrar['vs barato'] = df_mostrar['precio'].apply(
                    lambda x: (
                        "⭐"
                        if x == p_min
                        else f"+{((x - p_min) / p_min * 100):.0f}%"
                    )
                )
                df_mostrar['precio'] = df_mostrar['precio'].apply(
                    lambda x: f"€{x:.2f}"
                )
                st.dataframe(
                    df_mostrar, use_container_width=True, hide_index=True,
                )
                st.caption(f"{len(df_filtrado)} productos mostrados")
            else:
                st.info("No hay productos con esos filtros.")

            # ── Guardar como equivalencia ──────────────────────────────────
            with st.expander("Guardar como equivalencia"):
                st.markdown(
                    "Selecciona un producto de cada supermercado para "
                    "guardarlos como equivalentes y poder seguir su "
                    "evolución temporal."
                )
                nombre_equiv = st.text_input(
                    "Nombre del grupo:",
                    value=busqueda.title(),
                    key="nombre_equiv_nuevo",
                )
                ids_sel = st.multiselect(
                    "Productos equivalentes:",
                    df['id'].tolist(),
                    format_func=lambda x: (
                        f"{df[df['id']==x].iloc[0]['supermercado']} — "
                        f"€{df[df['id']==x].iloc[0]['precio']:.2f} — "
                        f"{df[df['id']==x].iloc[0]['nombre']}"
                    ),
                    key="ids_equiv_nuevo",
                )
                if st.button("Guardar equivalencia", key="btn_guardar_comp"):
                    if ids_sel and nombre_equiv:
                        db.crear_equivalencia(nombre_equiv, ids_sel)
                        st.success(f"Equivalencia «{nombre_equiv}» guardada.")
                        st.rerun()
                    else:
                        st.warning(
                            "Selecciona al menos un producto y escribe un nombre."
                        )
    else:
        st.info(
            "Escribe el nombre de un producto para comparar precios "
            "entre supermercados."
        )

# =============================================================================
# TAB 2 — Equivalencias guardadas
# =============================================================================
with tab2:
    grupos = db.listar_grupos_equivalencia()
    if grupos:
        grupo_sel = st.selectbox(
            "Selecciona un grupo de equivalencia:", grupos,
        )
        if grupo_sel:
            df_equiv = db.obtener_equivalencias(grupo_sel)
            if not df_equiv.empty:
                st.subheader(f"Precio actual: {grupo_sel}")
                st.plotly_chart(
                    grafico_barras_precio_actual(df_equiv),
                    use_container_width=True,
                )

                st.subheader("Evolución temporal comparada")
                df_hist = db.obtener_historico_equivalencia(grupo_sel)
                if not df_hist.empty and len(df_hist) > 1:
                    st.plotly_chart(
                        grafico_comparativa_supermercados(df_hist),
                        use_container_width=True,
                    )
                else:
                    st.info(
                        "Se necesitan datos de más de un día para mostrar "
                        "la evolución temporal. Ejecuta el scraper en "
                        "distintos días."
                    )

                with st.expander("Ver detalle"):
                    st.dataframe(
                        df_equiv[['nombre', 'supermercado', 'formato', 'precio']],
                        use_container_width=True, hide_index=True,
                    )
    else:
        st.info(
            "No hay equivalencias guardadas. Usa la pestaña "
            "«Comparar precios» para buscar productos y guardar "
            "equivalencias."
        )
