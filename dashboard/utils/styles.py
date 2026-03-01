# -*- coding: utf-8 -*-
"""Sistema de diseño unificado para el dashboard.

Centraliza TODOS los estilos CSS, Material Icons y tokens de diseño.
Cada página llama a inyectar_estilos() una sola vez al inicio.
"""

import streamlit as st

# ── Design Tokens ─────────────────────────────────────────────────────
# Colores de supermercados (fijos en todo el proyecto)
COLORES_SUPERMERCADO = {
    'Mercadona': '#2ECC71',
    'Carrefour': '#3498DB',
    'Dia':       '#E74C3C',
    'Alcampo':   '#F39C12',
    'Eroski':    '#9B59B6',
}

# Tokens de color del sistema
COLOR_PRIMARY = '#1565C0'       # Azul Material 800
COLOR_ON_PRIMARY = '#FFFFFF'
COLOR_SURFACE = '#FFFFFF'
COLOR_SURFACE_VARIANT = '#F5F7FA'
COLOR_ON_SURFACE = '#1A1A1A'
COLOR_ON_SURFACE_VARIANT = '#5A6C7D'
COLOR_OUTLINE = '#E0E4E8'
COLOR_OUTLINE_VARIANT = '#C4CDD5'
COLOR_SUCCESS = '#2E7D32'
COLOR_ERROR = '#C62828'
COLOR_WARNING = '#F57F17'
COLOR_NEUTRAL = '#78909C'

# Tokens de tipografía
FONT_FAMILY = "'Inter', 'Segoe UI', Roboto, sans-serif"

# Tokens de elevación y espaciado
RADIUS_SM = '8px'
RADIUS_MD = '12px'
RADIUS_LG = '16px'
SPACING_XS = '4px'
SPACING_SM = '8px'
SPACING_MD = '16px'
SPACING_LG = '24px'
SPACING_XL = '32px'


def inyectar_estilos():
    """Inyecta TODOS los estilos globales. Llamar una vez por página."""
    st.markdown(_CSS_GLOBAL, unsafe_allow_html=True)


# ── CSS global (única fuente de verdad) ───────────────────────────────
_CSS_GLOBAL = """
<!-- Material Icons -->
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Outlined"
      rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
      rel="stylesheet">

<style>
/* ═══════════════════════════════════════════════════════════════════
   DESIGN TOKENS (variables CSS)
   ═══════════════════════════════════════════════════════════════════ */
:root {
    --color-primary: #1565C0;
    --color-on-primary: #FFFFFF;
    --color-surface: #FFFFFF;
    --color-surface-variant: #F5F7FA;
    --color-on-surface: #1A1A1A;
    --color-on-surface-variant: #5A6C7D;
    --color-outline: #E0E4E8;
    --color-outline-variant: #C4CDD5;
    --color-success: #2E7D32;
    --color-error: #C62828;
    --color-warning: #F57F17;
    --color-neutral: #78909C;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
    --shadow-md: 0 2px 8px rgba(0,0,0,0.10);
    --font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;

    /* Colores de supermercados */
    --color-mercadona: #2ECC71;
    --color-carrefour: #3498DB;
    --color-dia: #E74C3C;
    --color-alcampo: #F39C12;
    --color-eroski: #9B59B6;
}

/* ═══════════════════════════════════════════════════════════════════
   ENCABEZADOS CON ICONO (icon-header)
   ═══════════════════════════════════════════════════════════════════ */
.icon-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}
.icon-header .material-icons-outlined {
    font-size: 28px;
    color: var(--color-on-surface-variant);
}
.icon-header h2, .icon-header h3 {
    margin: 0;
    padding: 0;
    font-family: var(--font-family);
    color: var(--color-on-surface);
}

/* ═══════════════════════════════════════════════════════════════════
   TARJETAS DE MÉTRICAS (metric-card)
   ═══════════════════════════════════════════════════════════════════ */
.metric-row {
    display: flex;
    gap: 12px;
    margin: 16px 0 24px 0;
    flex-wrap: wrap;
}
.metric-card {
    flex: 1;
    min-width: 140px;
    background: var(--color-surface-variant);
    border: 1px solid var(--color-outline);
    border-radius: var(--radius-md);
    padding: 16px 20px;
    text-align: center;
    transition: box-shadow 0.2s ease;
}
.metric-card:hover {
    box-shadow: var(--shadow-md);
}
.metric-card .metric-icon {
    font-size: 22px;
    color: var(--color-on-surface-variant);
    margin-bottom: 4px;
}
.metric-card .metric-value {
    font-size: 26px;
    font-weight: 700;
    color: var(--color-on-surface);
    line-height: 1.2;
    font-family: var(--font-family);
}
.metric-card .metric-label {
    font-size: 12px;
    color: var(--color-on-surface-variant);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 2px;
    font-family: var(--font-family);
}

/* ═══════════════════════════════════════════════════════════════════
   TARJETAS DE INSIGHT (insight-card)
   Para comparador y favoritos: resúmenes de decisión
   ═══════════════════════════════════════════════════════════════════ */
.insight-row {
    display: flex;
    gap: 12px;
    margin: 12px 0 20px 0;
    flex-wrap: wrap;
}
.insight-card {
    flex: 1;
    min-width: 200px;
    background: var(--color-surface);
    border: 1px solid var(--color-outline);
    border-radius: var(--radius-md);
    padding: 16px 20px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    transition: box-shadow 0.2s ease;
}
.insight-card:hover {
    box-shadow: var(--shadow-md);
}
.insight-card .insight-icon {
    font-size: 28px;
    line-height: 1;
    flex-shrink: 0;
}
.insight-card .insight-icon.success { color: var(--color-success); }
.insight-card .insight-icon.error   { color: var(--color-error); }
.insight-card .insight-icon.warning { color: var(--color-warning); }
.insight-card .insight-icon.neutral { color: var(--color-neutral); }
.insight-card .insight-icon.primary { color: var(--color-primary); }
.insight-card .insight-body {
    flex: 1;
}
.insight-card .insight-title {
    font-size: 13px;
    color: var(--color-on-surface-variant);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin: 0 0 2px 0;
    font-family: var(--font-family);
}
.insight-card .insight-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--color-on-surface);
    line-height: 1.2;
    font-family: var(--font-family);
}
.insight-card .insight-detail {
    font-size: 12px;
    color: var(--color-on-surface-variant);
    margin-top: 2px;
}

/* Variante compacta para insight-card (favoritos) */
.insight-card.compact {
    padding: 12px 16px;
}
.insight-card.compact .insight-icon { font-size: 24px; }
.insight-card.compact .insight-value { font-size: 16px; }

/* ═══════════════════════════════════════════════════════════════════
   BADGES / CHIPS (para estados, etiquetas)
   ═══════════════════════════════════════════════════════════════════ */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    font-family: var(--font-family);
    line-height: 1.4;
    white-space: nowrap;
}
.badge .material-icons-outlined {
    font-size: 14px;
}
.badge.success {
    background: #E8F5E9;
    color: var(--color-success);
}
.badge.error {
    background: #FFEBEE;
    color: var(--color-error);
}
.badge.warning {
    background: #FFF8E1;
    color: var(--color-warning);
}
.badge.neutral {
    background: #ECEFF1;
    color: var(--color-neutral);
}
.badge.primary {
    background: #E3F2FD;
    color: var(--color-primary);
}

/* ═══════════════════════════════════════════════════════════════════
   PAGINACIÓN
   ═══════════════════════════════════════════════════════════════════ */
.pagination-info {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    font-size: 13px;
    color: var(--color-on-surface-variant);
    font-family: var(--font-family);
}
.pagination-info .page-range {
    font-weight: 600;
    color: var(--color-on-surface);
}

/* ═══════════════════════════════════════════════════════════════════
   ESTADOS UX: vacío, carga, error accionable
   ═══════════════════════════════════════════════════════════════════ */
.estado-vacio {
    text-align: center;
    padding: 48px 24px;
    color: var(--color-on-surface-variant);
}
.estado-vacio .material-icons-outlined {
    font-size: 48px;
    color: var(--color-outline-variant);
    margin-bottom: 12px;
    display: block;
}
.estado-vacio .estado-titulo {
    font-size: 16px;
    font-weight: 600;
    color: var(--color-on-surface);
    margin-bottom: 4px;
    font-family: var(--font-family);
}
.estado-vacio .estado-detalle {
    font-size: 14px;
    color: var(--color-on-surface-variant);
    font-family: var(--font-family);
}

/* ═══════════════════════════════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════════════════════════════ */
.sidebar-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 20px;
    font-weight: 600;
    color: var(--color-on-surface);
    font-family: var(--font-family);
}
.sidebar-title .material-icons-outlined {
    font-size: 24px;
    color: var(--color-on-surface-variant);
}

/* ═══════════════════════════════════════════════════════════════════
   TARJETA DE PRODUCTO (para favoritos y búsquedas)
   ═══════════════════════════════════════════════════════════════════ */
.product-card {
    background: var(--color-surface);
    border: 1px solid var(--color-outline);
    border-radius: var(--radius-md);
    padding: 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: box-shadow 0.2s ease;
}
.product-card:hover {
    box-shadow: var(--shadow-md);
}
.product-card .product-super {
    width: 8px;
    height: 48px;
    border-radius: 4px;
    flex-shrink: 0;
}
.product-card .product-info {
    flex: 1;
    min-width: 0;
}
.product-card .product-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-on-surface);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: var(--font-family);
}
.product-card .product-meta {
    font-size: 12px;
    color: var(--color-on-surface-variant);
    margin-top: 2px;
    font-family: var(--font-family);
}
.product-card .product-price {
    font-size: 18px;
    font-weight: 700;
    color: var(--color-on-surface);
    white-space: nowrap;
    font-family: var(--font-family);
}
.product-card .product-unit-price {
    font-size: 12px;
    color: var(--color-on-surface-variant);
    font-family: var(--font-family);
}

/* ═══════════════════════════════════════════════════════════════════
   UTILIDADES
   ═══════════════════════════════════════════════════════════════════ */
.text-success { color: var(--color-success) !important; }
.text-error   { color: var(--color-error) !important; }
.text-warning { color: var(--color-warning) !important; }
.text-neutral { color: var(--color-neutral) !important; }
.text-primary { color: var(--color-primary) !important; }
.text-muted   { color: var(--color-on-surface-variant) !important; }

.section-divider {
    border: none;
    border-top: 1px solid var(--color-outline);
    margin: 24px 0;
}
</style>
"""
