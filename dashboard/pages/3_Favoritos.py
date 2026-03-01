# -*- coding: utf-8 -*-
"""Pagina: Favoritos orientado a decision."""

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
from dashboard.utils.styles import inyectar_estilos, COLORES_SUPERMERCADO
from dashboard.utils.components import (
    encabezado, fila_insights, fila_metricas,
    estado_vacio, barra_filtros,
    badge_html, tarjeta_producto_html,
)

st.set_page_config(page_title="Favoritos", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Mis Favoritos", "bookmark")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════

def _construir_opciones_favoritos(df_favs):
    """Construye diccionario label->id para selectboxes de favoritos."""
    if df_favs.empty:
        return {}
    return {
        f"{row['nombre']} ({row['supermercado']})": row['id']
        for _, row in df_favs.iterrows()
    }


def _enriquecer_favoritos(db, df_favs):
    """Anade indicadores de decision a cada favorito."""
    datos_enriquecidos = []
    for _, row in df_favs.iterrows():
        prod_id = row.get('id') or row.get('producto_id')
        if not prod_id:
            continue

        info = {
            'id': prod_id,
            'nombre': row.get('nombre', ''),
            'supermercado': row.get('supermercado', ''),
            'precio': row.get('precio', 0),
            'marca': row.get('marca', ''),
            'categoria_normalizada': row.get('categoria_normalizada', ''),
            'formato_normalizado': row.get('formato_normalizado', ''),
            'fecha_agregado': row.get('fecha_agregado', ''),
        }

        df_hist = db.obtener_historico_precios(prod_id)
        if not df_hist.empty:
            precio_actual = df_hist.iloc[-1]['precio']
            precio_min = df_hist['precio'].min()
            precio_max = df_hist['precio'].max()

            info['precio_actual'] = precio_actual
            info['precio_min'] = precio_min
            info['precio_max'] = precio_max
            info['en_minimo'] = abs(precio_actual - precio_min) < 0.005

            if len(df_hist) > 1:
                precio_anterior = df_hist.iloc[-2]['precio']
                variacion = precio_actual - precio_anterior
                info['variacion'] = variacion
                if info['en_minimo']:
                    info['estado'] = 'minimo'
                elif variacion < -0.005:
                    info['estado'] = 'bajo'
                elif variacion > 0.005:
                    info['estado'] = 'subio'
                else:
                    info['estado'] = 'estable'
            else:
                info['variacion'] = 0
                info['estado'] = 'estable'
        else:
            info['precio_actual'] = info['precio']
            info['precio_min'] = info['precio']
            info['precio_max'] = info['precio']
            info['variacion'] = 0
            info['en_minimo'] = True
            info['estado'] = 'estable'

        datos_enriquecidos.append(info)

    return pd.DataFrame(datos_enriquecidos) if datos_enriquecidos else pd.DataFrame()


def _icono_estado(estado):
    mapa = {
        'minimo':  ('arrow_downward', 'success'),
        'bajo':    ('trending_down', 'success'),
        'subio':   ('trending_up', 'error'),
        'estable': ('trending_flat', 'neutral'),
    }
    return mapa.get(estado, ('help_outline', 'neutral'))


def _texto_estado(estado):
    mapa = {
        'minimo':  'Minimo historico',
        'bajo':    'Bajo de precio',
        'subio':   'Subio de precio',
        'estable': 'Precio estable',
    }
    return mapa.get(estado, 'Sin datos')


# ── Cargar favoritos actuales (se usa en varios bloques) ──────────────
df_favs = db.obtener_favoritos()
ids_fav_actuales = set(df_favs['id'].tolist()) if not df_favs.empty else set()


# ═══════════════════════════════════════════════════════════════════════
# 1) ANADIR PRODUCTO A FAVORITOS  (arriba del todo)
# ═══════════════════════════════════════════════════════════════════════
encabezado("Anadir producto a favoritos", "add_circle_outline", nivel=3)

filtros_add = barra_filtros(
    db, clave_vista="fav_add",
    mostrar_busqueda=True, mostrar_super=True,
    mostrar_categoria=False, mostrar_precio=False, mostrar_orden=False
)

if filtros_add['busqueda']:
    with st.spinner("Buscando..."):
        df_res = db.buscar_productos(
            nombre=filtros_add['busqueda'],
            supermercado=filtros_add['supermercado'],
            limite=30)

    if not df_res.empty:
        df_res = df_res[~df_res['id'].isin(ids_fav_actuales)]

        if df_res.empty:
            st.info("Todos los resultados ya estan en favoritos.")
        else:
            opciones_add = {
                (f"{row['nombre']} ({row['supermercado']}) - "
                 f"{row.get('precio', '?')} EUR"): row['id']
                for _, row in df_res.iterrows()
            }
            fav_agregar = st.selectbox(
                f"Productos encontrados ({len(df_res)}):",
                list(opciones_add.keys()), key="fav_agregar")

            if st.button("Anadir a favoritos", key="fav_btn_add"):
                db.agregar_favorito(opciones_add[fav_agregar])
                st.success("Anadido a favoritos.")
                st.rerun()
    else:
        estado_vacio(
            "search_off",
            f"No se encontraron productos con '{filtros_add['busqueda']}'",
            "Prueba con otro termino."
        )


# ═══════════════════════════════════════════════════════════════════════
# 2) ELIMINAR FAVORITO  (justo debajo de anadir)
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
encabezado("Eliminar un favorito", "remove_circle_outline", nivel=3)

if not df_favs.empty:
    opciones_elim = _construir_opciones_favoritos(df_favs)
    fav_eliminar = st.selectbox(
        "Selecciona el favorito a eliminar:",
        list(opciones_elim.keys()), key="fav_eliminar")

    confirmar = st.checkbox(
        "Confirmo que quiero eliminar este favorito",
        key="fav_confirmar_elim")
    if st.button("Eliminar", key="fav_btn_elim", disabled=not confirmar):
        db.eliminar_favorito(opciones_elim[fav_eliminar])
        st.success("Eliminado.")
        st.rerun()
else:
    st.caption("No hay favoritos para eliminar.")


# ═══════════════════════════════════════════════════════════════════════
# 3) LISTA DE FAVORITOS CON INDICADORES  (parte inferior)
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
encabezado("Tus favoritos", "list", nivel=3)

if not df_favs.empty:
    with st.spinner("Analizando favoritos..."):
        df_enriquecido = _enriquecer_favoritos(db, df_favs)

    if not df_enriquecido.empty:
        # ── Metricas resumen ──────────────────────────────────────
        total = len(df_enriquecido)
        en_minimo = (df_enriquecido['estado'] == 'minimo').sum()
        bajaron = (df_enriquecido['estado'] == 'bajo').sum()
        subieron = (df_enriquecido['estado'] == 'subio').sum()

        fila_metricas([
            ("bookmark", str(total), "Favoritos"),
            ("arrow_downward", str(en_minimo), "En minimo"),
            ("trending_down", str(bajaron), "Bajaron"),
            ("trending_up", str(subieron), "Subieron"),
        ])

        # ── Oportunidades destacadas ──────────────────────────────
        df_oportunidades = df_enriquecido[
            df_enriquecido['estado'].isin(['minimo', 'bajo'])
        ]
        if not df_oportunidades.empty:
            encabezado("Oportunidades", "local_offer", nivel=3)
            for _, row in df_oportunidades.iterrows():
                icono, tipo = _icono_estado(row['estado'])
                badges = [(_texto_estado(row['estado']), tipo)]
                if row['variacion'] != 0:
                    badges.append((f"{row['variacion']:+.2f} EUR", tipo))
                st.markdown(
                    tarjeta_producto_html(
                        nombre=row['nombre'],
                        supermercado=row['supermercado'],
                        precio=row['precio_actual'],
                        formato=row.get('formato_normalizado', ''),
                        badges_extra=badges,
                    ),
                    unsafe_allow_html=True)
            st.markdown("---")

        # ── Todos los favoritos ───────────────────────────────────
        col_orden, _ = st.columns([1, 3])
        with col_orden:
            orden_fav = st.selectbox(
                "Ordenar por:",
                ["Estado (oportunidades primero)",
                 "Precio menor", "Precio mayor", "Nombre A-Z"],
                key="fav_orden")

        if orden_fav == "Estado (oportunidades primero)":
            orden_estados = {'minimo': 0, 'bajo': 1, 'estable': 2, 'subio': 3}
            df_enriquecido['_orden'] = df_enriquecido['estado'].map(orden_estados)
            df_ordenado = df_enriquecido.sort_values(['_orden', 'precio_actual'])
        elif orden_fav == "Precio menor":
            df_ordenado = df_enriquecido.sort_values('precio_actual')
        elif orden_fav == "Precio mayor":
            df_ordenado = df_enriquecido.sort_values('precio_actual', ascending=False)
        else:
            df_ordenado = df_enriquecido.sort_values('nombre')

        for _, row in df_ordenado.iterrows():
            icono, tipo = _icono_estado(row['estado'])
            badges = [(_texto_estado(row['estado']), tipo)]
            if row['variacion'] != 0:
                badges.append((f"{row['variacion']:+.2f} EUR", tipo))
            if row.get('marca'):
                badges.append((row['marca'], 'neutral'))
            st.markdown(
                tarjeta_producto_html(
                    nombre=row['nombre'],
                    supermercado=row['supermercado'],
                    precio=row['precio_actual'],
                    formato=row.get('formato_normalizado', ''),
                    badges_extra=badges,
                ),
                unsafe_allow_html=True)
    else:
        estado_vacio(
            "bookmark_border",
            "No se pudieron cargar los datos de favoritos",
            "Puede haber un problema con la base de datos."
        )
else:
    estado_vacio(
        "bookmark_border",
        "No tienes productos en favoritos",
        "Usa el buscador de arriba para anadir productos."
    )
