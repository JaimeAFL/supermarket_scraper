# -*- coding: utf-8 -*-
"""Módulo de exportación de la cesta de la compra.

Genera PDF con la lista agrupada por supermercado y crea
enlaces mailto: para que el usuario se envíe la lista desde
su propio correo (sin necesidad de servidor SMTP).
"""

import os
import tempfile
import urllib.request as _urllib
from datetime import datetime
from urllib.parse import quote

from fpdf import FPDF


# ═══════════════════════════════════════════════════════════════════════
# GENERACIÓN DE PDF
# ═══════════════════════════════════════════════════════════════════════

_DEJAVU = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
_DEJAVU_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_DEJAVU_I = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'

# ── Dimensiones imagen en PDF ──────────────────────────────────────────
_IMG_W = 12   # mm ancho miniatura
_IMG_H = 12   # mm alto miniatura
_IMG_PAD = 3  # mm espacio entre imagen y texto
_ROW_H = 15   # mm alto de fila con imagen (imagen 12 + 1.5 arriba y abajo)


def _fetch_img_temp(url):
    """Descarga una imagen desde URL a fichero temporal. Devuelve ruta o None."""
    if not url or not url.startswith('http'):
        return None
    try:
        req = _urllib.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with _urllib.urlopen(req, timeout=4) as resp:
            data = resp.read()
        ext = '.png' if url.lower().endswith('.png') else '.jpg'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
            return f.name
    except Exception:
        return None


def _cleanup(paths):
    for p in paths:
        try:
            os.unlink(p)
        except Exception:
            pass


def generar_pdf_cesta(cesta):
    """Genera un PDF con la lista de la compra agrupada por supermercado.

    Los ítems pueden incluir 'url_imagen' para mostrar una miniatura
    del producto en la columna izquierda.

    Returns:
        bytes: contenido del PDF listo para st.download_button
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    if os.path.exists(_DEJAVU):
        pdf.add_font('DejaVu', '', _DEJAVU)
        pdf.add_font('DejaVu', 'B', _DEJAVU_B)
        pdf.add_font('DejaVu', 'I', _DEJAVU_I)
        font, eur = 'DejaVu', '\u20ac'
    else:
        font, eur = 'Helvetica', 'EUR'

    pdf.set_font(font, 'B', 20)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 12, 'Lista de la compra', ln=True)

    pdf.set_font(font, '', 10)
    pdf.set_text_color(107, 114, 128)
    fecha = datetime.now().strftime('%d/%m/%Y a las %H:%M')
    pdf.cell(0, 6, f'Generada el {fecha}', ln=True)
    pdf.ln(8)

    por_super = {}
    for item in cesta:
        s = item.get('supermercado', 'Desconocido')
        por_super.setdefault(s, []).append(item)

    total_general = 0
    total_items = 0
    _tmp_imgs = []

    for supermercado, items in por_super.items():
        subtotal = sum(
            i.get('precio', 0) * i.get('cantidad', 1) for i in items)
        total_general += subtotal
        n_items = sum(i.get('cantidad', 1) for i in items)
        total_items += n_items

        pdf.set_text_color(31, 41, 55)
        pdf.set_font(font, 'B', 13)
        pdf.cell(0, 9,
                 f'{supermercado}  ({len(items)} prod.  |  '
                 f'{subtotal:.2f} {eur})',
                 ln=True)

        pdf.set_draw_color(200, 200, 200)
        y_line = pdf.get_y()
        pdf.line(pdf.get_x(), y_line, pdf.get_x() + 170, y_line)
        pdf.ln(3)

        for item in items:
            precio = item.get('precio', 0)
            cantidad = item.get('cantidad', 1)
            sub = precio * cantidad
            formato = item.get('formato_normalizado', '')
            fmt_txt = f'  ({formato})' if formato else ''

            nombre_txt = item.get('nombre', '')
            if len(nombre_txt) > 46:
                nombre_txt = nombre_txt[:43] + '...'

            linea = f'[ ]  {nombre_txt}{fmt_txt}'
            precio_txt = f'x{cantidad}    {sub:.2f} {eur}'

            # Salto de página manual antes de dibujar imagen + texto
            if pdf.get_y() + _ROW_H > pdf.h - pdf.b_margin:
                pdf.add_page()

            y0 = pdf.get_y()
            x0 = pdf.get_x()

            # ── Imagen miniatura ──────────────────────────────────
            url_img = item.get('url_imagen', '')
            img_path = _fetch_img_temp(url_img)
            if img_path:
                _tmp_imgs.append(img_path)
                try:
                    pdf.image(img_path,
                              x=x0, y=y0 + (_ROW_H - _IMG_H) / 2,
                              w=_IMG_W, h=_IMG_H)
                except Exception:
                    pass

            # ── Texto (siempre con offset de imagen) ──────────────
            txt_x = x0 + _IMG_W + _IMG_PAD
            txt_y = y0 + (_ROW_H - 7) / 2  # centra texto 7mm en fila

            pdf.set_xy(txt_x, txt_y)
            pdf.set_font(font, '', 11)
            pdf.set_text_color(55, 65, 81)

            # ancho disponible para nombre = 190 - offset_imagen - col_precio
            name_w = 190 - (_IMG_W + _IMG_PAD) - 52
            pdf.cell(name_w, 7, linea, ln=False)
            pdf.cell(52, 7, precio_txt, ln=False, align='R')

            pdf.set_y(y0 + _ROW_H)

        pdf.ln(3)

    _cleanup(_tmp_imgs)

    pdf.set_draw_color(60, 60, 60)
    y_line = pdf.get_y()
    pdf.line(pdf.get_x(), y_line, pdf.get_x() + 170, y_line)
    pdf.ln(5)

    pdf.set_font(font, 'B', 14)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 10,
             f'TOTAL:  {total_items} unidades  |  '
             f'{total_general:.2f} {eur}',
             ln=True)

    ahorro = _calcular_ahorro_posible(cesta)
    if ahorro > 0.01:
        pdf.set_font(font, 'I', 10)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 8,
                 f'Ahorro posible: {ahorro:.2f} {eur} '
                 f'(intercambiando por alternativas)',
                 ln=True)

    pdf.ln(12)
    pdf.set_font(font, '', 8)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 5, 'Supermarket Price Tracker', ln=True)

    return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════════════
# RESUMEN EN TEXTO PLANO
# ═══════════════════════════════════════════════════════════════════════

def generar_resumen_texto(cesta):
    """Genera un resumen en texto plano de la cesta."""
    if not cesta:
        return "La cesta esta vacia."

    lineas = []
    por_super = {}
    for item in cesta:
        s = item.get('supermercado', 'Desconocido')
        if s not in por_super:
            por_super[s] = []
        por_super[s].append(item)

    total = 0
    for supermercado, items in por_super.items():
        subtotal = sum(
            i.get('precio', 0) * i.get('cantidad', 1) for i in items)
        total += subtotal
        lineas.append(
            f"\n{supermercado} ({len(items)} prod. - "
            f"{subtotal:.2f} EUR)")
        for item in items:
            sub = item.get('precio', 0) * item.get('cantidad', 1)
            lineas.append(
                f"  - {item.get('nombre', '')} "
                f"x{item.get('cantidad', 1)}  {sub:.2f} EUR")

    n_total = sum(i.get('cantidad', 1) for i in cesta)
    lineas.append(f"\nTOTAL: {n_total} unidades - {total:.2f} EUR")

    ahorro = _calcular_ahorro_posible(cesta)
    if ahorro > 0.01:
        lineas.append(f"Ahorro posible: {ahorro:.2f} EUR")

    return "\n".join(lineas)


# ═══════════════════════════════════════════════════════════════════════
# ENLACES DE EMAIL WEB (sin servidor, sin credenciales)
# ═══════════════════════════════════════════════════════════════════════

def generar_enlaces_email(cesta):
    """Genera enlaces para abrir el compositor de email en navegador.

    Devuelve un dict con enlaces directos a Gmail, Outlook.com y Yahoo
    que abren la ventana de redacción con asunto y cuerpo ya rellenos.

    No necesita SMTP, ni servidor, ni credenciales, ni app de escritorio.

    Nota: los enlaces webmail rellenan asunto/cuerpo, pero NO pueden adjuntar
    ficheros automáticamente por restricciones de seguridad de los proveedores.

    Returns:
        dict con claves 'gmail', 'outlook', 'yahoo', cada una con la URL
    """
    fecha = datetime.now().strftime('%d/%m/%Y')
    asunto = f"Mi lista de la compra - {fecha}"
    resumen = generar_resumen_texto(cesta)
    cuerpo = (
        "Lista de la compra generada con Supermarket Price Tracker:\n"
        f"{resumen}\n\n"
        "---\n"
        "Tip: descarga el PDF desde la app y adjúntalo manualmente en el "
        "correo (los enlaces web no permiten adjuntar archivos automáticamente)."
    )

    asunto_enc = quote(asunto)
    cuerpo_enc = quote(cuerpo)
    # Para Outlook web se necesita codificación con + en vez de %20
    cuerpo_enc_outlook = quote(cuerpo, safe='')

    return {
        # Gmail: https://mail.google.com/mail/?view=cm&su=...&body=...
        'gmail': (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&su={asunto_enc}&body={cuerpo_enc}"
        ),
        # Outlook.com: https://outlook.live.com/mail/0/deeplink/compose?...
        'outlook': (
            f"https://outlook.live.com/mail/0/deeplink/compose"
            f"?subject={asunto_enc}&body={cuerpo_enc_outlook}"
        ),
        # Yahoo: https://compose.mail.yahoo.com/?subject=...&body=...
        'yahoo': (
            f"https://compose.mail.yahoo.com/"
            f"?subject={asunto_enc}&body={cuerpo_enc}"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════

def _calcular_ahorro_posible(cesta):
    """Calcula el ahorro total posible si se intercambian alternativas."""
    ahorro = 0
    for item in cesta:
        alt_precio = item.get('alternativa_precio')
        if (alt_precio is not None
                and alt_precio < item.get('precio', 0)):
            diff = item['precio'] - alt_precio
            ahorro += diff * item.get('cantidad', 1)
    return ahorro
