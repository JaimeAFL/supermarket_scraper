# -*- coding: utf-8 -*-
"""Pagina: Historico de precios."""

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
    barra_filtros,
)

st.set_page_config(page_title="Historico de precios", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Historico de precios", "trending_up")
st.markdown("Selecciona un producto para ver como ha evolucionado su precio.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

stats = db.obtener_estadisticas()
dias = stats.get('dias_con_datos', 0)
if dias <= 1:
    st.info("Solo hay datos de **1 dia**. El grafico aparecera cuando "
            "el scraper se ejecute en distintos dias.")

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
            limite=50
        )

    if not df_res.empty:
        def _label(row):
            cat = row.get('categoria_normalizada', '')
            cat_tag = f" [{cat}]" if cat else ""
            return f"{row['nombre']} ({row['supermercado']}){cat_tag}"

        opciones = {_label(row): row['id'] for _, row in df_res.iterrows()}
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

            # ── Insight cards ─────────────────────────────────────
            insights = []

            if len(df_hist) > 1:
                variacion = precio_actual - df_hist.iloc[-2]['precio']
                if variacion > 0:
                    icono_var = "trending_up"
                    tipo_var = "error"
                    detalle_var = f"+{variacion:.2f} € vs anterior"
                elif variacion < 0:
                    icono_var = "trending_down"
                    tipo_var = "success"
                    detalle_var = f"{variacion:.2f} € vs anterior"
                else:
                    icono_var = "trending_flat"
                    tipo_var = "neutral"
                    detalle_var = "Sin cambio vs anterior"
            else:
                icono_var = "sell"
                tipo_var = "primary"
                detalle_var = "Unico registro"

            insights.append({
                "icono": icono_var, "tipo": tipo_var,
                "titulo": "Precio actual",
                "valor": f"{precio_actual:.2f} €",
                "detalle": detalle_var
            })
            insights.append({
                "icono": "arrow_downward", "tipo": "success",
                "titulo": "Minimo historico",
                "valor": f"{precio_min:.2f} €",
            })
            insights.append({
                "icono": "arrow_upward", "tipo": "error",
                "titulo": "Maximo historico",
                "valor": f"{precio_max:.2f} €",
            })
            insights.append({
                "icono": "receipt_long", "tipo": "neutral",
                "titulo": "Registros",
                "valor": str(len(df_hist)),
            })

            fila_insights(insights)

            # ── Grafico ApexCharts ────────────────────────────────
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
                st.info("Solo hay 1 punto de datos. El grafico aparecera "
                        "cuando haya capturas de mas de un dia.")

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
                        columns={
                            'fecha_captura': 'Fecha',
                            'precio': 'Precio'
                        }),
                    use_container_width=True, hide_index=True)
        else:
            estado_vacio(
                "timeline", "Este producto no tiene registros de precio",
                "Los precios se registran cada vez que se ejecuta el scraper."
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
        "Escribe el nombre de un producto para empezar",
        "Puedes filtrar por supermercado para acotar la busqueda."
    )
