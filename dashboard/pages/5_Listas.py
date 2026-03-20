# -*- coding: utf-8 -*-
"""Página: Mis listas de la compra."""

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
)
from dashboard.utils.export import (
    generar_pdf_cesta, generar_enlaces_email,
)

st.set_page_config(page_title="Mis listas", page_icon="", layout="wide")
inyectar_estilos()

encabezado("Mis listas", "list_alt")
st.caption("Guarda tus listas de la compra habituales y cárgalas en la cesta cuando las necesites.")

inicializar_base_datos(_DB_PATH)
db = DatabaseManager(_DB_PATH)


# ── Etiquetas predefinidas ────────────────────────────────────────────
_ETIQUETAS = [
    ("Compra semanal",  "calendar_today"),
    ("Compra mensual",  "date_range"),
    ("Barbacoa",        "outdoor_grill"),
    ("Cumpleaños",      "cake"),
    ("Bebé",            "child_care"),
    ("Dieta",           "monitor_weight"),
    ("Otra",            "label"),
]
_NOMBRES_ETIQUETAS = [e[0] for e in _ETIQUETAS]
_ICONOS_ETIQUETAS  = {e[0]: e[1] for e in _ETIQUETAS}


def _icono_etiqueta(etiqueta):
    return _ICONOS_ETIQUETAS.get(etiqueta, "label")


def _badge_etiqueta(etiqueta):
    if not etiqueta:
        return ""
    icono = _icono_etiqueta(etiqueta)
    return (
        f'<span class="badge neutral" style="font-size:11px">'
        f'<span class="material-icons-outlined" style="font-size:13px">'
        f'{icono}</span>{etiqueta}</span>'
    )


# ═══════════════════════════════════════════════════════════════════════
# SECCIÓN A: CREAR NUEVA LISTA
# ═══════════════════════════════════════════════════════════════════════
encabezado("Crear nueva lista", "add_circle_outline", nivel=3)

with st.form("form_crear_lista", clear_on_submit=True):
    col_nombre, col_etiqueta = st.columns([2, 1])
    with col_nombre:
        nuevo_nombre = st.text_input(
            "Nombre de la lista *",
            placeholder="Ej: Compra del lunes, Cena barbacoa...")
    with col_etiqueta:
        nueva_etiqueta = st.selectbox("Etiqueta", _NOMBRES_ETIQUETAS)
    nuevas_notas = st.text_area(
        "Notas (opcional)",
        placeholder="Ej: recordar comprar sin gluten...",
        height=68)
    crear_ok = st.form_submit_button("Crear lista", type="primary")

if crear_ok:
    if not nuevo_nombre.strip():
        st.error("El nombre de la lista no puede estar vacío.")
    else:
        try:
            lista_id = db.crear_lista(
                nuevo_nombre.strip(), nueva_etiqueta, nuevas_notas.strip())
            st.success(f"Lista '{nuevo_nombre.strip()}' creada correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al crear la lista: {e}")


# ═══════════════════════════════════════════════════════════════════════
# SECCIÓN B: MIS LISTAS
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
encabezado("Mis listas", "folder_open", nivel=3)

df_listas = db.obtener_listas()

if df_listas.empty:
    estado_vacio(
        "list_alt",
        "Aún no tienes listas",
        "Crea tu primera lista de la compra arriba.")
else:
    # Resumen global
    total_listas = len(df_listas)
    total_productos = int(df_listas['num_productos'].sum()) if 'num_productos' in df_listas.columns else 0
    fila_metricas([
        ("list_alt",    str(total_listas),    "Listas"),
        ("shopping_bag", str(total_productos), "Productos guardados"),
    ])

    for _, lista in df_listas.iterrows():
        lista_id    = int(lista['id'])
        nombre      = lista.get('nombre', '')
        etiqueta    = lista.get('etiqueta', '')
        notas       = lista.get('notas', '')
        num_prods   = int(lista.get('num_productos', 0))
        coste_total = float(lista.get('coste_total', 0))
        fecha_act   = str(lista.get('fecha_actualizacion', ''))[:10]

        # ── Cabecera de la tarjeta ──
        badge_et = _badge_etiqueta(etiqueta)
        st.markdown(
            f'<div style="background:#F5F7FA;border:1px solid #E0E4E8;'
            f'border-radius:12px;padding:16px 20px;margin-bottom:8px">'
            f'<div style="display:flex;align-items:center;'
            f'justify-content:space-between;flex-wrap:wrap;gap:8px">'
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<span class="material-icons-outlined" '
            f'style="font-size:22px;color:#5A6C7D">list_alt</span>'
            f'<span style="font-size:16px;font-weight:600;'
            f'color:#1A1A1A">{nombre}</span>'
            f'{badge_et}</div>'
            f'<div style="font-size:12px;color:#5A6C7D">'
            f'{num_prods} productos · {coste_total:.2f} € · '
            f'actualizada {fecha_act}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True)

        # ── Botones de acción ──
        col_ver, col_cesta, col_dup, col_del = st.columns(4)

        with col_ver:
            ver = st.toggle(
                "Ver / Editar",
                key=f"ver_{lista_id}",
                value=st.session_state.get(f"expandir_{lista_id}", False))
            st.session_state[f"expandir_{lista_id}"] = ver

        with col_cesta:
            if st.button("Cargar en cesta",
                          key=f"cesta_{lista_id}",
                          use_container_width=True):
                cesta = db.cargar_lista_en_cesta(lista_id)
                if cesta:
                    st.session_state['cesta'] = cesta
                    st.success(
                        f"{len(cesta)} productos cargados en la cesta.")
                    st.switch_page("pages/4_Cesta.py")
                else:
                    st.warning("La lista está vacía.")

        with col_dup:
            if st.button("Duplicar",
                          key=f"dup_{lista_id}",
                          use_container_width=True):
                try:
                    nuevo_id = db.duplicar_lista(
                        lista_id, f"{nombre} (copia)")
                    st.success(f"Lista duplicada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al duplicar: {e}")

        with col_del:
            if st.button("Eliminar",
                          key=f"del_{lista_id}",
                          use_container_width=True,
                          type="secondary"):
                st.session_state[f"confirmar_del_{lista_id}"] = True
                st.rerun()

        # Confirmación de borrado
        if st.session_state.get(f"confirmar_del_{lista_id}", False):
            st.warning(f"¿Eliminar '{nombre}' y todos sus productos?")
            col_si, col_no = st.columns(2)
            with col_si:
                if st.button("Sí, eliminar",
                              key=f"si_del_{lista_id}",
                              type="primary",
                              use_container_width=True):
                    db.eliminar_lista(lista_id)
                    st.session_state.pop(f"confirmar_del_{lista_id}", None)
                    st.success("Lista eliminada.")
                    st.rerun()
            with col_no:
                if st.button("Cancelar",
                              key=f"no_del_{lista_id}",
                              use_container_width=True):
                    st.session_state.pop(f"confirmar_del_{lista_id}", None)
                    st.rerun()

        # ── Panel Ver / Editar ──
        if st.session_state.get(f"expandir_{lista_id}", False):
            with st.container():
                st.markdown(
                    '<hr style="border:none;border-top:1px solid #E0E4E8;'
                    'margin:4px 0 16px 0">',
                    unsafe_allow_html=True)

                # ── Renombrar lista ──
                with st.expander("Editar nombre / etiqueta / notas", expanded=False):
                    with st.form(f"form_editar_{lista_id}"):
                        col_n, col_e = st.columns([2, 1])
                        with col_n:
                            nuevo_n = st.text_input(
                                "Nombre", value=nombre,
                                key=f"edit_nombre_{lista_id}")
                        with col_e:
                            idx_et = (_NOMBRES_ETIQUETAS.index(etiqueta)
                                      if etiqueta in _NOMBRES_ETIQUETAS else 0)
                            nueva_et = st.selectbox(
                                "Etiqueta", _NOMBRES_ETIQUETAS,
                                index=idx_et,
                                key=f"edit_etiqueta_{lista_id}")
                        nuevas_n = st.text_area(
                            "Notas", value=notas, height=60,
                            key=f"edit_notas_{lista_id}")
                        if st.form_submit_button("Guardar cambios"):
                            try:
                                db.renombrar_lista(
                                    lista_id, nuevo_n.strip(),
                                    nueva_et, nuevas_n.strip())
                                st.success("Lista actualizada.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

                # ── Tabla de productos ──
                df_detalle = db.obtener_lista_detalle(lista_id)

                if df_detalle.empty:
                    estado_vacio(
                        "shopping_bag",
                        "Esta lista no tiene productos",
                        "Añade productos usando el buscador de abajo.")
                else:
                    encabezado(
                        f"Productos ({len(df_detalle)})",
                        "inventory_2", nivel=3)

                    for _, prod in df_detalle.iterrows():
                        prod_id   = int(prod['producto_id'])
                        p_nombre  = prod.get('nombre', '')
                        p_super   = prod.get('supermercado', '')
                        p_precio  = float(prod.get('precio', 0) or 0)
                        p_cant    = int(prod.get('cantidad', 1))
                        p_fmt     = prod.get('formato_normalizado', '')
                        p_img     = prod.get('url_imagen', '')
                        color     = COLORES_SUPERMERCADO.get(p_super, '#95A5A6')
                        _has_img  = isinstance(p_img, str) and p_img.startswith('http')

                        _card_html = (
                            f'<div class="product-card" '
                            f'style="margin-bottom:4px;padding:10px 14px">'
                            f'<div class="product-super" '
                            f'style="background:{color}"></div>'
                            f'<div class="product-info">'
                            f'<div class="product-name">{p_nombre}</div>'
                            f'<div class="product-meta">'
                            f'{p_super}'
                            f'{"  ·  " + p_fmt if p_fmt else ""}</div>'
                            f'</div>'
                            f'<div style="text-align:right">'
                            f'<div class="product-price">'
                            f'{p_precio:.2f} €</div>'
                            f'<div class="product-unit-price">'
                            f'x{p_cant}  =  '
                            f'{p_precio * p_cant:.2f} €</div>'
                            f'</div></div>'
                        )

                        if _has_img:
                            col_img, col_card, col_cant_ed, col_quitar = st.columns(
                                [1, 4, 1, 1])
                            with col_img:
                                try:
                                    st.image(p_img, width=56)
                                except Exception:
                                    pass
                        else:
                            col_card, col_cant_ed, col_quitar = st.columns(
                                [5, 1, 1])

                        with col_card:
                            st.markdown(_card_html, unsafe_allow_html=True)

                        with col_cant_ed:
                            nueva_cant = st.number_input(
                                "Cant.",
                                min_value=1, max_value=99,
                                value=p_cant,
                                key=f"cant_{lista_id}_{prod_id}",
                                label_visibility="collapsed")
                            if nueva_cant != p_cant:
                                db.actualizar_cantidad_lista(
                                    lista_id, prod_id, nueva_cant)
                                st.rerun()

                        with col_quitar:
                            if st.button(
                                "Quitar",
                                key=f"quitar_{lista_id}_{prod_id}",
                                use_container_width=True
                            ):
                                db.quitar_producto_de_lista(
                                    lista_id, prod_id)
                                st.rerun()

                    # Desglose por supermercado
                    st.markdown("")
                    encabezado("Desglose por supermercado",
                               "storefront", nivel=3)
                    por_super = {}
                    for _, prod in df_detalle.iterrows():
                        s = prod.get('supermercado', '')
                        precio = float(prod.get('precio', 0) or 0)
                        cant   = int(prod.get('cantidad', 1))
                        if s not in por_super:
                            por_super[s] = {'productos': 0, 'subtotal': 0.0}
                        por_super[s]['productos'] += cant
                        por_super[s]['subtotal']  += precio * cant

                    datos_desglose = [
                        {
                            'Supermercado': s,
                            'Unidades': v['productos'],
                            'Subtotal': f"{v['subtotal']:.2f} €",
                        }
                        for s, v in sorted(por_super.items())
                    ]
                    st.dataframe(
                        pd.DataFrame(datos_desglose),
                        use_container_width=True,
                        hide_index=True)

                # ── Añadir productos ──
                st.markdown("")
                encabezado("Añadir productos", "add_shopping_cart", nivel=3)

                col_busq, col_super_filtro = st.columns([3, 1])
                with col_busq:
                    texto_busq = st.text_input(
                        "Buscar producto:",
                        placeholder="Ej: leche, arroz...",
                        key=f"busq_{lista_id}")
                with col_super_filtro:
                    df_todos = db.obtener_productos_con_precio_actual()
                    supers_disp = (
                        ['Todos'] +
                        sorted(df_todos['supermercado'].unique().tolist())
                        if not df_todos.empty else ['Todos'])
                    filtro_super_lista = st.selectbox(
                        "Supermercado:", supers_disp,
                        key=f"super_{lista_id}")

                if texto_busq:
                    super_param = (None if filtro_super_lista == 'Todos'
                                   else filtro_super_lista)
                    df_busq = db.buscar_productos(
                        nombre=texto_busq,
                        supermercado=super_param,
                        limite=80)

                    if not df_busq.empty:
                        if 'prioridad' in df_busq.columns:
                            df_p1 = df_busq[df_busq['prioridad'] == 1]
                            if not df_p1.empty:
                                df_busq = df_p1

                        opciones_busq = {
                            (f"{r['nombre']} ({r['supermercado']}) "
                             f"— {r.get('precio', '?')} €"): int(r['id'])
                            for _, r in df_busq.iterrows()
                        }
                        col_sel, col_cant_add, col_btn_add = st.columns(
                            [4, 1, 1])
                        with col_sel:
                            sel_prod = st.selectbox(
                                f"Resultados ({len(df_busq)}):",
                                list(opciones_busq.keys()),
                                key=f"sel_{lista_id}")
                        with col_cant_add:
                            cant_add = st.number_input(
                                "Cant.", min_value=1, max_value=99,
                                value=1,
                                key=f"cant_add_{lista_id}",
                                label_visibility="collapsed")
                        with col_btn_add:
                            if st.button(
                                "Añadir",
                                key=f"btn_add_{lista_id}",
                                type="primary",
                                use_container_width=True
                            ):
                                ok = db.añadir_producto_a_lista(
                                    lista_id,
                                    opciones_busq[sel_prod],
                                    cant_add)
                                if ok:
                                    st.success("Producto añadido.")
                                    st.rerun()
                                else:
                                    st.error("No se pudo añadir el producto.")
                    else:
                        estado_vacio(
                            "search_off",
                            f"No se encontraron productos con '{texto_busq}'",
                            "Prueba con otro término.")


# ═══════════════════════════════════════════════════════════════════════
# SECCIÓN C: EXPORTAR LISTA
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
encabezado("Exportar lista", "file_download", nivel=3)

if df_listas.empty:
    estado_vacio(
        "file_download",
        "Nada que exportar",
        "Primero crea una lista y añade productos.")
else:
    opciones_export = {
        f"{row['nombre']} ({int(row.get('num_productos', 0))} prod.)": int(row['id'])
        for _, row in df_listas.iterrows()
        if int(row.get('num_productos', 0)) > 0
    }

    if not opciones_export:
        st.info("Tus listas están vacías. Añade productos para poder exportar.")
    else:
        lista_sel_nombre = st.selectbox(
            "Selecciona la lista a exportar:",
            list(opciones_export.keys()),
            key="export_lista_sel")
        lista_sel_id = opciones_export[lista_sel_nombre]

        cesta_export = db.cargar_lista_en_cesta(lista_sel_id)

        if cesta_export:
            col_pdf, col_email = st.columns(2)

            with col_pdf:
                nombre_pdf = (
                    f"lista_{lista_sel_nombre.split(' (')[0]}_"
                    f"{datetime.now().strftime('%Y%m%d')}.pdf")
                try:
                    pdf_bytes = generar_pdf_cesta(cesta_export)
                    st.download_button(
                        label="Descargar PDF",
                        data=pdf_bytes,
                        file_name=nombre_pdf,
                        mime="application/pdf",
                        key="export_pdf_btn",
                        use_container_width=True)
                except Exception as e:
                    st.error(f"Error al generar PDF: {e}")

            with col_email:
                enlaces = generar_enlaces_email(cesta_export)
                st.markdown(
                    f'<div style="display:flex;gap:8px">'
                    f'<a href="{enlaces["gmail"]}" target="_blank" '
                    f'rel="noopener noreferrer" '
                    f'style="flex:1;text-align:center;padding:8px;'
                    f'border:1px solid #E0E4E8;border-radius:8px;'
                    f'text-decoration:none;font-size:13px;'
                    f'color:#1565C0;background:#fff">'
                    f'Gmail</a>'
                    f'<a href="{enlaces["outlook"]}" target="_blank" '
                    f'rel="noopener noreferrer" '
                    f'style="flex:1;text-align:center;padding:8px;'
                    f'border:1px solid #E0E4E8;border-radius:8px;'
                    f'text-decoration:none;font-size:13px;'
                    f'color:#1565C0;background:#fff">'
                    f'Outlook</a>'
                    f'<a href="{enlaces["yahoo"]}" target="_blank" '
                    f'rel="noopener noreferrer" '
                    f'style="flex:1;text-align:center;padding:8px;'
                    f'border:1px solid #E0E4E8;border-radius:8px;'
                    f'text-decoration:none;font-size:13px;'
                    f'color:#1565C0;background:#fff">'
                    f'Yahoo</a>'
                    f'</div>',
                    unsafe_allow_html=True)
                st.caption(
                    "Los webmail no permiten adjuntar PDF automáticamente. "
                    "Descarga el PDF y adjúntalo manualmente.")
