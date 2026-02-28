# -*- coding: utf-8 -*-
"""Página: Comparador de precios entre supermercados."""

import sys, os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_DB_PATH = os.environ.get("SUPERMARKET_DB_PATH",
                          os.path.join(_PROJECT_ROOT, "database", "supermercados.db"))

import streamlit as st
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import grafico_comparador_precios
from matching.normalizer import calcular_precio_unitario

st.set_page_config(page_title="Comparador", page_icon="⚖️", layout="wide")
st.title("⚖️ Comparador de precios")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)


def _añadir_precio_unitario(df):
    """Añade columnas precio_unitario y unidad_precio al DataFrame."""
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


tab1, tab2 = st.tabs(["🔍 Comparar precios", "📌 Equivalencias guardadas"])

with tab1:
    st.markdown("Busca un producto y compara precios **unitarios** (€/L, €/kg) "
                "entre supermercados.")
    st.caption("La búsqueda prioriza el **tipo** de producto: 'leche' muestra "
               "solo lácteos, no 'café con leche'.")

    busqueda = st.text_input("Buscar producto:",
                             placeholder="Ej: leche entera, café, aceite oliva...",
                             key="comp_busqueda")

    if busqueda:
        df = db.buscar_para_comparar(busqueda, limite_por_super=25)

        if df.empty:
            st.warning(f"No se encontraron productos con '{busqueda}'.")
        else:
            # Calcular precio unitario
            df = _añadir_precio_unitario(df)

            if 'prioridad' in df.columns:
                df_tipo = df[df['prioridad'] == 1]
                df_otros = df[df['prioridad'] == 2]
            else:
                df_tipo = df
                df_otros = pd.DataFrame()

            df_principal = df_tipo if not df_tipo.empty else df
            supers_disp = sorted(df_principal['supermercado'].unique().tolist())

            st.subheader(f"Resultados para «{busqueda}»")
            st.caption(f"{len(df_tipo)} resultados directos"
                       + (f", {len(df_otros)} menciones secundarias"
                          if not df_otros.empty else ""))

            # ── Resumen con precio unitario ──
            if not df_principal.empty:
                df_con_pu = df_principal[df_principal['precio_unitario'].notna()]
                if not df_con_pu.empty:
                    unidad_comun = df_con_pu['unidad_precio'].mode().iloc[0] if not df_con_pu['unidad_precio'].mode().empty else ""
                else:
                    unidad_comun = ""

                if not df_con_pu.empty and unidad_comun:
                    # Resumen por precio unitario
                    df_misma_unidad = df_con_pu[df_con_pu['unidad_precio'] == unidad_comun]
                    if not df_misma_unidad.empty:
                        resumen = df_misma_unidad.groupby('supermercado')['precio_unitario'].agg(
                            ['count', 'min', 'median', 'max']).reset_index()
                        resumen.columns = ['Supermercado', 'Productos',
                                           f'Más barato ({unidad_comun})',
                                           f'Mediana ({unidad_comun})',
                                           f'Más caro ({unidad_comun})']
                        pu_min = resumen[f'Más barato ({unidad_comun})'].min()
                        resumen['vs más barato'] = resumen[f'Más barato ({unidad_comun})'].apply(
                            lambda x: "⭐ Más barato" if x == pu_min
                            else f"+{((x - pu_min) / pu_min * 100):.0f}%")
                        for col in [f'Más barato ({unidad_comun})', f'Mediana ({unidad_comun})',
                                    f'Más caro ({unidad_comun})']:
                            resumen[col] = resumen[col].apply(lambda x: f"{x:.2f} €")
                        st.dataframe(resumen, use_container_width=True, hide_index=True)

                    # Gráfico: precio unitario más bajo por supermercado
                    df_baratos = (df_misma_unidad.sort_values('precio_unitario')
                                  .groupby('supermercado').first().reset_index())
                    st.plotly_chart(
                        grafico_comparador_precios(
                            df_baratos,
                            f"Precio unitario más bajo de «{busqueda}» ({unidad_comun})",
                            usar_precio_unitario=True),
                        use_container_width=True)
                else:
                    # Sin precio unitario → fallback a precio absoluto
                    st.caption("⚠️ No hay datos de formato suficientes para "
                               "comparar por precio unitario. Mostrando precio absoluto.")
                    resumen = df_principal.groupby('supermercado')['precio'].agg(
                        ['count', 'min', 'median', 'max']).reset_index()
                    resumen.columns = ['Supermercado', 'Productos', 'Más barato',
                                       'Mediana', 'Más caro']
                    precio_min_global = resumen['Más barato'].min()
                    resumen['vs más barato'] = resumen['Más barato'].apply(
                        lambda x: "⭐ Más barato" if x == precio_min_global
                        else f"+{((x - precio_min_global) / precio_min_global * 100):.0f}%")
                    for col in ['Más barato', 'Mediana', 'Más caro']:
                        resumen[col] = resumen[col].apply(lambda x: f"{x:.2f} €")
                    st.dataframe(resumen, use_container_width=True, hide_index=True)

                    df_baratos = (df_principal.sort_values('precio')
                                  .groupby('supermercado').first().reset_index())
                    st.plotly_chart(
                        grafico_comparador_precios(
                            df_baratos,
                            f"Precio más bajo de «{busqueda}» por supermercado"),
                        use_container_width=True)

            st.markdown("---")
            st.subheader("Todos los productos encontrados")

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                supers_sel = st.multiselect("Filtrar supermercados:",
                                            supers_disp, default=supers_disp,
                                            key="comp_supers")
            with col_f2:
                if not df_principal.empty:
                    pmin = float(df_principal['precio'].min())
                    pmax = float(df_principal['precio'].max())
                    rango = (st.slider("Rango de precios (€):", pmin, pmax,
                                       (pmin, pmax), key="comp_rango")
                             if pmin < pmax else (pmin, pmax))
                else:
                    rango = (0.0, 999.0)

            df_filtrado = df_principal[
                (df_principal['supermercado'].isin(supers_sel)) &
                (df_principal['precio'] >= rango[0]) &
                (df_principal['precio'] <= rango[1])
            ]

            # Ordenar por precio unitario si disponible, sino por precio
            if df_filtrado['precio_unitario'].notna().any():
                df_filtrado = df_filtrado.sort_values(
                    'precio_unitario', na_position='last')
            else:
                df_filtrado = df_filtrado.sort_values('precio')

            # Tabla con precio unitario
            cols = ['nombre', 'supermercado', 'precio',
                    'formato_normalizado', 'precio_unitario', 'unidad_precio',
                    'marca', 'categoria_normalizada']
            cols = [c for c in cols if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols],
                         use_container_width=True, hide_index=True)

            if not df_otros.empty:
                df_otros = _añadir_precio_unitario(df_otros)
                with st.expander(f"Ver {len(df_otros)} menciones secundarias de '{busqueda}'"):
                    cols_o = [c for c in cols if c in df_otros.columns]
                    st.dataframe(df_otros[cols_o].sort_values('precio'),
                                 use_container_width=True, hide_index=True)

            with st.expander("💾 Guardar como equivalencia"):
                opciones_eq = {
                    f"{row['nombre']} ({row['supermercado']}) - {row['precio']:.2f}€": row['id']
                    for _, row in df_filtrado.iterrows()}
                ids_sel = st.multiselect("Selecciona productos equivalentes:",
                                         list(opciones_eq.keys()), key="comp_equiv")
                nombre_equiv = st.text_input("Nombre:", placeholder=f"Ej: {busqueda}",
                                             key="comp_nombre_eq")
                if st.button("Guardar equivalencia", key="comp_btn_eq"):
                    if nombre_equiv and len(ids_sel) >= 2:
                        db.crear_equivalencia(nombre_equiv,
                                              [opciones_eq[o] for o in ids_sel])
                        st.success(f"Equivalencia «{nombre_equiv}» guardada.")
                    else:
                        st.warning("Necesitas un nombre y al menos 2 productos.")
    else:
        st.info("Escribe un producto para comparar precios entre supermercados.")

with tab2:
    grupos = db.listar_grupos_equivalencia()
    if not grupos:
        st.info("No hay equivalencias guardadas.")
    else:
        grupo_sel = st.selectbox("Equivalencia:", grupos, key="eq_grupo")
        if grupo_sel:
            df_eq = db.obtener_equivalencias(grupo_sel)
            if not df_eq.empty:
                st.dataframe(df_eq, use_container_width=True, hide_index=True)
                from dashboard.utils.charts import grafico_comparativa_supermercados
                df_hist_eq = db.obtener_historico_equivalencia(grupo_sel)
                if not df_hist_eq.empty and len(df_hist_eq) > 1:
                    st.plotly_chart(grafico_comparativa_supermercados(df_hist_eq),
                                   use_container_width=True)
            else:
                st.warning("No se encontraron productos para esta equivalencia.")
