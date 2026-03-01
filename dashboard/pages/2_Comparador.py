# -*- coding: utf-8 -*-
"""Pagina: Comparador de precios entre supermercados."""

import sys, os

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_DB_PATH = os.environ.get(
    "SUPERMARKET_DB_PATH",
    os.path.join(_PROJECT_ROOT, "database", "supermercados.db"))

import streamlit as st
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import grafico_comparador_precios
from matching.normalizer import calcular_precio_unitario
from dashboard.utils.styles import inyectar_estilos
from dashboard.utils.components import (
    encabezado, fila_insights, estado_vacio,
    paginar_dataframe, badge_html,
)

st.set_page_config(page_title="Comparador", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Comparador de precios", "balance")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)


def _añadir_precio_unitario(df):
    """Anade columnas precio_unitario y unidad_precio al DataFrame."""
    precios_u = []
    unidades = []
    for _, row in df.iterrows():
        fmt = row.get('formato_normalizado', '') or ''
        precio = row.get('precio', 0) or 0
        pu, unidad = calcular_precio_unitario(precio, fmt)
        precios_u.append(pu)
        unidades.append(unidad)
    df = df.copy()
    df['precio_unitario'] = precios_u
    df['unidad_precio'] = unidades
    return df


# ═══════════════════════════════════════════════════════════════════════
# TABS PRINCIPALES
# ═══════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["Comparar precios", "Equivalencias guardadas"])

with tab1:
    st.markdown(
        "Busca un producto y compara precios **unitarios** (EUR/L, EUR/kg) "
        "entre supermercados.")

    busqueda = st.text_input(
        "Buscar producto:",
        placeholder="Ej: leche entera, cafe, aceite oliva...",
        key="comp_busqueda")

    if busqueda:
        with st.spinner("Buscando..."):
            df = db.buscar_para_comparar(busqueda, limite_por_super=25)

        if df.empty:
            estado_vacio(
                "search_off",
                f"No se encontraron productos con '{busqueda}'",
                "Prueba con otro termino de busqueda."
            )
        else:
            df = _añadir_precio_unitario(df)

            if 'prioridad' in df.columns:
                df_tipo = df[df['prioridad'] == 1]
                df_otros = df[df['prioridad'] == 2]
            else:
                df_tipo = df
                df_otros = pd.DataFrame()

            df_principal = df_tipo if not df_tipo.empty else df
            supers_disp = sorted(
                df_principal['supermercado'].unique().tolist())

            # ── PASO 1: Resultados encontrados ────────────────────
            encabezado(f"Resultados para «{busqueda}»", "query_stats", nivel=3)
            st.caption(
                f"{len(df_tipo)} resultados directos"
                + (f", {len(df_otros)} menciones secundarias"
                   if not df_otros.empty else ""))

            if not df_principal.empty:
                df_con_pu = df_principal[
                    df_principal['precio_unitario'].notna()]
                if not df_con_pu.empty:
                    moda = df_con_pu['unidad_precio'].mode()
                    unidad_comun = (moda.iloc[0]
                                    if not moda.empty else "")
                else:
                    unidad_comun = ""

                # ── PASO 2: Insights de decisión rápida ──────────
                usa_unitario = (not df_con_pu.empty and unidad_comun)

                if usa_unitario:
                    df_misma_unidad = df_con_pu[
                        df_con_pu['unidad_precio'] == unidad_comun]
                else:
                    df_misma_unidad = pd.DataFrame()

                if usa_unitario and not df_misma_unidad.empty:
                    # Mejor precio unitario
                    idx_mejor = df_misma_unidad['precio_unitario'].idxmin()
                    mejor = df_misma_unidad.loc[idx_mejor]
                    peor_pu = df_misma_unidad['precio_unitario'].max()
                    mediana_pu = df_misma_unidad['precio_unitario'].median()
                    ahorro_max = peor_pu - mejor['precio_unitario']
                    n_supers = df_misma_unidad['supermercado'].nunique()

                    fila_insights([
                        {
                            "icono": "emoji_events", "tipo": "success",
                            "titulo": "Mas barato",
                            "valor": (f"{mejor['precio_unitario']:.2f} "
                                      f"{unidad_comun}"),
                            "detalle": mejor['supermercado'],
                        },
                        {
                            "icono": "analytics", "tipo": "neutral",
                            "titulo": "Mediana",
                            "valor": f"{mediana_pu:.2f} {unidad_comun}",
                            "detalle": (
                                f"{n_supers} supermercados comparados"),
                        },
                        {
                            "icono": "savings", "tipo": "primary",
                            "titulo": "Ahorro maximo",
                            "valor": f"{ahorro_max:.2f} {unidad_comun}",
                            "detalle": (
                                f"vs el mas caro "
                                f"({peor_pu:.2f} {unidad_comun})"),
                        },
                    ])

                    # ── Tabla resumen ─────────────────────────────
                    resumen = (df_misma_unidad
                               .groupby('supermercado')['precio_unitario']
                               .agg(['count', 'min', 'median', 'max'])
                               .reset_index())
                    resumen.columns = [
                        'Supermercado', 'Productos',
                        f'Mas barato ({unidad_comun})',
                        f'Mediana ({unidad_comun})',
                        f'Mas caro ({unidad_comun})',
                    ]
                    pu_min = resumen[
                        f'Mas barato ({unidad_comun})'].min()
                    resumen['vs mas barato'] = resumen[
                        f'Mas barato ({unidad_comun})'
                    ].apply(
                        lambda x: "Mas barato" if x == pu_min
                        else f"+{((x - pu_min) / pu_min * 100):.0f}%"
                    )
                    for col in [
                        f'Mas barato ({unidad_comun})',
                        f'Mediana ({unidad_comun})',
                        f'Mas caro ({unidad_comun})',
                    ]:
                        resumen[col] = resumen[col].apply(
                            lambda x: f"{x:.2f} EUR")
                    st.dataframe(
                        resumen, use_container_width=True,
                        hide_index=True)

                    # ── Gráfico ───────────────────────────────────
                    df_baratos = (
                        df_misma_unidad
                        .sort_values('precio_unitario')
                        .groupby('supermercado').first()
                        .reset_index())
                    st.plotly_chart(
                        grafico_comparador_precios(
                            df_baratos,
                            (f"Precio unitario mas bajo de "
                             f"«{busqueda}» ({unidad_comun})"),
                            usar_precio_unitario=True),
                        use_container_width=True)

                else:
                    # Fallback: precio absoluto
                    st.caption(
                        "No hay datos de formato suficientes para "
                        "comparar por precio unitario. "
                        "Mostrando precio absoluto.")

                    idx_mejor_abs = df_principal['precio'].idxmin()
                    mejor_abs = df_principal.loc[idx_mejor_abs]
                    mediana_abs = df_principal['precio'].median()

                    fila_insights([
                        {
                            "icono": "emoji_events", "tipo": "success",
                            "titulo": "Mas barato",
                            "valor": f"{mejor_abs['precio']:.2f} EUR",
                            "detalle": mejor_abs['supermercado'],
                        },
                        {
                            "icono": "analytics", "tipo": "neutral",
                            "titulo": "Precio mediana",
                            "valor": f"{mediana_abs:.2f} EUR",
                            "detalle": (
                                f"{df_principal['supermercado'].nunique()} "
                                "supermercados"),
                        },
                    ])

                    resumen = (
                        df_principal.groupby('supermercado')['precio']
                        .agg(['count', 'min', 'median', 'max'])
                        .reset_index())
                    resumen.columns = [
                        'Supermercado', 'Productos',
                        'Mas barato', 'Mediana', 'Mas caro',
                    ]
                    precio_min_global = resumen['Mas barato'].min()
                    resumen['vs mas barato'] = resumen[
                        'Mas barato'
                    ].apply(
                        lambda x: "Mas barato" if x == precio_min_global
                        else f"+{((x - precio_min_global) / precio_min_global * 100):.0f}%"
                    )
                    for col in ['Mas barato', 'Mediana', 'Mas caro']:
                        resumen[col] = resumen[col].apply(
                            lambda x: f"{x:.2f} EUR")
                    st.dataframe(
                        resumen, use_container_width=True,
                        hide_index=True)

                    df_baratos = (
                        df_principal.sort_values('precio')
                        .groupby('supermercado').first()
                        .reset_index())
                    st.plotly_chart(
                        grafico_comparador_precios(
                            df_baratos,
                            (f"Precio mas bajo de «{busqueda}» "
                             "por supermercado")),
                        use_container_width=True)

            # ── PASO 3: Todos los productos (con filtros + paginación)
            st.markdown("---")
            encabezado(
                "Todos los productos encontrados",
                "format_list_bulleted", nivel=3)

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                supers_sel = st.multiselect(
                    "Filtrar supermercados:",
                    supers_disp, default=supers_disp,
                    key="comp_supers")
            with col_f2:
                if not df_principal.empty:
                    pmin = float(df_principal['precio'].min())
                    pmax = float(df_principal['precio'].max())
                    rango = (
                        st.slider(
                            "Rango de precios (EUR):", pmin, pmax,
                            (pmin, pmax), key="comp_rango")
                        if pmin < pmax else (pmin, pmax))
                else:
                    rango = (0.0, 999.0)

            df_filtrado = df_principal[
                (df_principal['supermercado'].isin(supers_sel))
                & (df_principal['precio'] >= rango[0])
                & (df_principal['precio'] <= rango[1])
            ]

            if df_filtrado['precio_unitario'].notna().any():
                df_filtrado = df_filtrado.sort_values(
                    'precio_unitario', na_position='last')
            else:
                df_filtrado = df_filtrado.sort_values('precio')

            if df_filtrado.empty:
                estado_vacio(
                    "filter_list_off",
                    "Sin resultados con los filtros actuales",
                    "Prueba ampliando el rango de precios o "
                    "seleccionando mas supermercados."
                )
            else:
                cols = [
                    'nombre', 'supermercado', 'precio',
                    'formato_normalizado', 'precio_unitario',
                    'unidad_precio', 'marca', 'categoria_normalizada',
                ]
                cols = [c for c in cols if c in df_filtrado.columns]

                # Paginación
                df_pagina = paginar_dataframe(
                    df_filtrado, "pag_comp", filas_por_pagina=20)
                st.dataframe(
                    df_pagina[cols],
                    use_container_width=True, hide_index=True)

            # ── Menciones secundarias ─────────────────────────────
            if not df_otros.empty:
                df_otros = _añadir_precio_unitario(df_otros)
                with st.expander(
                    f"Ver {len(df_otros)} menciones secundarias "
                    f"de '{busqueda}'"
                ):
                    cols_o = [c for c in cols if c in df_otros.columns]
                    df_pag_otros = paginar_dataframe(
                        df_otros.sort_values('precio'),
                        "pag_comp_otros", filas_por_pagina=20)
                    st.dataframe(
                        df_pag_otros[cols_o],
                        use_container_width=True, hide_index=True)

            # ── Guardar equivalencia ──────────────────────────────
            with st.expander("Guardar como equivalencia"):
                if not df_filtrado.empty:
                    opciones_eq = {
                        (f"{row['nombre']} ({row['supermercado']}) - "
                         f"{row['precio']:.2f} EUR"): row['id']
                        for _, row in df_filtrado.iterrows()
                    }
                    ids_sel = st.multiselect(
                        "Selecciona productos equivalentes:",
                        list(opciones_eq.keys()), key="comp_equiv")
                    nombre_equiv = st.text_input(
                        "Nombre:",
                        placeholder=f"Ej: {busqueda}",
                        key="comp_nombre_eq")
                    if st.button(
                        "Guardar equivalencia", key="comp_btn_eq"
                    ):
                        if nombre_equiv and len(ids_sel) >= 2:
                            db.crear_equivalencia(
                                nombre_equiv,
                                [opciones_eq[o] for o in ids_sel])
                            st.success(
                                f"Equivalencia «{nombre_equiv}» "
                                "guardada.")
                        else:
                            st.warning(
                                "Necesitas un nombre y al menos "
                                "2 productos.")
    else:
        estado_vacio(
            "balance",
            "Escribe un producto para comparar precios",
            "Compara precios unitarios (EUR/L, EUR/kg) "
            "entre supermercados."
        )


# ═══════════════════════════════════════════════════════════════════════
# TAB 2: EQUIVALENCIAS GUARDADAS
# ═══════════════════════════════════════════════════════════════════════
with tab2:
    grupos = db.listar_grupos_equivalencia()
    if not grupos:
        estado_vacio(
            "link_off",
            "No hay equivalencias guardadas",
            "Busca un producto en la pestana 'Comparar precios' y "
            "guarda una equivalencia."
        )
    else:
        grupo_sel = st.selectbox(
            "Equivalencia:", grupos, key="eq_grupo")
        if grupo_sel:
            df_eq = db.obtener_equivalencias(grupo_sel)
            if not df_eq.empty:
                st.dataframe(
                    df_eq, use_container_width=True,
                    hide_index=True)
                from dashboard.utils.charts import (
                    grafico_comparativa_supermercados,
                )
                df_hist_eq = db.obtener_historico_equivalencia(
                    grupo_sel)
                if not df_hist_eq.empty and len(df_hist_eq) > 1:
                    st.plotly_chart(
                        grafico_comparativa_supermercados(
                            df_hist_eq),
                        use_container_width=True)
            else:
                estado_vacio(
                    "error_outline",
                    "No se encontraron productos para "
                    "esta equivalencia",
                )
