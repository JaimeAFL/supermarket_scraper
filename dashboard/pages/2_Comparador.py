# -*- coding: utf-8 -*-
"""Página: Comparador de precios entre supermercados."""

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
from matching.normalizer import calcular_precio_unitario
from dashboard.utils.styles import inyectar_estilos
from dashboard.utils.components import (
    encabezado, fila_insights, estado_vacio,
    añadir_a_cesta_rapido,
    obtener_url_producto, boton_consultar_web,
)

st.set_page_config(page_title="Comparador", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Comparador de precios", "balance")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)


def _añadir_precio_unitario(df):
    """Añade columnas precio_unitario y unidad_precio al DataFrame."""
    precios_u = []
    unidades = []
    for _, row in df.iterrows():
        fmt = row.get('formato_normalizado', '') or ''
        precio = row.get('precio', 0) or 0
        # Usar precio_referencia de la BD si ya viene calculado; si no, calcularlo
        precio_ref_bd = row.get('precio_referencia') or None
        unidad_ref_bd = row.get('unidad_referencia') or ''
        if precio_ref_bd and unidad_ref_bd:
            pu, unidad = precio_ref_bd, unidad_ref_bd
        else:
            calc = calcular_precio_unitario(precio, fmt)
            pu = calc['precio_referencia']
            unidad = calc['unidad_referencia']
        precios_u.append(pu)
        unidades.append(unidad)
    df = df.copy()
    df['precio_unitario'] = precios_u
    df['unidad_precio'] = unidades
    return df


def _ids_favoritos_actuales():
    """Devuelve set de IDs (Python int) de productos ya en favoritos."""
    df_favs = db.obtener_favoritos()
    if not df_favs.empty and 'id' in df_favs.columns:
        return set(int(x) for x in df_favs['id'].tolist())
    return set()


def _widget_añadir_a_lista(producto_id, df_listas, key_suffix):
    """Renderiza selectbox + botón para añadir un producto a una lista."""
    if df_listas.empty:
        st.caption("Sin listas. Créalas en 'Mis listas'.")
        return
    opciones = {row['nombre']: int(row['id'])
                for _, row in df_listas.iterrows()}
    col_s, col_b = st.columns([3, 1])
    with col_s:
        lista_sel = st.selectbox(
            "Lista:", list(opciones.keys()),
            key=f"lista_sel_{key_suffix}",
            label_visibility="collapsed")
    with col_b:
        if st.button("Añadir a lista", key=f"lista_btn_{key_suffix}",
                      use_container_width=True):
            ok = db.añadir_producto_a_lista(opciones[lista_sel], producto_id)
            if ok:
                st.success(f"Añadido a '{lista_sel}'.")
            else:
                st.error("No se pudo añadir a la lista.")
st.markdown(
    "Busca un producto y compara precios **unitarios** (€/L, €/kg) "
    "entre supermercados.")

busqueda = st.text_input(
    "Buscar producto:",
    placeholder="Ej: leche entera, café, aceite oliva...",
    key="comp_busqueda")

if busqueda:
    with st.spinner("Buscando..."):
        df = db.buscar_para_comparar(busqueda, limite_por_super=25)

    if df.empty:
        estado_vacio(
            "search_off",
            f"No se encontraron productos con '{busqueda}'",
            "Prueba con otro término de búsqueda.")
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

                fila_insights([
                    {
                        "icono": "emoji_events", "tipo": "success",
                        "titulo": "Más barato",
                        "valor": f"{mejor['precio_unitario']:.2f} {unidad_comun}",
                        "detalle": mejor['supermercado'],
                    },
                    {
                        "icono": "arrow_upward", "tipo": "error",
                        "titulo": "Más caro",
                        "valor": f"{peor_pu:.2f} {unidad_comun}",
                        "detalle": peor['supermercado'],
                    },
                    {
                        "icono": "savings", "tipo": "primary",
                        "titulo": "Ahorro máximo",
                        "valor": f"{ahorro_max:.2f} {unidad_comun}",
                        "detalle": f"{n_supers} supermercados comparados",
                    },
                ])

                # Tabla resumen (con Mediana + nombre producto)
                # Obtener el más barato por super con su nombre
                df_mejor_por_super = (
                    df_misma_unidad.sort_values('precio_unitario')
                    .groupby('supermercado').first().reset_index())
                resumen_rows = []
                for _, r in df_mejor_por_super.iterrows():
                    df_super_u = df_misma_unidad[
                        df_misma_unidad['supermercado'] == r['supermercado']]
                    resumen_rows.append({
                        'Supermercado': r['supermercado'],
                        'Producto': r['nombre'],
                        f'Más barato ({unidad_comun})': df_super_u['precio_unitario'].min(),
                        f'Mediana ({unidad_comun})': df_super_u['precio_unitario'].median(),
                        f'Más caro ({unidad_comun})': df_super_u['precio_unitario'].max(),
                    })
                resumen = pd.DataFrame(resumen_rows)
                pu_min = resumen[f'Más barato ({unidad_comun})'].min()
                resumen['vs más barato'] = resumen[
                    f'Más barato ({unidad_comun})'
                ].apply(
                    lambda x: "Más barato" if x == pu_min
                    else f"+{((x - pu_min) / pu_min * 100):.0f}%")
                for col in [
                    f'Más barato ({unidad_comun})',
                    f'Mediana ({unidad_comun})',
                    f'Más caro ({unidad_comun})',
                ]:
                    resumen[col] = resumen[col].apply(
                        lambda x: f"{x:.2f} €")
                st.dataframe(resumen, use_container_width=True,
                             hide_index=True)

            else:
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
                        "titulo": "Más barato",
                        "valor": f"{mejor_abs['precio']:.2f} €",
                        "detalle": mejor_abs['supermercado'],
                    },
                    {
                        "icono": "arrow_upward", "tipo": "error",
                        "titulo": "Más caro",
                        "valor": f"{peor_abs['precio']:.2f} €",
                        "detalle": peor_abs['supermercado'],
                    },
                    {
                        "icono": "savings", "tipo": "primary",
                        "titulo": "Ahorro máximo",
                        "valor": f"{ahorro_abs:.2f} €",
                        "detalle": f"{df_principal['supermercado'].nunique()} supermercados",
                    },
                ])

                # Tabla resumen (con Mediana + nombre producto)
                df_mejor_abs_super = (
                    df_principal.sort_values('precio')
                    .groupby('supermercado').first().reset_index())
                resumen_rows_abs = []
                for _, r in df_mejor_abs_super.iterrows():
                    df_super_p = df_principal[
                        df_principal['supermercado'] == r['supermercado']]
                    resumen_rows_abs.append({
                        'Supermercado': r['supermercado'],
                        'Producto': r['nombre'],
                        'Más barato': df_super_p['precio'].min(),
                        'Mediana': df_super_p['precio'].median(),
                        'Más caro': df_super_p['precio'].max(),
                    })
                resumen = pd.DataFrame(resumen_rows_abs)
                precio_min_global = resumen['Más barato'].min()
                resumen['vs más barato'] = resumen['Más barato'].apply(
                    lambda x: "Más barato" if x == precio_min_global
                    else f"+{((x - precio_min_global) / precio_min_global * 100):.0f}%")
                for col in ['Más barato', 'Mediana', 'Más caro']:
                    resumen[col] = resumen[col].apply(
                        lambda x: f"{x:.2f} €")
                st.dataframe(resumen, use_container_width=True,
                             hide_index=True)

        # ── Todos los productos (filtros, sin paginación) ─────
        st.markdown("---")
        encabezado("Todos los productos encontrados",
                    "format_list_bulleted", nivel=3)

        col_f1, col_f2, col_f3 = st.columns(3)
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
                    st.slider("Rango de precios (€):", pmin, pmax,
                               (pmin, pmax), key="comp_rango")
                    if pmin < pmax else (pmin, pmax))
            else:
                rango = (0.0, 999.0)
        with col_f3:
            tiene_precio_unitario = (
                df_principal['precio_unitario'].notna().any()
                if not df_principal.empty else False)
            orden_comp = st.radio(
                "Ordenar por:",
                ["Precio de referencia (€/kg, €/L...)", "Precio de venta (€)"],
                key="comp_orden",
                horizontal=True,
                disabled=not tiene_precio_unitario,
                index=0 if tiene_precio_unitario else 1,
            )

        df_filtrado = df_principal[
            (df_principal['supermercado'].isin(supers_sel))
            & (df_principal['precio'] >= rango[0])
            & (df_principal['precio'] <= rango[1])]

        usar_precio_ref = (
            orden_comp == "Precio de referencia (€/kg, €/L...)"
            and df_filtrado['precio_unitario'].notna().any())
        if usar_precio_ref:
            df_filtrado = df_filtrado.sort_values(
                'precio_unitario', na_position='last')
        else:
            df_filtrado = df_filtrado.sort_values('precio')

        if df_filtrado.empty:
            estado_vacio(
                "filter_list_off",
                "Sin resultados con los filtros actuales",
                "Prueba ampliando el rango de precios o "
                "seleccionando más supermercados.")
        else:
            cols = ['nombre', 'supermercado', 'precio',
                    'formato_normalizado', 'precio_unitario',
                    'unidad_precio', 'precio_referencia', 'unidad_referencia',
                    'marca', 'categoria_normalizada']
            cols = [c for c in cols if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols],
                         use_container_width=True, hide_index=True)

        # ── Menciones secundarias ─────────────────────────────
        if not df_otros.empty:
            df_otros = _añadir_precio_unitario(df_otros)
            with st.expander(
                f"Ver {len(df_otros)} menciones secundarias "
                f"de '{busqueda}'"):
                cols_o = [c for c in cols if c in df_otros.columns]
                st.dataframe(df_otros[cols_o].sort_values('precio'),
                             use_container_width=True, hide_index=True)

        # ── Añadir a favoritos / cesta / lista ────────────────
        st.markdown("---")
        encabezado("Añadir a favoritos / cesta / lista", "bookmark_add", nivel=3)

        if not df_filtrado.empty:
            ids_fav = _ids_favoritos_actuales()
            df_listas_comp = db.obtener_listas()

            # Producto más barato
            if df_filtrado['precio_unitario'].notna().any():
                idx_mb = df_filtrado['precio_unitario'].idxmin()
            else:
                idx_mb = df_filtrado['precio'].idxmin()
            mas_barato = df_filtrado.loc[idx_mb]
            id_barato = int(mas_barato['id'])
            nombre_barato = (f"{mas_barato['nombre']} "
                             f"({mas_barato['supermercado']})")
            ya_en_favs = id_barato in ids_fav

            st.markdown(f"**El más barato:** {nombre_barato}")

            col_fav_r, col_cesta_r, col_web_r = st.columns(3)
            with col_fav_r:
                if ya_en_favs:
                    st.button("Ya está en favoritos",
                              disabled=True, key="comp_fav_rapido_dis",
                              use_container_width=True)
                else:
                    if st.button("Añadir el más barato a favoritos",
                                  key="comp_fav_rapido",
                                  use_container_width=True):
                        db.agregar_favorito(id_barato)
                        st.success(f"Añadido: {nombre_barato}")
                        st.rerun()
            with col_cesta_r:
                if st.button("Añadir el más barato a la cesta",
                              key="comp_cesta_rapido",
                              use_container_width=True):
                    añadir_a_cesta_rapido(
                        id_barato, mas_barato['nombre'],
                        mas_barato['supermercado'],
                        float(mas_barato['precio']),
                        mas_barato.get('formato_normalizado', ''))
                    st.success(f"Añadido a la cesta: {nombre_barato}")
            with col_web_r:
                url_barato = (mas_barato.get('url', '') or ''
                              if 'url' in mas_barato.index else
                              obtener_url_producto(db, id_barato))
                boton_consultar_web(url_barato, key_suffix="comp_rapido")

            _widget_añadir_a_lista(id_barato, df_listas_comp, "comp_rapido")

            # Selección manual
            st.markdown("")
            opciones_manual = {
                (f"{row['nombre']} ({row['supermercado']}) - "
                 f"{row['precio']:.2f} €"): int(row['id'])
                for _, row in df_filtrado.iterrows()
            }
            if opciones_manual:
                sel_manual = st.selectbox(
                    "O selecciona otro producto:",
                    list(opciones_manual.keys()),
                    key="comp_manual_sel")
                sel_id = opciones_manual[sel_manual]
                sel_row = (df_filtrado[df_filtrado['id'] == sel_id].iloc[0]
                           if not df_filtrado[df_filtrado['id'] == sel_id].empty
                           else None)

                col_fav_m, col_cesta_m, col_web_m = st.columns(3)
                with col_fav_m:
                    if sel_id in ids_fav:
                        st.button("Ya está en favoritos",
                                  disabled=True,
                                  key="comp_fav_manual_dis",
                                  use_container_width=True)
                    else:
                        if st.button("Añadir a favoritos",
                                      key="comp_fav_manual_btn",
                                      use_container_width=True):
                            db.agregar_favorito(sel_id)
                            st.success("Añadido a favoritos.")
                            st.rerun()
                with col_cesta_m:
                    if st.button("Añadir a la cesta",
                                  key="comp_cesta_manual_btn",
                                  use_container_width=True):
                        if sel_row is not None:
                            añadir_a_cesta_rapido(
                                sel_id, sel_row['nombre'],
                                sel_row['supermercado'],
                                float(sel_row['precio']),
                                sel_row.get('formato_normalizado', ''))
                        st.success("Añadido a la cesta.")
                with col_web_m:
                    url_manual = ""
                    if sel_row is not None and 'url' in sel_row.index:
                        url_manual = sel_row.get('url', '') or ''
                    if not url_manual:
                        url_manual = obtener_url_producto(db, sel_id)
                    boton_consultar_web(url_manual,
                                        key_suffix="comp_manual")

                _widget_añadir_a_lista(sel_id, df_listas_comp, "comp_manual")