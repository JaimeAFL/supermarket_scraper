# -*- coding: utf-8 -*-
"""Página: Calculadora de cesta de la compra."""

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

    # Reemplazar con alternativa
    item['producto_id'] = item['alternativa_id']
    item['nombre'] = item['alternativa_nombre']
    item['supermercado'] = item['alternativa_super']
    item['precio'] = item['alternativa_precio']

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

col_busq, col_super, col_cant = st.columns([3, 1.5, 1])
with col_busq:
    busqueda_cesta = st.text_input(
        "Buscar producto:",
        placeholder="Ej: leche, arroz, aceite...",
        key="cesta_busq")
with col_super:
    df_todos = db.obtener_productos_con_precio_actual()
    supers_list = (['Todos'] + sorted(
        df_todos['supermercado'].unique().tolist())
        if not df_todos.empty else ['Todos'])
    filtro_super = st.selectbox(
        "Supermercado:", supers_list, key="cesta_super")
with col_cant:
    cantidad_input = st.number_input(
        "Cantidad:", min_value=1, max_value=99,
        value=1, key="cesta_cant")

if busqueda_cesta:
    super_param = None if filtro_super == 'Todos' else filtro_super
    with st.spinner("Buscando..."):
        df_res = db.buscar_productos(
            nombre=busqueda_cesta,
            supermercado=super_param,
            limite=100)

    if not df_res.empty:
        # Filtrar solo prioridad 1 si existe
        if 'prioridad' in df_res.columns:
            df_prio = df_res[df_res['prioridad'] == 1]
            if not df_prio.empty:
                df_res = df_prio

        opciones = {
            (f"{row['nombre']} ({row['supermercado']}) - "
             f"{row.get('precio', '?')} €"): int(row['id'])
            for _, row in df_res.iterrows()
        }
        sel_producto = st.selectbox(
            f"Productos encontrados ({len(df_res)}):",
            list(opciones.keys()), key="cesta_sel")

        if st.button("Añadir a la cesta", key="cesta_btn_add",
                      type="primary"):
            ok = _añadir_a_cesta(db, opciones[sel_producto],
                                  cantidad_input)
            if ok:
                st.success("Producto añadido a la cesta.")
                st.rerun()
    else:
        estado_vacio(
            "search_off",
            f"No se encontraron productos con '{busqueda_cesta}'",
            "Prueba con otro término.")


# ═══════════════════════════════════════════════════════════════════════
# SECCIÓN B: TU CESTA
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
cesta = st.session_state['cesta']

if cesta:
    totales = _calcular_totales(cesta)

    encabezado(
        f"Tu cesta ({totales['n_productos']} productos "
        f"· {totales['total']:.2f} €)",
        "shopping_bag", nivel=3)

    # Renderizar cada producto con botones de acción
    for i, item in enumerate(cesta):
        # Tarjeta visual
        st.markdown(
            _tarjeta_cesta_html(item, i),
            unsafe_allow_html=True)

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

    # ═══════════════════════════════════════════════════════════════
    # SECCIÓN C: RESUMEN Y TOTALES
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    encabezado("Resumen", "receipt_long", nivel=3)

    fila_metricas([
        ("shopping_bag", str(totales['n_items']), "Unidades"),
        ("payments", f"{totales['total']:.2f} €", "Total"),
        ("savings", f"{totales['ahorro']:.2f} €", "Ahorro posible"),
        ("price_check", f"{totales['optimizado']:.2f} €", "Optimizado"),
    ])

    # Desglose por supermercado
    st.markdown("")
    encabezado("Desglose por supermercado", "storefront", nivel=3)

    por_super = {}
    for item in cesta:
        s = item['supermercado']
        if s not in por_super:
            por_super[s] = {'productos': 0, 'subtotal': 0}
        por_super[s]['productos'] += item['cantidad']
        por_super[s]['subtotal'] += item['precio'] * item['cantidad']

    datos_desglose = [
        {
            'Supermercado': s,
            'Productos': v['productos'],
            'Subtotal': f"{v['subtotal']:.2f} €",
        }
        for s, v in sorted(por_super.items())
    ]
    if datos_desglose:
        st.dataframe(
            pd.DataFrame(datos_desglose),
            use_container_width=True, hide_index=True)

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
    # SECCIÓN D: GUARDAR TU CESTA (PDF + email web)
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    encabezado("Guardar tu cesta", "save", nivel=3)

    # PDF
    try:
        pdf_bytes = generar_pdf_cesta(cesta)
        nombre_pdf = (
            f"lista_compra_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
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
    st.caption("O envía la lista a tu correo (se abre en el navegador):")

    enlaces = generar_enlaces_email(cesta)

    # Logos de proveedores de correo (favicons por dominio, estables)
    # Evitamos depender de slugs/versiones de catálogos de iconos externos que
    # pueden cambiar y devolver 404 para algunas marcas.
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
