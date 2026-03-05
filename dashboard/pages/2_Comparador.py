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
import streamlit.components.v1 as components
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from matching.normalizer import calcular_precio_unitario
from dashboard.utils.styles import inyectar_estilos
from dashboard.utils.components import (
    encabezado, fila_insights, estado_vacio,
)

st.set_page_config(page_title="Comparador", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Comparador de precios", "balance")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)


def _anadir_precio_unitario(df):
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


def _ids_favoritos_actuales():
    """Devuelve set de IDs de productos ya en favoritos."""
    df_favs = db.obtener_favoritos()
    if not df_favs.empty and 'id' in df_favs.columns:
        return set(df_favs['id'].tolist())
    return set()


# ═══════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["Comparar precios", "Equivalencias guardadas"])

with tab1:
    st.markdown(
        "Busca un producto y compara precios **unitarios** (€/L, €/kg) "
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
            df = _anadir_precio_unitario(df)

            if 'prioridad' in df.columns:
                df_tipo = df[df['prioridad'] == 1]
                df_otros = df[df['prioridad'] == 2]
            else:
                df_tipo = df
                df_otros = pd.DataFrame()

            df_principal = df_tipo if not df_tipo.empty else df
            supers_disp = sorted(
                df_principal['supermercado'].unique().tolist())

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
                    unidad_comun = moda.iloc[0] if not moda.empty else ""
                else:
                    unidad_comun = ""

                usa_unitario = (not df_con_pu.empty and unidad_comun)

                if usa_unitario:
                    df_misma_unidad = df_con_pu[
                        df_con_pu['unidad_precio'] == unidad_comun]
                else:
                    df_misma_unidad = pd.DataFrame()

                if usa_unitario and not df_misma_unidad.empty:
                    idx_mejor = df_misma_unidad['precio_unitario'].idxmin()
                    mejor = df_misma_unidad.loc[idx_mejor]
                    peor_pu = df_misma_unidad['precio_unitario'].max()
                    idx_peor = df_misma_unidad['precio_unitario'].idxmax()
                    peor = df_misma_unidad.loc[idx_peor]
                    ahorro_max = peor_pu - mejor['precio_unitario']
                    n_supers = df_misma_unidad['supermercado'].nunique()

                    # Insight cards: Mas barato + Mas caro + Ahorro
                    fila_insights([
                        {
                            "icono": "emoji_events", "tipo": "success",
                            "titulo": "Mas barato",
                            "valor": f"{mejor['precio_unitario']:.2f} {unidad_comun}",
                            "detalle": mejor['supermercado'],
                        },
                        {
                            "icono": "arrow_upward", "tipo": "error",
                            "titulo": "Mas caro",
                            "valor": f"{peor_pu:.2f} {unidad_comun}",
                            "detalle": peor['supermercado'],
                        },
                        {
                            "icono": "savings", "tipo": "primary",
                            "titulo": "Ahorro maximo",
                            "valor": f"{ahorro_max:.2f} {unidad_comun}",
                            "detalle": f"{n_supers} supermercados comparados",
                        },
                    ])

                    # Tabla resumen (con Mediana)
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
                    pu_min = resumen[f'Mas barato ({unidad_comun})'].min()
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
                            lambda x: f"{x:.2f} €")
                    st.dataframe(
                        resumen, use_container_width=True,
                        hide_index=True)

                else:
                    # Fallback: precio absoluto
                    st.caption(
                        "No hay datos de formato suficientes para "
                        "comparar por precio unitario. "
                        "Mostrando precio absoluto.")

                    idx_mejor_abs = df_principal['precio'].idxmin()
                    mejor_abs = df_principal.loc[idx_mejor_abs]
                    idx_peor_abs = df_principal['precio'].idxmax()
                    peor_abs = df_principal.loc[idx_peor_abs]
                    ahorro_abs = peor_abs['precio'] - mejor_abs['precio']

                    fila_insights([
                        {
                            "icono": "emoji_events", "tipo": "success",
                            "titulo": "Mas barato",
                            "valor": f"{mejor_abs['precio']:.2f} €",
                            "detalle": mejor_abs['supermercado'],
                        },
                        {
                            "icono": "arrow_upward", "tipo": "error",
                            "titulo": "Mas caro",
                            "valor": f"{peor_abs['precio']:.2f} €",
                            "detalle": peor_abs['supermercado'],
                        },
                        {
                            "icono": "savings", "tipo": "primary",
                            "titulo": "Ahorro maximo",
                            "valor": f"{ahorro_abs:.2f} €",
                            "detalle": f"{df_principal['supermercado'].nunique()} supermercados",
                        },
                    ])

                    # Tabla resumen (con Mediana)
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
                            lambda x: f"{x:.2f} €")
                    st.dataframe(
                        resumen, use_container_width=True,
                        hide_index=True)

            # ── Todos los productos (filtros, sin paginacion) ─────
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
                            "Rango de precios (€):", pmin, pmax,
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
                st.dataframe(
                    df_filtrado[cols],
                    use_container_width=True, hide_index=True)

            # ── Menciones secundarias ─────────────────────────────
            if not df_otros.empty:
                df_otros = _anadir_precio_unitario(df_otros)
                with st.expander(
                    f"Ver {len(df_otros)} menciones secundarias "
                    f"de '{busqueda}'"
                ):
                    cols_o = [c for c in cols if c in df_otros.columns]
                    st.dataframe(
                        df_otros[cols_o].sort_values('precio'),
                        use_container_width=True, hide_index=True)

            # ── Anadir a favoritos desde comparador ───────────────
            st.markdown("---")
            encabezado("Anadir a favoritos", "bookmark_add", nivel=3)

            if not df_filtrado.empty:
                ids_fav = _ids_favoritos_actuales()

                col_rapido, col_manual = st.columns(2)

                with col_rapido:
                    if df_filtrado['precio_unitario'].notna().any():
                        idx_mas_barato = df_filtrado['precio_unitario'].idxmin()
                    else:
                        idx_mas_barato = df_filtrado['precio'].idxmin()
                    mas_barato = df_filtrado.loc[idx_mas_barato]
                    nombre_barato = (
                        f"{mas_barato['nombre']} "
                        f"({mas_barato['supermercado']})")
                    ya_en_favs = mas_barato['id'] in ids_fav

                    st.markdown(f"**El mas barato:** {nombre_barato}")
                    if ya_en_favs:
                        st.caption("Ya esta en favoritos.")
                    else:
                        if st.button(
                            "Anadir el mas barato a favoritos",
                            key="comp_fav_rapido"
                        ):
                            db.agregar_favorito(mas_barato['id'])
                            st.success(f"Anadido: {nombre_barato}")
                            st.rerun()

                with col_manual:
                    opciones_fav = {
                        (f"{row['nombre']} ({row['supermercado']}) - "
                         f"{row['precio']:.2f} €"): row['id']
                        for _, row in df_filtrado.iterrows()
                        if row['id'] not in ids_fav
                    }
                    if opciones_fav:
                        fav_sel = st.selectbox(
                            "O selecciona otro producto:",
                            list(opciones_fav.keys()),
                            key="comp_fav_manual")
                        if st.button(
                            "Anadir seleccionado",
                            key="comp_fav_manual_btn"
                        ):
                            db.agregar_favorito(opciones_fav[fav_sel])
                            st.success("Anadido a favoritos.")
                            st.rerun()
                    else:
                        st.caption(
                            "Todos los productos filtrados ya "
                            "estan en favoritos.")

            # ── Guardar equivalencia ──────────────────────────────
            st.markdown("---")
            encabezado("Guardar equivalencia", "compare_arrows", nivel=3)
            st.caption(
                "Selecciona al menos 2 productos del mismo tipo "
                "de distintos supermercados para crear una "
                "equivalencia y seguir su precio.")

            if not df_filtrado.empty:
                opciones_eq = {
                    (f"{row['nombre']} ({row['supermercado']}) - "
                     f"{row['precio']:.2f} €"): row['id']
                    for _, row in df_filtrado.iterrows()
                }

                if st.button(
                    "Preseleccionar el mas barato de cada super",
                    key="comp_eq_presel"
                ):
                    if df_filtrado['precio_unitario'].notna().any():
                        presel = (
                            df_filtrado.sort_values('precio_unitario')
                            .groupby('supermercado').first().reset_index())
                    else:
                        presel = (
                            df_filtrado.sort_values('precio')
                            .groupby('supermercado').first().reset_index())
                    labels_presel = []
                    for _, r in presel.iterrows():
                        lbl = (f"{r['nombre']} ({r['supermercado']}) "
                               f"- {r['precio']:.2f} €")
                        if lbl in opciones_eq:
                            labels_presel.append(lbl)
                    st.session_state['comp_equiv'] = labels_presel

                ids_sel = st.multiselect(
                    "Selecciona productos equivalentes:",
                    list(opciones_eq.keys()), key="comp_equiv")
                nombre_equiv = st.text_input(
                    "Nombre de la equivalencia:",
                    placeholder=f"Ej: {busqueda}",
                    key="comp_nombre_eq")

                if st.button(
                    "Guardar equivalencia", key="comp_btn_eq",
                    type="primary"
                ):
                    if not nombre_equiv:
                        st.warning("Escribe un nombre para la equivalencia.")
                    elif len(ids_sel) < 2:
                        st.warning("Selecciona al menos 2 productos.")
                    else:
                        db.crear_equivalencia(
                            nombre_equiv,
                            [opciones_eq[o] for o in ids_sel])
                        st.success(
                            f"Equivalencia «{nombre_equiv}» guardada "
                            f"con {len(ids_sel)} productos.")
    else:
        estado_vacio(
            "balance",
            "Escribe un producto para comparar precios",
            "Compara precios unitarios (€/L, €/kg) entre supermercados."
        )

# ═══════════════════════════════════════════════════════════════════════
# TAB 2: EQUIVALENCIAS GUARDADAS (ApexCharts)
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
        grupo_sel = st.selectbox("Equivalencia:", grupos, key="eq_grupo")
        if grupo_sel:
            df_eq = db.obtener_equivalencias(grupo_sel)
            if not df_eq.empty:
                st.dataframe(
                    df_eq, use_container_width=True,
                    hide_index=True)
                from dashboard.utils.charts import (
                    apex_comparativa_supermercados_html,
                )
                df_hist_eq = db.obtener_historico_equivalencia(grupo_sel)
                if not df_hist_eq.empty and len(df_hist_eq) > 1:
                    components.html(
                        apex_comparativa_supermercados_html(df_hist_eq),
                        height=460, scrolling=False,
                    )
            else:
                estado_vacio(
                    "error_outline",
                    "No se encontraron productos para esta equivalencia",
                )
