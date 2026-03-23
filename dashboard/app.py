# -*- coding: utf-8 -*-
"""Dashboard principal de Supermarket Price Tracker."""

import sys, os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import (
    apex_productos_por_supermercado_html,
    apex_distribucion_precios_html,
)
from dashboard.utils.styles import inyectar_estilos
from dashboard.utils.components import (
    encabezado, fila_metricas, sidebar_branding,
    barra_filtros, estado_vacio,
    widget_añadir_a_lista,
)

st.set_page_config(page_title="Supermarket Price Tracker", page_icon="",
                   layout="wide", initial_sidebar_state="expanded")

inyectar_estilos()

@st.cache_resource
def _init_db():
    inicializar_base_datos()
    return DatabaseManager()

db = _init_db()

st.title("Supermarket Price Tracker")
st.markdown("Comparador de precios de supermercados espanoles con historico semanal.")

# ── Metricas en cards ─────────────────────────────────────────────────
stats = db.obtener_estadisticas()
cats = stats.get('productos_por_categoria', {})
dias = stats.get('dias_con_datos', 0)

fila_metricas([
    ("inventory_2",    f"{stats.get('total_productos', 0):,}",          "Productos"),
    ("sell",           f"{stats.get('total_registros_precios', 0):,}",  "Registros precio"),
    ("storefront",     str(stats.get('total_supermercados', 0)),        "Supermercados"),
    ("category",       str(len(cats)),                                   "Categorias"),
    ("calendar_month", str(dias),                                        "Dias de datos"),
])

if dias <= 1:
    st.info("Datos de un solo dia. El historico se construye ejecutando "
            "el scraper semanalmente.")

# ── Busqueda rapida (sin paginacion) ─────────────────────────────────
st.markdown("---")
encabezado("Busqueda rapida de productos", "search", nivel=3)

filtros = barra_filtros(
    db, clave_vista="home",
    mostrar_busqueda=True, mostrar_super=True, mostrar_categoria=True,
    mostrar_precio=False, mostrar_orden=False
)

if filtros['busqueda']:
    with st.spinner("Buscando..."):
        df_res = db.buscar_productos(
            nombre=filtros['busqueda'],
            supermercado=filtros['supermercado'],
            limite=100
        )

    if not df_res.empty:
        if filtros['categoria'] and 'categoria_normalizada' in df_res.columns:
            df_res = df_res[df_res['categoria_normalizada'] == filtros['categoria']]

        if not df_res.empty:
            if 'prioridad' in df_res.columns:
                df_tipo = df_res[df_res['prioridad'] == 1]
                df_nombre = df_res[df_res['prioridad'] == 2]
            else:
                df_tipo = df_res
                df_nombre = pd.DataFrame()

            cols_mostrar = ['nombre', 'supermercado', 'precio', 'marca',
                            'categoria_normalizada', 'formato_normalizado']
            cols_mostrar = [c for c in cols_mostrar if c in df_res.columns]

            if not df_tipo.empty:
                st.caption(f"{len(df_tipo)} resultados directos")
                st.dataframe(df_tipo[cols_mostrar],
                             use_container_width=True, hide_index=True)

                # Añadir a lista: selecciona producto y luego usa el popover
                opciones_prod_home = {
                    f"{row['nombre']} ({row['supermercado']}) — "
                    f"{row.get('precio', '?')} €": int(row['id'])
                    for _, row in df_tipo.iterrows()
                }
                col_prod_h, col_btn_h = st.columns([4, 1])
                with col_prod_h:
                    prod_home_sel = st.selectbox(
                        "Producto:",
                        list(opciones_prod_home.keys()),
                        key="home_lista_prod_sel",
                        label_visibility="collapsed")
                with col_btn_h:
                    prod_home_id = opciones_prod_home[prod_home_sel]
                    # Botón popover con selector de lista y cantidad
                    widget_añadir_a_lista(
                        db, prod_home_id,
                        f"home_{prod_home_id}")

            if not df_nombre.empty:
                with st.expander(
                    f"Otros {len(df_nombre)} productos que mencionan "
                    f"'{filtros['busqueda']}'"
                ):
                    st.dataframe(df_nombre[cols_mostrar],
                                 use_container_width=True, hide_index=True)
        else:
            estado_vacio(
                "filter_list_off",
                f"Sin resultados para '{filtros['busqueda']}' en "
                f"categoria '{filtros['categoria']}'",
                "Prueba cambiando el filtro de categoria a 'Todas'."
            )
    else:
        estado_vacio(
            "search_off",
            f"No se encontraron productos con '{filtros['busqueda']}'",
            "Prueba con otro termino de busqueda."
        )
else:
    estado_vacio(
        "search",
        "Escribe un termino para buscar productos",
        "Puedes filtrar por supermercado y categoria."
    )

st.markdown("---")

components.html(
    apex_productos_por_supermercado_html(stats),
    height=360, scrolling=False,
)

# ── Distribucion de precios (ApexCharts) ──────────────────────────────
st.markdown("---")
encabezado("Distribucion de precios", "bar_chart", nivel=3)

supers_disponibles = list(stats.get('productos_por_supermercado', {}).keys())
if supers_disponibles:
    super_sel = st.selectbox("Supermercado:", supers_disponibles, key="dist_super")

    @st.cache_data(ttl=300)
    def _cargar_productos_super(_db, supermercado):
        return _db.obtener_productos_con_precio_actual(supermercado=supermercado)

    with st.spinner("Cargando datos..."):
        df_super = _cargar_productos_super(db, super_sel)

    components.html(
        apex_distribucion_precios_html(df_super, super_sel, completa=False),
        height=560, scrolling=False,
    )
    with st.expander("Ver distribucion completa (incluye precios extremos)"):
        components.html(
            apex_distribucion_precios_html(df_super, super_sel, completa=True),
            height=560, scrolling=False,
        )

# ── Resumen por supermercado (con Mediana, € en vez de EUR) ──────────
st.markdown("---")
encabezado("Resumen por supermercado", "table_chart", nivel=3)

if stats.get('productos_por_supermercado'):
    datos_tabla = []
    for supermercado, total in stats['productos_por_supermercado'].items():
        df_s = db.obtener_productos_con_precio_actual(supermercado=supermercado)
        if not df_s.empty:
            datos_tabla.append({
                'Supermercado': supermercado,
                'Productos': total,
                'Precio medio': f"{df_s['precio'].mean():.2f} €",
                'Mediana': f"{df_s['precio'].median():.2f} €",
                'Minimo': f"{df_s['precio'].min():.2f} €",
                'Maximo': f"{df_s['precio'].max():.2f} €",
            })
    if datos_tabla:
        st.dataframe(pd.DataFrame(datos_tabla),
                     use_container_width=True, hide_index=True)


# ── Footer ────────────────────────────────────────────────────────────
st.markdown("---")
if stats.get('ultima_captura'):
    from datetime import datetime
    try:
        primera = datetime.fromisoformat(
            stats['primera_captura']).strftime('%d/%m/%Y %H:%M')
        ultima = datetime.fromisoformat(
            stats['ultima_captura']).strftime('%d/%m/%Y %H:%M')
        st.caption(f"Primera captura: {primera} · Ultima: {ultima}")
    except Exception:
        st.caption(f"Ultima captura: {stats['ultima_captura']}")
