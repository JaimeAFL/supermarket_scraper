# -*- coding: utf-8 -*-
"""Modulo de exportacion de la cesta de la compra.

Genera PDF con la lista agrupada por supermercado y permite
enviar por email como adjunto.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

from fpdf import FPDF


# ═══════════════════════════════════════════════════════════════════════
# GENERACION DE PDF
# ═══════════════════════════════════════════════════════════════════════

# Rutas a fuentes Unicode (DejaVu, comun en Linux)
_DEJAVU = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
_DEJAVU_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_DEJAVU_I = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'


def generar_pdf_cesta(cesta):
    """Genera un PDF con la lista de la compra agrupada por supermercado.

    Args:
        cesta: lista de dicts con la estructura de session_state['cesta']

    Returns:
        bytes: contenido del PDF listo para st.download_button
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Cargar fuente Unicode si esta disponible (soporte para €)
    if os.path.exists(_DEJAVU):
        pdf.add_font('DejaVu', '', _DEJAVU, uni=True)
        pdf.add_font('DejaVu', 'B', _DEJAVU_B, uni=True)
        pdf.add_font('DejaVu', 'I', _DEJAVU_I, uni=True)
        font = 'DejaVu'
        eur = '\u20ac'  # €
    else:
        font = 'Helvetica'
        eur = 'EUR'

    # ── Titulo ────────────────────────────────────────────────────
    pdf.set_font(font, 'B', 20)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 12, 'Lista de la compra', ln=True)

    pdf.set_font(font, '', 10)
    pdf.set_text_color(107, 114, 128)
    fecha = datetime.now().strftime('%d/%m/%Y a las %H:%M')
    pdf.cell(0, 6, f'Generada el {fecha}', ln=True)
    pdf.ln(8)

    # ── Agrupar por supermercado ──────────────────────────────────
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

        # Cabecera del supermercado
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

        # Productos
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

    # ── Total general ─────────────────────────────────────────────
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

    # ── Nota de ahorro ────────────────────────────────────────────
    ahorro = _calcular_ahorro_posible(cesta)
    if ahorro > 0.01:
        pdf.set_font(font, 'I', 10)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 8,
                 f'Ahorro posible: {ahorro:.2f} {eur} '
                 f'(intercambiando por alternativas)',
                 ln=True)

    # ── Footer ────────────────────────────────────────────────────
    pdf.ln(12)
    pdf.set_font(font, '', 8)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 5, 'Supermarket Price Tracker', ln=True)

    return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════════════
# RESUMEN EN TEXTO PLANO (para cuerpo de email)
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
            f"\n{supermercado} ({len(items)} prod. · "
            f"{subtotal:.2f} EUR)")
        for item in items:
            sub = item.get('precio', 0) * item.get('cantidad', 1)
            lineas.append(
                f"  - {item.get('nombre', '')} "
                f"x{item.get('cantidad', 1)}  {sub:.2f} EUR")

    n_total = sum(i.get('cantidad', 1) for i in cesta)
    lineas.append(f"\nTOTAL: {n_total} unidades · {total:.2f} EUR")

    ahorro = _calcular_ahorro_posible(cesta)
    if ahorro > 0.01:
        lineas.append(f"Ahorro posible: {ahorro:.2f} EUR")

    return "\n".join(lineas)


# ═══════════════════════════════════════════════════════════════════════
# ENVIO POR EMAIL
# ═══════════════════════════════════════════════════════════════════════

def smtp_configurado():
    """Comprueba si hay credenciales SMTP configuradas."""
    return bool(
        os.environ.get('SMTP_USER')
        and os.environ.get('SMTP_PASSWORD')
    )


def enviar_cesta_por_email(destinatario, pdf_bytes, resumen_texto):
    """Envia la cesta como PDF adjunto por email.

    Raises:
        ValueError: si no hay SMTP configurado
    """
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASSWORD')

    if not smtp_user or not smtp_pass:
        raise ValueError(
            "Credenciales SMTP no configuradas. "
            "Anade SMTP_USER y SMTP_PASSWORD al archivo .env")

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = destinatario
    msg['Subject'] = (
        f"Tu lista de la compra - "
        f"{datetime.now().strftime('%d/%m/%Y')}")

    cuerpo = (
        "Hola,\n\n"
        "Aqui tienes tu lista de la compra generada desde "
        "Supermarket Price Tracker.\n"
        f"{resumen_texto}\n\n"
        "El PDF adjunto incluye el detalle completo agrupado "
        "por supermercado, listo para imprimir.\n\n"
        "---\n"
        "Generado automaticamente por Supermarket Price Tracker"
    )
    msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

    nombre_archivo = (
        f"lista_compra_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    adjunto = MIMEApplication(pdf_bytes, _subtype='pdf')
    adjunto.add_header(
        'Content-Disposition', 'attachment',
        filename=nombre_archivo)
    msg.attach(adjunto)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


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
