# -*- coding: utf-8 -*-
"""Página: Calculadora de cesta de la compra."""

import sys, os, json, tempfile, subprocess

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_DB_PATH = os.environ.get(
    "SUPERMARKET_DB_PATH",
    os.path.join(_PROJECT_ROOT, "database", "supermercados.db"))

import streamlit as st
import pandas as pd
from datetime import datetime
from database.database_db_manager import DatabaseManager
from database.init_db import inicializar_base_datos
from dashboard.utils.styles import inyectar_estilos, COLORES_SUPERMERCADO
from dashboard.utils.components import (
    encabezado, fila_metricas, estado_vacio,
    barra_filtros, badge_html,
)
from dashboard.utils.export import (
    generar_pdf_cesta, generar_enlaces_email,
)
from routing import geocodificar, buscar_supermercados_cercanos, calcular_ruta_optima
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Cesta de la compra", page_icon="",
                   layout="wide")
inyectar_estilos()

encabezado("Cesta de la compra", "shopping_cart")
st.caption(
    "Tu cesta se guarda durante la sesión. "
    "Descárgala como PDF o envíala a tu email para no perderla.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)

# ── Límite de productos ──────────────────────────────────────────────
_MAX_ITEMS = 80


# ═══════════════════════════════════════════════════════════════════════
# INICIALIZAR SESSION STATE
# ═══════════════════════════════════════════════════════════════════════

if 'cesta' not in st.session_state:
    st.session_state['cesta'] = []


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════

def _buscar_alternativa(db, producto_id):
    """Busca alternativa más barata. Devuelve dict o None."""
    if not hasattr(db, 'buscar_alternativa_mas_barata'):
        return None
    try:
        return db.buscar_alternativa_mas_barata(producto_id)
    except Exception:
        return None


def _añadir_a_cesta(db, producto_id, cantidad):
    """Añade un producto a la cesta con detección de alternativa."""
    if len(st.session_state['cesta']) >= _MAX_ITEMS:
        st.warning(f"Límite de {_MAX_ITEMS} productos alcanzado.")
        return False

    # Comprobar si ya está en la cesta
    for item in st.session_state['cesta']:
        if item['producto_id'] == producto_id:
            item['cantidad'] += cantidad
            return True

    # Obtener datos del producto
    if hasattr(db, 'obtener_producto_por_id'):
        prod = db.obtener_producto_por_id(producto_id)
    else:
        prod = None

    if not prod:
        st.error("No se encontró el producto.")
        return False

    # Buscar alternativa
    alt = _buscar_alternativa(db, producto_id)

    item = {
        'producto_id': int(prod['id']),
        'nombre': prod.get('nombre', ''),
        'supermercado': prod.get('supermercado', ''),
        'precio': float(prod.get('precio', 0)),
        'formato_normalizado': prod.get('formato_normalizado', ''),
        'marca': prod.get('marca', ''),
        'url_imagen': prod.get('url_imagen', ''),
        'cantidad': cantidad,
        'alternativa_id': int(alt['id']) if alt else None,
        'alternativa_nombre': alt.get('nombre') if alt else None,
        'alternativa_super': alt.get('supermercado') if alt else None,
        'alternativa_precio': float(alt['precio']) if alt else None,
        # Datos originales para deshacer intercambio
        'original_id': None,
        'original_nombre': None,
        'original_super': None,
        'original_precio': None,
    }
    st.session_state['cesta'].append(item)
    return True


def _quitar_de_cesta(indice):
    """Elimina un producto de la cesta por índice."""
    if 0 <= indice < len(st.session_state['cesta']):
        st.session_state['cesta'].pop(indice)


def _intercambiar_producto(db, indice):
    """Intercambia un producto por su alternativa más barata."""
    cesta = st.session_state['cesta']
    if indice < 0 or indice >= len(cesta):
        return
    item = cesta[indice]
    if not item.get('alternativa_id'):
        return

    # Guardar original para deshacer
    item['original_id'] = item['producto_id']
    item['original_nombre'] = item['nombre']
    item['original_super'] = item['supermercado']
    item['original_precio'] = item['precio']
    item['original_url_imagen'] = item.get('url_imagen', '')

    # Reemplazar con alternativa
    item['producto_id'] = item['alternativa_id']
    item['nombre'] = item['alternativa_nombre']
    item['supermercado'] = item['alternativa_super']
    item['precio'] = item['alternativa_precio']
    alt_prod = db.obtener_producto_por_id(item['producto_id'])
    item['url_imagen'] = alt_prod.get('url_imagen', '') if alt_prod else ''

    # Recalcular alternativa desde la nueva posición
    nueva_alt = _buscar_alternativa(db, item['producto_id'])
    item['alternativa_id'] = int(nueva_alt['id']) if nueva_alt else None
    item['alternativa_nombre'] = nueva_alt.get('nombre') if nueva_alt else None
    item['alternativa_super'] = nueva_alt.get('supermercado') if nueva_alt else None
    item['alternativa_precio'] = float(nueva_alt['precio']) if nueva_alt else None


def _deshacer_intercambio(db, indice):
    """Deshace un intercambio previo restaurando el producto original."""
    cesta = st.session_state['cesta']
    if indice < 0 or indice >= len(cesta):
        return
    item = cesta[indice]
    if not item.get('original_id'):
        return

    # Restaurar original
    item['producto_id'] = item['original_id']
    item['nombre'] = item['original_nombre']
    item['supermercado'] = item['original_super']
    item['precio'] = item['original_precio']
    item['url_imagen'] = item.get('original_url_imagen', '')

    # Limpiar backup
    item['original_id'] = None
    item['original_nombre'] = None
    item['original_super'] = None
    item['original_precio'] = None

    # Recalcular alternativa
    nueva_alt = _buscar_alternativa(db, item['producto_id'])
    item['alternativa_id'] = int(nueva_alt['id']) if nueva_alt else None
    item['alternativa_nombre'] = nueva_alt.get('nombre') if nueva_alt else None
    item['alternativa_super'] = nueva_alt.get('supermercado') if nueva_alt else None
    item['alternativa_precio'] = float(nueva_alt['precio']) if nueva_alt else None


def _optimizar_toda_la_cesta(db):
    """Intercambia todos los productos que tienen alternativa más barata."""
    for i, item in enumerate(st.session_state['cesta']):
        if (item.get('alternativa_id')
                and item.get('alternativa_precio') is not None
                and item['alternativa_precio'] < item['precio']
                and not item.get('original_id')):
            _intercambiar_producto(db, i)


def _calcular_totales(cesta):
    """Calcula métricas de la cesta."""
    total = sum(i['precio'] * i['cantidad'] for i in cesta)
    n_items = sum(i['cantidad'] for i in cesta)
    ahorro = sum(
        (i['precio'] - i['alternativa_precio']) * i['cantidad']
        for i in cesta
        if i.get('alternativa_precio') is not None
        and i['alternativa_precio'] < i['precio']
    )
    optimizado = total - ahorro
    return {
        'total': total,
        'n_items': n_items,
        'n_productos': len(cesta),
        'ahorro': ahorro,
        'optimizado': optimizado,
    }


def _tarjeta_cesta_html(item, indice):
    """Genera HTML de una tarjeta de producto en la cesta."""
    color = COLORES_SUPERMERCADO.get(item['supermercado'], '#95A5A6')
    subtotal = item['precio'] * item['cantidad']
    formato = item.get('formato_normalizado', '')

    meta_parts = [item['supermercado']]
    if formato:
        meta_parts.append(formato)
    meta_parts.append(f"x{item['cantidad']}")

    # Badge de alternativa
    badge = ""
    alt_precio = item.get('alternativa_precio')
    if item.get('original_id'):
        # Fue intercambiado → badge azul
        ahorro = item['original_precio'] - item['precio']
        badge = (
            f'<span class="badge primary">'
            f'<span class="material-icons-outlined" '
            f'style="font-size:14px">swap_horiz</span>'
            f'Intercambiado (ahorras {ahorro:.2f} €)</span>')
    elif alt_precio is not None and alt_precio < item['precio']:
        diff = item['precio'] - alt_precio
        badge = (
            f'<span class="badge success">'
            f'<span class="material-icons-outlined" '
            f'style="font-size:14px">local_offer</span>'
            f'-{diff:.2f} € en {item["alternativa_super"]}</span>')
    else:
        badge = (
            '<span class="badge neutral">'
            '<span class="material-icons-outlined" '
            'style="font-size:14px">check_circle</span>'
            'Mejor precio</span>')

    return (
        f'<div class="product-card" style="margin-bottom:6px">'
        f'<div class="product-super" style="background:{color}"></div>'
        f'<div class="product-info">'
        f'<div class="product-name" title="{item["nombre"]}">'
        f'{item["nombre"]}</div>'
        f'<div class="product-meta">{" · ".join(meta_parts)}</div>'
        f'<div style="margin-top:4px">{badge}</div>'
        f'</div>'
        f'<div style="text-align:right">'
        f'<div class="product-price">{subtotal:.2f} €</div>'
        f'<div class="product-unit-price">'
        f'{item["precio"]:.2f} €/ud</div>'
        f'</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════
# SECCIÓN A: BUSCADOR + AÑADIR PRODUCTO
# ═══════════════════════════════════════════════════════════════════════
encabezado("Añadir productos", "add_shopping_cart", nivel=3)

if '_supers_cesta' not in st.session_state:
    _df_todos = db.obtener_productos_con_precio_actual()
    st.session_state['_supers_cesta'] = (
        ['Todos'] + sorted(_df_todos['supermercado'].unique().tolist())
        if not _df_todos.empty else ['Todos'])

col_busq, col_super, col_cant, col_btn_busq = st.columns([3, 1.5, 1, 1])
with col_busq:
    busqueda_cesta = st.text_input(
        "Buscar producto:",
        placeholder="Ej: leche, arroz, aceite...",
        key="cesta_busq")
with col_super:
    filtro_super = st.selectbox(
        "Supermercado:",
        st.session_state['_supers_cesta'],
        key="cesta_super")
with col_cant:
    cantidad_input = st.number_input(
        "Cantidad:", min_value=1, max_value=99,
        value=1, key="cesta_cant")
with col_btn_busq:
    st.markdown('<div style="margin-top:28px"></div>', unsafe_allow_html=True)
    if st.button("Buscar", key="cesta_btn_busq",
                 type="primary", use_container_width=True):
        super_param = None if filtro_super == 'Todos' else filtro_super
        with st.spinner("Buscando..."):
            st.session_state['_cesta_res'] = db.buscar_productos(
                nombre=busqueda_cesta,
                supermercado=super_param,
                limite=100)

if not busqueda_cesta:
    st.session_state.pop('_cesta_res', None)

_df_res = st.session_state.get('_cesta_res')
if _df_res is not None:
    if not _df_res.empty:
        if 'prioridad' in _df_res.columns:
            _df_prio = _df_res[_df_res['prioridad'] == 1]
            if not _df_prio.empty:
                _df_res = _df_prio

        opciones = {
            (f"{row['nombre']} ({row['supermercado']}) - "
             f"{row.get('precio', '?')} €"): int(row['id'])
            for _, row in _df_res.iterrows()
        }
        sel_producto = st.selectbox(
            f"Productos encontrados ({len(_df_res)}):",
            list(opciones.keys()), key="cesta_sel")

        if st.button("Añadir a la cesta", key="cesta_btn_add",
                      type="primary"):
            ok = _añadir_a_cesta(db, opciones[sel_producto],
                                  cantidad_input)
            if ok:
                st.session_state.pop('_cesta_res', None)
                st.success("Producto añadido a la cesta.")
                st.rerun()
    else:
        estado_vacio(
            "search_off",
            f"No se encontraron productos con '{busqueda_cesta}'",
            "Prueba con otro término.")


# ═══════════════════════════════════════════════════════════════════════
# SECCIÓN B: CONTENIDO DE LA CESTA
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
cesta = st.session_state['cesta']

if cesta:
    totales = _calcular_totales(cesta)

    # ═══════════════════════════════════════════════════════════════
    # RESUMEN
    # ═══════════════════════════════════════════════════════════════
    encabezado("Resumen", "receipt_long", nivel=3)

    fila_metricas([
        ("shopping_bag", str(totales['n_items']), "Unidades"),
        ("payments", f"{totales['total']:.2f} €", "Total"),
        ("savings", f"{totales['ahorro']:.2f} €", "Ahorro posible"),
        ("price_check", f"{totales['optimizado']:.2f} €", "Optimizado"),
    ])

    # ═══════════════════════════════════════════════════════════════
    # DESGLOSE POR SUPERMERCADO
    # ═══════════════════════════════════════════════════════════════
    st.markdown("")
    encabezado("Desglose por supermercado", "storefront", nivel=3)

    por_super = {}
    for item in cesta:
        s = item['supermercado']
        if s not in por_super:
            por_super[s] = {'productos': 0, 'subtotal': 0.0}
        por_super[s]['productos'] += item['cantidad']
        por_super[s]['subtotal'] += item['precio'] * item['cantidad']

    datos_desglose = []
    total_envios = 0.0
    avisos_pedido_minimo = []

    for s, v in sorted(por_super.items()):
        subtotal = v['subtotal']
        envio = db.obtener_envio_supermercado(s)

        if envio:
            coste_envio = envio['coste_envio']
            umbral = envio.get('umbral_gratis')
            minimo = envio.get('pedido_minimo')

            if minimo and subtotal < minimo:
                faltan_min = minimo - subtotal
                avisos_pedido_minimo.append(
                    f"**{s}**: pedido mínimo {minimo:.2f} €. "
                    f"Te faltan **{faltan_min:.2f} €**.")
                envio_txt = f"{coste_envio:.2f} €"
                nota_envio = f"Mínimo no alcanzado ({minimo:.2f} €)"
            elif umbral and subtotal >= umbral:
                coste_envio = 0.0
                envio_txt = "Gratis"
                nota_envio = f"Envío gratis (≥ {umbral:.2f} €)"
            else:
                if umbral:
                    faltan = umbral - subtotal
                    nota_envio = f"Te faltan {faltan:.2f} € para envío gratis"
                else:
                    nota_envio = envio.get('notas', '')
                envio_txt = f"{coste_envio:.2f} €"
        else:
            coste_envio = 0.0
            envio_txt = "—"
            nota_envio = "Sin datos de envío"

        total_envios += coste_envio
        datos_desglose.append({
            'Supermercado': s,
            'Unidades': v['productos'],
            'Subtotal': f"{subtotal:.2f} €",
            'Envío': envio_txt,
            'Total c/envío': f"{subtotal + coste_envio:.2f} €",
            'Nota envío': nota_envio,
        })

    if avisos_pedido_minimo:
        for aviso in avisos_pedido_minimo:
            st.warning(aviso)

    if datos_desglose:
        st.dataframe(
            pd.DataFrame(datos_desglose),
            use_container_width=True, hide_index=True)
        total_con_envio = totales['total'] + total_envios
        st.markdown(
            f"**Total productos:** {totales['total']:.2f} €  ·  "
            f"**Total envíos:** {total_envios:.2f} €  ·  "
            f"**Total real:** {total_con_envio:.2f} €")
        st.caption(
            "Los costes de envío son orientativos y pueden variar según "
            "zona, promociones o condiciones del momento.")

    # ═══════════════════════════════════════════════════════════════
    # RUTA DE COMPRA
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    encabezado("Ruta de compra", "route", nivel=3)
    st.caption(
        "Encuentra la tienda más cercana de cada supermercado de tu cesta "
        "y calcula la ruta óptima entre ellas.")

    # Cachear resultados de ruta en session_state
    if 'ruta_cache' not in st.session_state:
        st.session_state['ruta_cache'] = {
            'direccion': None, 'tiendas': None, 'ruta': None,
            'origen': None, 'supermercados': None,
        }

    col_dir, col_modo, col_radio = st.columns([3, 1, 1])
    with col_dir:
        direccion_ruta = st.text_input(
            "Tu dirección o código postal:",
            placeholder="Ej: Calle Mayor 1, Madrid / 28001",
            key="ruta_direccion")
    with col_modo:
        modos = {"Coche": "driving", "A pie": "walking", "Bici": "cycling"}
        modo_sel = st.selectbox("Transporte:", list(modos.keys()),
                                key="ruta_modo")
    with col_radio:
        radio_km = st.slider("Radio (km):", 1, 15, 5, key="ruta_radio")

    if st.button("Calcular ruta", key="ruta_calcular", type="primary",
                  use_container_width=True):
        if not direccion_ruta.strip():
            st.error("Introduce una dirección o código postal.")
        else:
            supermercados_cesta = list(set(
                item['supermercado'] for item in cesta))

            with st.spinner("Geocodificando dirección..."):
                origen = geocodificar(direccion_ruta.strip())

            if not origen:
                st.error(
                    "No se pudo encontrar la dirección. "
                    "Prueba con otra más específica.")
            else:
                with st.spinner(
                    f"Buscando tiendas en un radio de {radio_km} km..."
                ):
                    tiendas_result = buscar_supermercados_cercanos(
                        origen['lat'], origen['lon'],
                        supermercados_cesta,
                        radio_metros=radio_km * 1000)

                # Recopilar tiendas encontradas
                tiendas_encontradas = []
                tiendas_no_encontradas = []
                for s, lista_tiendas in tiendas_result.items():
                    if lista_tiendas:
                        t = lista_tiendas[0]
                        tiendas_encontradas.append({
                            **t, "supermercado": s})
                    else:
                        tiendas_no_encontradas.append(s)

                # Avisos de tiendas no encontradas
                for s in tiendas_no_encontradas:
                    st.warning(
                        f"No se encontró tienda de **{s}** "
                        f"en un radio de {radio_km} km.")

                ruta_datos = None
                if tiendas_encontradas:
                    with st.spinner("Calculando ruta óptima..."):
                        ruta_datos = calcular_ruta_optima(
                            origen, tiendas_encontradas,
                            modo=modos[modo_sel])

                    if not ruta_datos:
                        st.info(
                            "No se pudo calcular la ruta óptima. "
                            "Mostrando tiendas en el mapa sin ruta.")

                # Guardar en cache
                st.session_state['ruta_cache'] = {
                    'direccion': direccion_ruta.strip(),
                    'origen': origen,
                    'tiendas': tiendas_encontradas,
                    'ruta': ruta_datos,
                    'supermercados': supermercados_cesta,
                }

    # ── Renderizar mapa y resultados desde cache ──
    cache = st.session_state['ruta_cache']
    if cache.get('origen') and cache.get('tiendas') is not None:
        origen = cache['origen']
        tiendas_encontradas = cache['tiendas']
        ruta_datos = cache['ruta']

        st.markdown(
            f"Ubicación: **{origen.get('display_name', cache['direccion'])}**")

        # Generar mapa Folium
        mapa = folium.Map(
            location=[origen["lat"], origen["lon"]],
            zoom_start=14,
            tiles="OpenStreetMap",
        )

        # Marcador de casa
        folium.Marker(
            location=[origen["lat"], origen["lon"]],
            popup="Tu ubicación",
            icon=folium.Icon(color="black", icon="home", prefix="fa"),
        ).add_to(mapa)

        # Marcadores de tiendas
        for tienda in tiendas_encontradas:
            color_hex = COLORES_SUPERMERCADO.get(
                tienda["supermercado"], "#95A5A6")
            folium.Marker(
                location=[tienda["lat"], tienda["lon"]],
                popup=(f"{tienda['nombre']}<br>"
                       f"{tienda.get('direccion', '')}<br>"
                       f"{tienda.get('distancia_m', '?')} m"),
                icon=folium.Icon(
                    color="green",
                    icon="shopping-cart",
                    prefix="fa",
                    icon_color=color_hex,
                ),
            ).add_to(mapa)

        # Línea de ruta
        if ruta_datos and ruta_datos.get("geometria"):
            # GeoJSON viene en [lon, lat], Folium espera [lat, lon]
            puntos_ruta = [[p[1], p[0]]
                           for p in ruta_datos["geometria"]]
            folium.PolyLine(
                locations=puntos_ruta,
                color="#1565C0",
                weight=4,
                opacity=0.8,
            ).add_to(mapa)

        # Ajustar zoom para que se vean todos los puntos
        todos_puntos = [[origen["lat"], origen["lon"]]]
        for t in tiendas_encontradas:
            todos_puntos.append([t["lat"], t["lon"]])
        if len(todos_puntos) > 1:
            mapa.fit_bounds(todos_puntos)

        st_folium(mapa, width=700, height=450)

        # Info de ruta debajo del mapa
        if ruta_datos:
            fila_metricas([
                ("route", f"{ruta_datos['distancia_total_km']} km",
                 "Distancia total"),
                ("schedule",
                 f"{ruta_datos['duracion_total_min']} min",
                 "Duración estimada"),
                ("storefront",
                 str(len(tiendas_encontradas)),
                 "Tiendas"),
            ])

            # ═══════════════════════════════════════════════════════
            # ORDEN DE PARADAS
            # ═══════════════════════════════════════════════════════
            st.markdown("---")
            encabezado("Orden de paradas", "format_list_numbered",
                       nivel=3)
            for idx, parada in enumerate(
                    ruta_datos.get("paradas_ordenadas", []), 1):
                tramo = (ruta_datos["tramos"][idx - 1]
                         if idx - 1 < len(ruta_datos["tramos"])
                         else None)
                tramo_txt = ""
                if tramo:
                    tramo_txt = (
                        f" — {tramo['distancia_km']} km, "
                        f"{tramo['duracion_min']} min")
                st.markdown(
                    f"**{idx}.** {parada.get('nombre', '')} "
                    f"({parada.get('supermercado', '')})"
                    f"{tramo_txt}")

        elif tiendas_encontradas:
            st.info(
                f"Se encontraron {len(tiendas_encontradas)} tiendas, "
                f"pero no se pudo calcular la ruta óptima.")

        if not tiendas_encontradas:
            estado_vacio(
                "wrong_location",
                "No se encontraron tiendas cercanas",
                "Prueba aumentando el radio de búsqueda.")

    # ═══════════════════════════════════════════════════════════════
    # TU CESTA
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    encabezado(
        f"Tu cesta ({totales['n_productos']} productos "
        f"· {totales['total']:.2f} €)",
        "shopping_bag", nivel=3)

    # Renderizar cada producto con botones de acción
    for i, item in enumerate(cesta):
        # Tarjeta visual (con imagen nativa si disponible)
        _url_img = item.get('url_imagen', '')
        _has_img = isinstance(_url_img, str) and _url_img.startswith('http')
        if _has_img:
            _ci, _cc = st.columns([1, 9])
            with _ci:
                st.markdown(
                    f'<img src="{_url_img}" width="56" '
                    f'style="border-radius:4px;object-fit:contain">',
                    unsafe_allow_html=True)
        else:
            _cc = st
        _cc.markdown(_tarjeta_cesta_html(item, i), unsafe_allow_html=True)

        # Botones de acción debajo de cada tarjeta
        cols_btn = st.columns([1, 1, 1, 3])

        with cols_btn[0]:
            if st.button("Quitar", key=f"cesta_quitar_{i}",
                          use_container_width=True):
                _quitar_de_cesta(i)
                st.rerun()

        with cols_btn[1]:
            # Botón de intercambiar o deshacer
            alt_precio = item.get('alternativa_precio')
            tiene_alt = (alt_precio is not None
                         and alt_precio < item['precio'])
            fue_intercambiado = item.get('original_id') is not None

            if fue_intercambiado:
                if st.button("Deshacer", key=f"cesta_deshacer_{i}",
                              use_container_width=True):
                    _deshacer_intercambio(db, i)
                    st.rerun()
            elif tiene_alt:
                if st.button("Intercambiar",
                              key=f"cesta_intercambiar_{i}",
                              use_container_width=True):
                    _intercambiar_producto(db, i)
                    st.rerun()

        with cols_btn[2]:
            # Ajustar cantidad
            nueva_cant = st.number_input(
                "Cant.", min_value=1, max_value=99,
                value=item['cantidad'],
                key=f"cesta_cant_{i}",
                label_visibility="collapsed")
            if nueva_cant != item['cantidad']:
                st.session_state['cesta'][i]['cantidad'] = nueva_cant
                st.rerun()

    # Botones de acción global
    st.markdown("")
    col_opt, col_clear = st.columns(2)

    with col_opt:
        n_intercambiables = sum(
            1 for i in cesta
            if i.get('alternativa_precio') is not None
            and i['alternativa_precio'] < i['precio']
            and not i.get('original_id')
        )
        if n_intercambiables > 0:
            if st.button(
                f"Optimizar toda la cesta "
                f"({n_intercambiables} cambios)",
                key="cesta_optimizar",
                type="primary",
                use_container_width=True
            ):
                _optimizar_toda_la_cesta(db)
                st.success("Cesta optimizada.")
                st.rerun()
        else:
            st.button(
                "Tu cesta ya está optimizada",
                disabled=True,
                use_container_width=True,
                key="cesta_optimizada_disabled")

    with col_clear:
        if st.button(
            "Limpiar cesta",
            key="cesta_limpiar",
            use_container_width=True
        ):
            st.session_state['cesta'] = []
            st.rerun()

    # ═══════════════════════════════════════════════════════════════
    # CARGAR EN CARRITO ONLINE (Carrefour / Alcampo)
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    encabezado("Cargar en carrito online", "shopping_cart_checkout", nivel=3)
    st.caption(
        "Abre un navegador, añade automáticamente tus productos al carrito "
        "del supermercado y te deja en la pantalla de pago para que completes "
        "el pedido con tus datos."
    )

    _SUPERMERCADOS_CARRITO = {
        "Carrefour": ("carrefour", "🔵"),
        "Alcampo":   ("alcampo",   "🟠"),
    }

    _cols_carrito = st.columns(len(_SUPERMERCADOS_CARRITO))

    for _col, (_nombre_super, (_clave, _emoji)) in zip(
        _cols_carrito, _SUPERMERCADOS_CARRITO.items()
    ):
        with _col:
            _items_super = [
                i for i in cesta
                if i.get("supermercado", "").lower() == _nombre_super.lower()
            ]
            _n = len(_items_super)
            _total_super = sum(
                i["precio"] * i["cantidad"] for i in _items_super
            )

            if _n == 0:
                st.button(
                    f"{_emoji} {_nombre_super}\n(sin productos)",
                    key=f"carrito_btn_{_clave}",
                    disabled=True,
                    use_container_width=True,
                )
            else:
                _label = (
                    f"{_emoji} Cargar en {_nombre_super}\n"
                    f"{_n} producto{'s' if _n > 1 else ''} · {_total_super:.2f} €"
                )
                if st.button(
                    _label,
                    key=f"carrito_btn_{_clave}",
                    use_container_width=True,
                    type="primary",
                ):
                    # Recopilar datos de cada producto (URL + id_externo desde BD)
                    _productos_cargar = []
                    for _item in _items_super:
                        _prod_db = db.obtener_producto_por_id(_item["producto_id"])
                        if _prod_db:
                            _productos_cargar.append({
                                "nombre":     _item["nombre"],
                                "cantidad":   _item["cantidad"],
                                "url":        _prod_db.get("url", ""),
                                "id_externo": _prod_db.get("id_externo", ""),
                            })

                    if not _productos_cargar:
                        st.error("No se encontraron URLs para los productos.")
                    else:
                        # Escribir JSON temporal y lanzar subprocess
                        try:
                            _tmp = tempfile.NamedTemporaryFile(
                                mode="w", suffix=".json",
                                delete=False, encoding="utf-8"
                            )
                            json.dump(_productos_cargar, _tmp, ensure_ascii=False)
                            _tmp.close()

                            _script = os.path.join(
                                _PROJECT_ROOT,
                                "dashboard", "utils", "cart_loader.py"
                            )
                            subprocess.Popen(
                                [sys.executable, _script,
                                 "--supermercado", _clave,
                                 "--archivo", _tmp.name],
                                cwd=_PROJECT_ROOT,
                            )
                            st.success(
                                f"Abriendo navegador con tu carrito de "
                                f"{_nombre_super}. Cuando se carguen todos "
                                f"los productos, completa el pedido con tus "
                                f"datos directamente en la web."
                            )
                        except Exception as _e:
                            st.error(f"Error al lanzar el navegador: {_e}")

    # ═══════════════════════════════════════════════════════════════
    # GUARDAR TU CESTA (PDF + email web)
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    encabezado("Guardar tu cesta", "save", nivel=3)

    # PDF
    nombre_pdf = f"lista_compra_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    try:
        pdf_bytes = generar_pdf_cesta(cesta)
        st.download_button(
            label="Descargar lista de la compra (PDF)",
            data=pdf_bytes,
            file_name=nombre_pdf,
            mime="application/pdf",
            key="cesta_pdf_download",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error al generar PDF: {e}")

    # Email web — botones con logo del servicio
    st.caption("Enviar por email (abre redacción en webmail):")
    st.info("Los proveedores web (Gmail/Outlook/Yahoo) no permiten adjuntar "
    "un PDF automáticamente desde un enlace por seguridad.\n\n"
    "Paso recomendado:\n"
    "1) Descarga la lista de la compra\n"
    "2) Adjunta el PDF manualmente al abrir el correo."
    )

    enlaces = generar_enlaces_email(cesta)

    # Logos de proveedores de correo (favicons por dominio, estables)
    _LOGO_GMAIL = "https://www.google.com/s2/favicons?domain=gmail.com&sz=64"
    _LOGO_OUTLOOK = "https://www.google.com/s2/favicons?domain=outlook.live.com&sz=64"
    _LOGO_YAHOO = "https://www.google.com/s2/favicons?domain=mail.yahoo.com&sz=64"

    _btn_base = (
        "display:flex;flex-direction:column;align-items:center;"
        "justify-content:center;gap:8px;width:100%;"
        "padding:14px 12px;border:1px solid #E0E4E8;"
        "border-radius:12px;background:#FFFFFF;"
        "text-decoration:none;cursor:pointer;"
        "transition:all 0.2s ease;"
        "box-shadow:0 1px 3px rgba(0,0,0,0.04)"
    )
    _btn_hover = "this.style.background='#F5F7FA';this.style.boxShadow='0 2px 8px rgba(0,0,0,0.08)';this.style.borderColor='#C4CDD5'"
    _btn_out = "this.style.background='#FFFFFF';this.style.boxShadow='0 1px 3px rgba(0,0,0,0.04)';this.style.borderColor='#E0E4E8'"
    _icon_circle_style = (
        "width:52px;height:52px;border-radius:999px;"
        "display:flex;align-items:center;justify-content:center;"
        "background:#FFFFFF;border:1px solid #E5E7EB;"
        "box-shadow:0 2px 6px rgba(0,0,0,0.08);overflow:hidden"
    )
    _icon_img_style = "width:32px;height:32px;object-fit:contain;border-radius:999px"
    _label_style = "font-size:11px;font-weight:500;color:#6B7280;font-family:Inter,sans-serif"

    col_gm, col_ol, col_yh = st.columns(3)

    with col_gm:
        st.markdown(
            f'<a href="{enlaces["gmail"]}" target="_blank" rel="noopener noreferrer" '
            f'style="{_btn_base}" title="Enviar con Gmail"'
            f' onmouseover="{_btn_hover}"'
            f' onmouseout="{_btn_out}">'
            f'<span style="{_icon_circle_style}"><img src="{_LOGO_GMAIL}" style="{_icon_img_style}" alt="Gmail"></span>'
            f'<span style="{_label_style}">Gmail</span></a>',
            unsafe_allow_html=True)

    with col_ol:
        st.markdown(
            f'<a href="{enlaces["outlook"]}" target="_blank" rel="noopener noreferrer" '
            f'style="{_btn_base}" title="Enviar con Outlook"'
            f' onmouseover="{_btn_hover}"'
            f' onmouseout="{_btn_out}">'
            f'<span style="{_icon_circle_style}"><img src="{_LOGO_OUTLOOK}" style="{_icon_img_style}" alt="Outlook"></span>'
            f'<span style="{_label_style}">Outlook</span></a>',
            unsafe_allow_html=True)

    with col_yh:
        st.markdown(
            f'<a href="{enlaces["yahoo"]}" target="_blank" rel="noopener noreferrer" '
            f'style="{_btn_base}" title="Enviar con Yahoo"'
            f' onmouseover="{_btn_hover}"'
            f' onmouseout="{_btn_out}">'
            f'<span style="{_icon_circle_style}"><img src="{_LOGO_YAHOO}" style="{_icon_img_style}" alt="Yahoo"></span>'
            f'<span style="{_label_style}">Yahoo</span></a>',
            unsafe_allow_html=True)

else:
    # Cesta vacía
    estado_vacio(
        "shopping_cart",
        "Tu cesta está vacía",
        "Busca productos arriba y añádelos a tu lista de la compra."
    )
