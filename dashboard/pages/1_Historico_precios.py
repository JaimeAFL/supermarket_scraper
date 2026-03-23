# -*- coding: utf-8 -*-
"""Página: Histórico de precios."""

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
from datetime import datetime
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.charts import apex_historico_precio_html
from dashboard.utils.styles import inyectar_estilos
from dashboard.utils.components import (
    encabezado, fila_insights, estado_vacio,
    barra_filtros, añadir_a_cesta_rapido,
    obtener_url_producto, boton_consultar_web,
    widget_añadir_a_lista,
)

st.set_page_config(page_title="Histórico de precios", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Histórico de precios", "trending_up")
st.markdown("Selecciona un producto para ver cómo ha evolucionado su precio.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

stats = db.obtener_estadisticas()
dias = stats.get('dias_con_datos', 0)
if dias <= 1:
    st.info("Solo hay datos de **1 día**. El gráfico aparecerá cuando "
            "el scraper se ejecute en distintos días.")

# ── Filtros ───────────────────────────────────────────────────────────
filtros = barra_filtros(
    db, clave_vista="hist",
    mostrar_busqueda=True, mostrar_super=True,
    mostrar_categoria=False, mostrar_precio=False, mostrar_orden=False
)

if filtros['busqueda']:
    with st.spinner("Buscando..."):
        df_res = db.buscar_productos(
            nombre=filtros['busqueda'],
            supermercado=filtros['supermercado'],
            limite=100
        )

    if not df_res.empty:
        def _label(row):
            cat = row.get('categoria_normalizada', '')
            cat_tag = f" [{cat}]" if cat else ""
            return f"{row['nombre']} ({row['supermercado']}){cat_tag}"

        opciones = {_label(row): int(row['id']) for _, row in df_res.iterrows()}
        seleccion = st.selectbox(
            f"Productos encontrados ({len(df_res)}):",
            list(opciones.keys()))
        producto_id = opciones[seleccion]

        st.markdown("---")
        df_hist = db.obtener_historico_precios(producto_id)

        if not df_hist.empty:
            nombre_prod = seleccion.split(" (")[0]
            precio_actual = df_hist.iloc[-1]['precio']
            precio_min = df_hist['precio'].min()
            precio_max = df_hist['precio'].max()

            # ── Botones: Favoritos / Cesta / Consultar web / Lista ─────
            # 4 columnas: las 3 acciones clásicas + botón popover de lista
            col_fav, col_cesta, col_web, col_lista = st.columns(4)

            # Comprobar si ya está en favoritos
            df_favs = db.obtener_favoritos()
            ids_fav = set(int(x) for x in df_favs['id'].tolist()) if not df_favs.empty else set()

            with col_fav:
                if producto_id in ids_fav:
                    st.button("Ya está en favoritos",
                              disabled=True, key="hist_fav_disabled",
                              use_container_width=True)
                else:
                    if st.button("Añadir a favoritos",
                                  key="hist_fav_btn",
                                  use_container_width=True):
                        db.agregar_favorito(producto_id)
                        st.success(f"Añadido a favoritos: {nombre_prod}")
                        st.rerun()

            with col_cesta:
                if st.button("Añadir a la cesta",
                              key="hist_cesta_btn",
                              use_container_width=True):
                    añadir_a_cesta_rapido(
                        producto_id, nombre_prod,
                        seleccion.split("(")[-1].replace(")", "").split("]")[0].replace("[", "").strip()
                        if "(" in seleccion else "",
                        float(precio_actual))
                    st.success(f"Añadido a la cesta: {nombre_prod}")

            with col_web:
                url_prod = obtener_url_producto(db, producto_id)
                boton_consultar_web(url_prod, key_suffix="hist")

            with col_lista:
                # Popover con selector de lista y cantidad
                widget_añadir_a_lista(db, producto_id,
                                      f"hist_{producto_id}")

            # ── Insight cards ─────────────────────────────────────
            insights = []

            if len(df_hist) > 1:
                variacion = precio_actual - df_hist.iloc[-2]['precio']
                if variacion > 0:
                    icono_var, tipo_var = "trending_up", "error"
                    detalle_var = f"+{variacion:.2f} € vs anterior"
                elif variacion < 0:
                    icono_var, tipo_var = "trending_down", "success"
                    detalle_var = f"{variacion:.2f} € vs anterior"
                else:
                    icono_var, tipo_var = "trending_flat", "neutral"
                    detalle_var = "Sin cambio vs anterior"
            else:
                icono_var, tipo_var = "sell", "primary"
                detalle_var = "Único registro"

            insights.append({
                "icono": icono_var, "tipo": tipo_var,
                "titulo": "Precio actual",
                "valor": f"{precio_actual:.2f} €",
                "detalle": detalle_var
            })
            insights.append({
                "icono": "arrow_downward", "tipo": "success",
                "titulo": "Mínimo histórico",
                "valor": f"{precio_min:.2f} €",
            })
            insights.append({
                "icono": "arrow_upward", "tipo": "error",
                "titulo": "Máximo histórico",
                "valor": f"{precio_max:.2f} €",
            })
            insights.append({
                "icono": "receipt_long", "tipo": "neutral",
                "titulo": "Registros",
                "valor": str(len(df_hist)),
            })

            fila_insights(insights)

            # ── Gráfico ApexCharts ────────────────────────────────
            if len(df_hist) > 1:
                components.html(
                    apex_historico_precio_html(df_hist, nombre_prod),
                    height=440, scrolling=False,
                )
            else:
                st.markdown(f"**Precio registrado:** {precio_actual:.2f} €")
                try:
                    fecha = datetime.fromisoformat(
                        df_hist.iloc[0]['fecha_captura'])
                    st.caption(
                        f"Capturado el "
                        f"{fecha.strftime('%d/%m/%Y a las %H:%M')}")
                except Exception:
                    pass
                st.info("Solo hay 1 punto de datos. El gráfico aparecerá "
                        "cuando haya capturas de más de un día.")

            # ── Tabla de datos ────────────────────────────────────
            with st.expander("Ver datos en tabla"):
                df_m = df_hist.copy()
                df_m['precio'] = df_m['precio'].apply(
                    lambda x: f"{x:.2f} €")
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
            estado_vacio(
                "timeline", "Este producto no tiene registros de precio",
                "Los precios se registran cada vez que se ejecuta el scraper.")
    else:
        estado_vacio(
            "search_off",
            f"No se encontraron productos con '{filtros['busqueda']}'",
            "Prueba con otro término de búsqueda.")
else:
    estado_vacio(
        "search",
        "Escribe el nombre de un producto para empezar",
        "Puedes filtrar por supermercado para acotar la búsqueda.")
