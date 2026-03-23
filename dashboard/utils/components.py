# -*- coding: utf-8 -*-
"""Componentes UI reutilizables para el dashboard.

Funciones que generan HTML para inyectar con st.markdown(unsafe_allow_html=True).
Todas usan las clases CSS definidas en styles.py.
"""

import math
import streamlit as st
from dashboard.utils.styles import COLORES_SUPERMERCADO


# ═══════════════════════════════════════════════════════════════════════
# ENCABEZADOS
# ═══════════════════════════════════════════════════════════════════════

def encabezado(texto, icono, nivel=2):
    """Renderiza un encabezado con Material Icon."""
    tag = f"h{nivel}"
    st.markdown(
        f'<div class="icon-header">'
        f'<span class="material-icons-outlined">{icono}</span>'
        f'<{tag}>{texto}</{tag}></div>',
        unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# TARJETAS DE METRICAS
# ═══════════════════════════════════════════════════════════════════════

def fila_metricas(metricas):
    """Renderiza una fila de tarjetas de metricas.

    Args:
        metricas: lista de tuplas (icono, valor, etiqueta)
    """
    html = '<div class="metric-row" role="group" aria-label="Metricas">'
    for icono, valor, etiqueta in metricas:
        html += (
            f'<div class="metric-card">'
            f'<div class="metric-icon">'
            f'<span class="material-icons-outlined" aria-hidden="true">{icono}</span>'
            f'</div>'
            f'<div class="metric-value">{valor}</div>'
            f'<div class="metric-label">{etiqueta}</div>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# TARJETAS DE INSIGHT (decision rapida)
# ═══════════════════════════════════════════════════════════════════════

def fila_insights(insights):
    """Renderiza tarjetas de insight para decision rapida.

    Args:
        insights: lista de dicts con claves:
            icono, tipo, titulo, valor, detalle (opcional)
    """
    html = '<div class="insight-row" role="group" aria-label="Insights">'
    for ins in insights:
        detalle_html = (
            f'<div class="insight-detail">{ins.get("detalle", "")}</div>'
            if ins.get("detalle") else ""
        )
        html += (
            f'<div class="insight-card">'
            f'<span class="material-icons-outlined insight-icon {ins["tipo"]}" '
            f'aria-hidden="true">{ins["icono"]}</span>'
            f'<div class="insight-body">'
            f'<div class="insight-title">{ins["titulo"]}</div>'
            f'<div class="insight-value">{ins["valor"]}</div>'
            f'{detalle_html}'
            f'</div></div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def insight_card(icono, tipo, titulo, valor, detalle="", compacto=False):
    """Renderiza una tarjeta de insight individual."""
    clase_compact = " compact" if compacto else ""
    detalle_html = (
        f'<div class="insight-detail">{detalle}</div>' if detalle else ""
    )
    st.markdown(
        f'<div class="insight-card{clase_compact}">'
        f'<span class="material-icons-outlined insight-icon {tipo}" '
        f'aria-hidden="true">{icono}</span>'
        f'<div class="insight-body">'
        f'<div class="insight-title">{titulo}</div>'
        f'<div class="insight-value">{valor}</div>'
        f'{detalle_html}'
        f'</div></div>',
        unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# BADGES / CHIPS
# ═══════════════════════════════════════════════════════════════════════

def badge_html(texto, tipo="neutral", icono=None):
    """Genera HTML de un badge."""
    icono_html = (
        f'<span class="material-icons-outlined" aria-hidden="true">{icono}</span>'
        if icono else ""
    )
    return (
        f'<span class="badge {tipo}">'
        f'{icono_html}{texto}'
        f'</span>'
    )


def badge(texto, tipo="neutral", icono=None):
    """Renderiza un badge directamente."""
    st.markdown(badge_html(texto, tipo, icono), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# ESTADOS UX (vacio, sin resultados, error)
# ═══════════════════════════════════════════════════════════════════════

def estado_vacio(icono, titulo, detalle=""):
    """Renderiza un estado vacio visual."""
    detalle_html = (
        f'<div class="estado-detalle">{detalle}</div>' if detalle else ""
    )
    st.markdown(
        f'<div class="estado-vacio">'
        f'<span class="material-icons-outlined" aria-hidden="true">{icono}</span>'
        f'<div class="estado-titulo">{titulo}</div>'
        f'{detalle_html}'
        f'</div>',
        unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# PAGINACION
# ═══════════════════════════════════════════════════════════════════════

def paginar_dataframe(df, clave_pagina, filas_por_pagina=20):
    """Pagina un DataFrame con controles de navegacion Streamlit."""
    total_filas = len(df)
    if total_filas == 0:
        return df

    total_paginas = math.ceil(total_filas / filas_por_pagina)

    if clave_pagina not in st.session_state:
        st.session_state[clave_pagina] = 1

    pagina_actual = st.session_state[clave_pagina]

    if pagina_actual > total_paginas:
        pagina_actual = 1
        st.session_state[clave_pagina] = 1

    inicio = (pagina_actual - 1) * filas_por_pagina
    fin = min(inicio + filas_por_pagina, total_filas)
    df_pagina = df.iloc[inicio:fin]

    st.markdown(
        f'<div class="pagination-info">'
        f'<span>Mostrando <span class="page-range">{inicio + 1}–{fin}</span>'
        f' de <span class="page-range">{total_filas}</span> resultados</span>'
        f'<span>Página {pagina_actual} de {total_paginas}</span>'
        f'</div>',
        unsafe_allow_html=True)

    if total_paginas > 1:
        col_prev, col_paginas, col_next = st.columns([1, 3, 1])

        with col_prev:
            if st.button(
                "Anterior", key=f"{clave_pagina}_prev",
                disabled=(pagina_actual <= 1),
                use_container_width=True
            ):
                st.session_state[clave_pagina] = pagina_actual - 1
                st.rerun()

        with col_paginas:
            nueva_pagina = st.select_slider(
                "Página", options=list(range(1, total_paginas + 1)),
                value=pagina_actual, key=f"{clave_pagina}_slider",
                label_visibility="collapsed"
            )
            if nueva_pagina != pagina_actual:
                st.session_state[clave_pagina] = nueva_pagina
                st.rerun()

        with col_next:
            if st.button(
                "Siguiente", key=f"{clave_pagina}_next",
                disabled=(pagina_actual >= total_paginas),
                use_container_width=True
            ):
                st.session_state[clave_pagina] = pagina_actual + 1
                st.rerun()

    return df_pagina


def reset_paginacion(clave_pagina):
    """Resetea la paginacion a la primera pagina."""
    if clave_pagina in st.session_state:
        st.session_state[clave_pagina] = 1


# ═══════════════════════════════════════════════════════════════════════
# BARRA DE FILTROS UNIFICADA
# ═══════════════════════════════════════════════════════════════════════

def barra_filtros(db, clave_vista, mostrar_busqueda=True, mostrar_super=True,
                  mostrar_categoria=True, mostrar_precio=False,
                  mostrar_orden=False, opciones_orden=None):
    """Renderiza una barra de filtros estandarizada."""
    filtros = {
        'busqueda': '',
        'supermercado': None,
        'categoria': None,
        'precio_min': 0.0,
        'precio_max': 999.0,
        'orden': None,
    }

    num_cols = sum([
        mostrar_busqueda, mostrar_super, mostrar_categoria,
        mostrar_precio, mostrar_orden
    ])

    if num_cols == 0:
        return filtros

    pesos = []
    if mostrar_busqueda:
        pesos.append(3)
    if mostrar_super:
        pesos.append(1.5)
    if mostrar_categoria:
        pesos.append(1.5)
    if mostrar_precio:
        pesos.append(2)
    if mostrar_orden:
        pesos.append(1.5)

    columnas = st.columns(pesos)
    idx = 0

    if mostrar_busqueda:
        with columnas[idx]:
            filtros['busqueda'] = st.text_input(
                "Buscar:", placeholder="Ej: leche, café, aceite...",
                key=f"{clave_vista}_busq")
        idx += 1

    if mostrar_super:
        with columnas[idx]:
            supers = _obtener_supermercados(db)
            opciones = ['Todos'] + supers
            sel = st.selectbox(
                "Supermercado:", opciones, key=f"{clave_vista}_super")
            filtros['supermercado'] = None if sel == 'Todos' else sel
        idx += 1

    if mostrar_categoria:
        with columnas[idx]:
            cats = db.obtener_categorias()
            opciones_cat = ['Todas'] + [c[0] for c in cats]
            sel_cat = st.selectbox(
                "Categoría:", opciones_cat, key=f"{clave_vista}_cat")
            filtros['categoria'] = None if sel_cat == 'Todas' else sel_cat
        idx += 1

    if mostrar_precio:
        with columnas[idx]:
            rango = st.slider(
                "Precio (€):", 0.0, 100.0, (0.0, 100.0),
                key=f"{clave_vista}_precio")
            filtros['precio_min'] = rango[0]
            filtros['precio_max'] = rango[1]
        idx += 1

    if mostrar_orden:
        with columnas[idx]:
            opts = opciones_orden or [
                "Precio menor", "Precio mayor", "Nombre A-Z"]
            filtros['orden'] = st.selectbox(
                "Ordenar por:", opts, key=f"{clave_vista}_orden")
        idx += 1

    return filtros


def aplicar_orden(df, orden, col_precio='precio'):
    """Aplica ordenacion a un DataFrame segun la seleccion del usuario."""
    if not orden or df.empty:
        return df
    if orden == "Precio menor":
        return df.sort_values(col_precio, ascending=True)
    elif orden == "Precio mayor":
        return df.sort_values(col_precio, ascending=False)
    elif orden == "Nombre A-Z":
        col_nombre = 'nombre' if 'nombre' in df.columns else df.columns[0]
        return df.sort_values(col_nombre)
    return df


# ═══════════════════════════════════════════════════════════════════════
# TARJETA DE PRODUCTO
# ═══════════════════════════════════════════════════════════════════════

def tarjeta_producto_html(nombre, supermercado, precio, formato="",
                          precio_unitario=None, unidad_precio="",
                          precio_referencia=None, unidad_referencia="",
                          badges_extra=None):
    """Genera HTML de una tarjeta de producto.

    Muestra el precio de venta en grande y, debajo en gris pequeño,
    el precio de referencia (€/kg, €/L...) cuando está disponible.
    """
    color_super = COLORES_SUPERMERCADO.get(supermercado, '#95A5A6')
    precio_str = (f"{precio:.2f} €"
                  if isinstance(precio, (int, float)) else str(precio))

    # precio_referencia tiene prioridad; precio_unitario es alias heredado
    _ref = precio_referencia if precio_referencia is not None else precio_unitario
    _ref_unidad = unidad_referencia if unidad_referencia else unidad_precio

    pu_html = ""
    if _ref and _ref_unidad:
        pu_html = (
            f'<div class="product-unit-price">'
            f'{_ref:.2f} {_ref_unidad}'
            f'</div>'
        )

    meta_parts = [supermercado]
    if formato:
        meta_parts.append(formato)

    badges_html = ""
    if badges_extra:
        badges_html = " ".join(
            badge_html(texto, tipo) for texto, tipo in badges_extra
        )
        badges_html = f'<div style="margin-top:4px">{badges_html}</div>'

    return (
        f'<div class="product-card">'
        f'<div class="product-super" style="background:{color_super}"></div>'
        f'<div class="product-info">'
        f'<div class="product-name" title="{nombre}">{nombre}</div>'
        f'<div class="product-meta">{" · ".join(meta_parts)}</div>'
        f'{badges_html}'
        f'</div>'
        f'<div style="text-align:right">'
        f'<div class="product-price">{precio_str}</div>'
        f'{pu_html}'
        f'</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════

def sidebar_branding(db_path=""):
    """Renderiza el branding del sidebar."""
    import os
    st.sidebar.markdown(
        '<div class="sidebar-title">'
        '<span class="material-icons-outlined">shopping_cart</span>'
        'Price Tracker</div>', unsafe_allow_html=True)
    st.sidebar.markdown("---")
    if db_path:
        st.sidebar.caption(f"BD: `{os.path.basename(db_path)}`")


# ═══════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def _obtener_supermercados(_db):
    """Obtiene lista de supermercados (cacheada 5 min)."""
    df = _db.obtener_productos_con_precio_actual()
    if df.empty:
        return []
    return sorted(df['supermercado'].unique().tolist())


# ═══════════════════════════════════════════════════════════════════════
# CESTA DE LA COMPRA (helper compartido entre páginas)
# ═══════════════════════════════════════════════════════════════════════

def añadir_a_cesta_rapido(producto_id, nombre, supermercado, precio,
                           formato_normalizado=""):
    """Añade un producto a la cesta rápidamente desde cualquier página.

    Inicializa session_state['cesta'] si no existe.
    Si el producto ya está en la cesta, incrementa la cantidad.
    """
    if 'cesta' not in st.session_state:
        st.session_state['cesta'] = []

    # Comprobar si ya está
    for item in st.session_state['cesta']:
        if item.get('producto_id') == int(producto_id):
            item['cantidad'] += 1
            return

    st.session_state['cesta'].append({
        'producto_id': int(producto_id),
        'nombre': nombre,
        'supermercado': supermercado,
        'precio': float(precio),
        'formato_normalizado': formato_normalizado,
        'marca': '',
        'cantidad': 1,
        'alternativa_id': None,
        'alternativa_nombre': None,
        'alternativa_super': None,
        'alternativa_precio': None,
        'original_id': None,
        'original_nombre': None,
        'original_super': None,
        'original_precio': None,
    })


# ═══════════════════════════════════════════════════════════════════════
# CONSULTAR PRODUCTO EN LA WEB
# ═══════════════════════════════════════════════════════════════════════

def obtener_url_producto(db, producto_id):
    """Obtiene la URL de un producto desde la BD.

    Si la columna url está vacía (problema de case en guardar_productos),
    construye la URL a partir de id_externo + supermercado usando los
    patrones conocidos de cada supermercado.

    Returns:
        str: URL del producto o cadena vacía si no es posible.
    """
    # Patrones de URL conocidos por supermercado
    _URL_PATTERNS = {
        'Alcampo': 'https://www.compraonline.alcampo.es/products/{}',
        'Eroski': 'https://www.eroski.es/es/productdetail/{}/',
        'Carrefour': 'https://www.carrefour.es/supermercado/{}',
    }

    try:
        cur = db._cursor()
        cur.execute(
            "SELECT url, id_externo, supermercado "
            "FROM productos WHERE id = %s",
            (int(producto_id),))
        row = cur.fetchone()
        if row is None:
            return ""

        # 1) Intentar URL almacenada directamente
        url = row[0]
        if url and isinstance(url, str) and url.strip():
            return url.strip()

        # 2) Fallback: construir URL desde id_externo + supermercado
        id_externo = row[1]
        supermercado = row[2]
        if id_externo and supermercado:
            patron = _URL_PATTERNS.get(supermercado)
            if patron:
                return patron.format(id_externo)

        return ""
    except Exception:
        return ""


def boton_consultar_web(url, key_suffix=""):
    """Renderiza un botón 'Consultar producto en la web'.

    Si la URL está vacía o no existe, muestra el botón deshabilitado.

    Args:
        url: URL del producto
        key_suffix: sufijo para la key del botón (evitar duplicados)
    """
    if url:
        st.markdown(
            f'<a href="{url}" target="_blank" '
            f'style="display:inline-flex;align-items:center;'
            f'justify-content:center;gap:8px;width:100%;'
            f'padding:8px 16px;border:1px solid #E0E4E8;'
            f'border-radius:8px;background:#FFFFFF;'
            f'color:#1565C0;text-decoration:none;'
            f'font-size:14px;font-weight:500;'
            f'font-family:Inter,sans-serif;cursor:pointer;'
            f'transition:all 0.2s"'
            f' onmouseover="this.style.background=\'#E3F2FD\';'
            f'this.style.borderColor=\'#90CAF9\'"'
            f' onmouseout="this.style.background=\'#FFFFFF\';'
            f'this.style.borderColor=\'#E0E4E8\'">'
            f'<span class="material-icons-outlined" '
            f'style="font-size:18px">open_in_new</span>'
            f'Consultar producto en la web</a>',
            unsafe_allow_html=True)
    else:
        st.button("URL no disponible", disabled=True,
                  key=f"url_na_{key_suffix}",
                  use_container_width=True)


def añadir_lista_favoritos_a_cesta(db):
    """Añade todos los productos de favoritos a la cesta."""
    df_favs = db.obtener_favoritos()
    if df_favs.empty:
        return 0

    count = 0
    for _, row in df_favs.iterrows():
        añadir_a_cesta_rapido(
            int(row['id']),
            row.get('nombre', ''),
            row.get('supermercado', ''),
            float(row.get('precio', 0)),
            row.get('formato_normalizado', ''))
        count += 1
    return count
