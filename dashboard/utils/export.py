# -*- coding: utf-8 -*-
"""Módulo de exportación de la cesta de la compra.

Genera PDF con la lista agrupada por supermercado y crea
enlaces mailto: para que el usuario se envíe la lista desde
su propio correo (sin necesidad de servidor SMTP).
"""

import os
from datetime import datetime
from urllib.parse import quote

from fpdf import FPDF


# ═══════════════════════════════════════════════════════════════════════
# GENERACIÓN DE PDF
# ═══════════════════════════════════════════════════════════════════════

_DEJAVU = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
_DEJAVU_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_DEJAVU_I = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'


def generar_pdf_cesta(cesta):
    """Genera un PDF con la lista de la compra agrupada por supermercado.

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
        if s not in por_super:
            por_super[s] = []
        por_super[s].append(item)

    total_general = 0
    total_items = 0

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

        pdf.set_font(font, '', 11)
        pdf.set_text_color(55, 65, 81)
        for item in items:
            precio = item.get('precio', 0)
            cantidad = item.get('cantidad', 1)
            sub = precio * cantidad
            formato = item.get('formato_normalizado', '')
            fmt_txt = f'  ({formato})' if formato else ''

            nombre_txt = item.get('nombre', '')
            if len(nombre_txt) > 50:
                nombre_txt = nombre_txt[:47] + '...'

            linea = f'[ ]  {nombre_txt}{fmt_txt}'
            precio_txt = f'x{cantidad}    {sub:.2f} {eur}'

            pdf.cell(130, 7, linea, ln=False)
            pdf.cell(0, 7, precio_txt, ln=True, align='R')

        pdf.ln(5)

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
# ENLACE MAILTO (reemplaza SMTP — sin servidor, sin credenciales)
# ═══════════════════════════════════════════════════════════════════════

def generar_mailto_link(cesta):
    """Genera un enlace mailto: con el resumen de la cesta.

    Al hacer clic, se abre el cliente de correo del usuario
    (Gmail, Outlook, Apple Mail, etc.) con el asunto y cuerpo
    ya rellenos. El usuario se lo envía a sí mismo.

    No necesita SMTP, ni servidor, ni credenciales.

    Returns:
        str: enlace mailto: listo para usar en <a href="...">
    """
    fecha = datetime.now().strftime('%d/%m/%Y')
    asunto = f"Mi lista de la compra - {fecha}"
    resumen = generar_resumen_texto(cesta)
    cuerpo = (
        "Lista de la compra generada con Supermarket Price Tracker:\n"
        f"{resumen}\n\n"
        "---\n"
        "Tip: descarga tambien el PDF desde la app para "
        "tener la lista con formato listo para imprimir."
    )

    # Codificar para URL
    asunto_enc = quote(asunto)
    cuerpo_enc = quote(cuerpo)

    return f"mailto:?subject={asunto_enc}&body={cuerpo_enc}"


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
