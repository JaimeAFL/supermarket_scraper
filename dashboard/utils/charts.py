# -*- coding: utf-8 -*-
"""Funciones de visualizacion con ApexCharts para el dashboard.

Todas las funciones devuelven HTML autocontenido para renderizar
con streamlit.components.v1.html().
"""

import json
import numpy as np
import pandas as pd
from string import Template

COLORES_SUPERMERCADO = {
    'Mercadona': '#2ECC71',
    'Carrefour': '#3498DB',
    'Dia':       '#E74C3C',
    'Alcampo':   '#F39C12',
    'Eroski':    '#9B59B6',
    'Consum':    '#E30613',
    'Condis':    '#CC0000',
}

_APEX_CDN = "https://cdn.jsdelivr.net/npm/apexcharts@3.49.0/dist/apexcharts.min.js"
_FONT_CDN = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
_FONT = "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _col_fecha(df):
    """Detecta la columna de fecha en un DataFrame."""
    for c in ('fecha_captura', 'fecha'):
        if c in df.columns:
            return c
    return None


def _base_css():
    """CSS compartido por todos los graficos."""
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        background: transparent;
        color: #1F2937;
    }
    .chart-wrapper {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 20px;
    }
    .chart-title {
        font-size: 15px;
        font-weight: 600;
        color: #1F2937;
        margin-bottom: 2px;
    }
    .chart-subtitle {
        font-size: 12px;
        color: #6B7280;
        margin-bottom: 12px;
    }
    .kpi-row {
        display: flex;
        gap: 12px;
        margin-top: 16px;
    }
    .kpi-card {
        flex: 1;
        background: #F7F9FC;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 18px;
        font-weight: 700;
        color: #1F2937;
        margin-top: 2px;
    }
    """


def _html_page(chart_id, options_js, extra_html="", extra_css=""):
    """Genera una pagina HTML completa con un grafico ApexCharts."""
    css = _base_css()
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="{_APEX_CDN}"></script>
<link href="{_FONT_CDN}" rel="stylesheet">
<style>{css}{extra_css}</style>
</head><body>
<div class="chart-wrapper">
<div id="{chart_id}"></div>
{extra_html}
</div>
<script>
var options = {options_js};
var chart = new ApexCharts(document.querySelector("#{chart_id}"), options);
chart.render();
</script>
</body></html>"""


def _html_vacio(mensaje="Sin datos disponibles"):
    """HTML de estado vacio cuando no hay datos."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link href="{_FONT_CDN}" rel="stylesheet">
<style>
body {{
    font-family: Inter, system-ui, sans-serif;
    display: flex; justify-content: center; align-items: center;
    height: 200px; color: #6B7280; font-size: 15px;
    background: transparent;
}}
</style></head><body>{mensaje}</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# BASE OPTIONS (ApexCharts config compartida)
# ═══════════════════════════════════════════════════════════════════════

_BASE_CHART_JS = Template("""{
    fontFamily: '$font',
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeinout', speed: 350 }
}""")

_BASE_GRID_JS = """{
    borderColor: '#EEF2F7',
    strokeDashArray: 4,
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } }
}"""


# ═══════════════════════════════════════════════════════════════════════
# 1) PRODUCTOS POR SUPERMERCADO (barras horizontales)
# ═══════════════════════════════════════════════════════════════════════

def apex_productos_por_supermercado_html(stats):
    """Grafico de barras horizontales: productos por supermercado."""
    datos = stats.get('productos_por_supermercado', {})
    if not datos:
        return _html_vacio("No hay productos registrados")

    datos_ord = dict(sorted(datos.items(), key=lambda x: x[1]))
    supers = list(datos_ord.keys())
    cantidades = list(datos_ord.values())
    colores = [COLORES_SUPERMERCADO.get(s, '#95A5A6') for s in supers]

    cats_json = json.dumps(supers)
    data_json = json.dumps(cantidades)
    colors_json = json.dumps(colores)

    t = Template("""{
        chart: {
            type: 'bar',
            height: 280,
            fontFamily: '$font',
            toolbar: { show: false },
            animations: { enabled: true, easing: 'easeinout', speed: 350 }
        },
        series: [{ name: 'Productos', data: $data }],
        plotOptions: {
            bar: {
                horizontal: true,
                borderRadius: 6,
                barHeight: '60%',
                distributed: true,
                dataLabels: { position: 'center' }
            }
        },
        colors: $colors,
        dataLabels: {
            enabled: true,
            formatter: function(val) { return val.toLocaleString(); },
            style: {
                fontSize: '13px',
                fontWeight: 600,
                colors: ['#FFFFFF']
            },
            dropShadow: { enabled: false }
        },
        xaxis: {
            categories: $categories,
            labels: {
                style: { fontSize: '12px', colors: '#6B7280' },
                formatter: function(val) { return val.toLocaleString(); }
            },
            axisBorder: { show: false },
            axisTicks: { show: false }
        },
        yaxis: {
            labels: {
                style: { fontSize: '13px', fontWeight: 500, colors: '#1F2937' }
            }
        },
        grid: $grid,
        tooltip: {
            theme: 'dark',
            y: { formatter: function(val) { return val.toLocaleString() + ' productos'; } }
        },
        legend: { show: false }
    }""")

    options_js = t.substitute(
        font=_FONT,
        data=data_json,
        categories=cats_json,
        colors=colors_json,
        grid=_BASE_GRID_JS,
    )

    title_html = '<div class="chart-title">Productos por supermercado</div>'
    return _html_page("chart-super", options_js, extra_html="",
                      extra_css="").replace(
        '<div id="chart-super"></div>',
        f'{title_html}<div id="chart-super"></div>')


# ═══════════════════════════════════════════════════════════════════════
# 2) DISTRIBUCION DE PRECIOS (histograma)
# ═══════════════════════════════════════════════════════════════════════

def apex_distribucion_precios_html(df, supermercado="", completa=False):
    """Histograma de distribucion de precios.

    Args:
        df: DataFrame con columna 'precio'
        supermercado: nombre del supermercado para color y titulo
        completa: False=vista 95%, True=todos los precios (log Y)
    """
    if df.empty or 'precio' not in df.columns:
        return _html_vacio("No hay datos de precios")

    color = COLORES_SUPERMERCADO.get(supermercado, '#2F80ED')
    precios = df['precio'].dropna()
    if precios.empty:
        return _html_vacio("No hay datos de precios")

    total = len(precios)

    if completa:
        precios_plot = precios
        max_val = int(np.ceil(precios.max()))
        # Bins adaptativos para vista completa
        if max_val <= 100:
            bin_width = 1
        elif max_val <= 250:
            bin_width = 2
        else:
            bin_width = 5
        titulo = f"{supermercado} — Todos los precios"
        subtitulo = f"{total:,} productos · escala logaritmica"
    else:
        p95 = float(np.percentile(precios, 95))
        precios_plot = precios[precios <= p95]
        max_val = int(np.ceil(p95))
        bin_width = 1
        titulo = f"{supermercado} — 95% de productos (hasta {max_val} €)"
        subtitulo = f"{len(precios_plot):,} de {total:,} productos"

    en_rango = len(precios_plot)
    mediana = float(np.median(precios_plot))
    media = float(np.mean(precios_plot))
    p25 = float(np.percentile(precios_plot, 25))
    p75 = float(np.percentile(precios_plot, 75))

    # Calcular bins
    bins = np.arange(0, max_val + bin_width, bin_width)
    counts, edges = np.histogram(precios_plot, bins=bins)

    # Categorias: "0", "1", "2", ... (inicio de cada bin)
    categories = [str(int(e)) for e in edges[:-1]]
    data = [int(x) for x in counts]

    # Para log scale: reemplazar 0 con null
    if completa:
        data_js = json.dumps([x if x > 0 else None for x in data])
    else:
        data_js = json.dumps(data)

    cats_json = json.dumps(categories)

    # Determinar intervalo de etiquetas en eje X
    label_interval = 5 if bin_width <= 2 else 10

    # Annotation positions (bin mas cercano)
    mediana_bin = str(int(round(mediana / bin_width) * bin_width))
    media_bin = str(int(round(media / bin_width) * bin_width))

    # Eje Y config
    if completa:
        yaxis_js = """{
            logarithmic: true,
            min: 1,
            title: { text: 'Productos (log)', style: { fontSize: '12px', color: '#6B7280' } },
            labels: { style: { fontSize: '11px', colors: '#6B7280' } }
        }"""
    else:
        yaxis_js = """{
            title: { text: 'Productos', style: { fontSize: '12px', color: '#6B7280' } },
            labels: { style: { fontSize: '11px', colors: '#6B7280' } }
        }"""

    t = Template("""{
        chart: {
            type: 'bar',
            height: $height,
            fontFamily: '$font',
            toolbar: { show: false },
            animations: { enabled: true, easing: 'easeinout', speed: 300 }
        },
        series: [{ name: '$supermercado', data: $data }],
        plotOptions: {
            bar: {
                borderRadius: 1,
                columnWidth: '95%'
            }
        },
        colors: ['$color'],
        fill: { opacity: 0.65 },
        dataLabels: { enabled: false },
        xaxis: {
            categories: $categories,
            title: {
                text: 'Precio (€)',
                style: { fontSize: '12px', color: '#6B7280', fontWeight: 500 }
            },
            labels: {
                rotate: 0,
                hideOverlappingLabels: true,
                style: { fontSize: '11px', colors: '#6B7280' },
                formatter: function(val) {
                    var n = parseInt(val);
                    return (n % $label_interval === 0) ? n : '';
                }
            },
            axisBorder: { color: '#E5E7EB' },
            axisTicks: { show: false },
            crosshairs: { show: false }
        },
        yaxis: $yaxis,
        grid: {
            borderColor: '#EEF2F7',
            strokeDashArray: 4,
            xaxis: { lines: { show: false } },
            yaxis: { lines: { show: true } }
        },
        tooltip: {
            theme: 'dark',
            custom: function(opts) {
                var count = opts.series[opts.seriesIndex][opts.dataPointIndex];
                var cat = opts.w.globals.labels[opts.dataPointIndex];
                var start = parseInt(cat);
                var end = start + $bin_width;
                if (count === null || count === undefined) count = 0;
                return '<div style="padding:8px 14px;font-size:13px;line-height:1.6">' +
                       '<div style="font-weight:600">' + start + ' – ' + end + ' €</div>' +
                       '<div style="opacity:0.8">' + count.toLocaleString() + ' productos</div></div>';
            }
        },
        annotations: {
            xaxis: [
                {
                    x: '$mediana_bin',
                    borderColor: '#1F2937',
                    strokeDashArray: 0,
                    label: {
                        text: 'Mediana',
                        orientation: 'vertical',
                        borderWidth: 0,
                        style: {
                            background: '#1F2937',
                            color: '#fff',
                            fontSize: '11px',
                            fontWeight: 600,
                            padding: { left: 6, right: 6, top: 3, bottom: 3 }
                        }
                    }
                },
                {
                    x: '$media_bin',
                    borderColor: '#6B7280',
                    strokeDashArray: 4,
                    label: {
                        text: 'Media',
                        orientation: 'vertical',
                        borderWidth: 0,
                        style: {
                            background: '#6B7280',
                            color: '#fff',
                            fontSize: '11px',
                            fontWeight: 600,
                            padding: { left: 6, right: 6, top: 3, bottom: 3 }
                        }
                    }
                }
            ]
        },
        legend: { show: false }
    }""")

    options_js = t.substitute(
        height=380,
        font=_FONT,
        supermercado=supermercado,
        data=data_js,
        categories=cats_json,
        color=color,
        label_interval=label_interval,
        bin_width=bin_width,
        yaxis=yaxis_js,
        mediana_bin=mediana_bin,
        media_bin=media_bin,
    )

    # KPI cards debajo del grafico
    kpi_html = f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Mediana</div>
            <div class="kpi-value">{mediana:.2f} €</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Media</div>
            <div class="kpi-value">{media:.2f} €</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label"> 50% de productos entre </div>
            <div class="kpi-value">{p25:.2f} / {p75:.2f} €</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Cobertura</div>
            <div class="kpi-value">{en_rango:,} de {total:,}</div>
        </div>
    </div>"""

    title_html = (
        f'<div class="chart-title">{titulo}</div>'
        f'<div class="chart-subtitle">{subtitulo}</div>'
    )

    return _html_page(
        "chart-dist", options_js, extra_html=kpi_html
    ).replace(
        '<div id="chart-dist"></div>',
        f'{title_html}<div id="chart-dist"></div>')


# ═══════════════════════════════════════════════════════════════════════
# 3) HISTORICO DE PRECIO (area chart)
# ═══════════════════════════════════════════════════════════════════════

def apex_historico_precio_html(df_historico, nombre_producto=""):
    """Grafico de evolucion temporal de precio de un producto."""
    if df_historico.empty:
        return _html_vacio("No hay datos de precios disponibles")

    df = df_historico.copy()
    cf = _col_fecha(df)
    if cf is None:
        return _html_vacio("Columna de fecha no encontrada")

    df[cf] = pd.to_datetime(df[cf])
    df = df.sort_values(cf)

    # Convertir a timestamps ms + precios
    timestamps = (df[cf].astype(np.int64) // 10**6).tolist()
    precios = [round(float(p), 2) for p in df['precio'].tolist()]
    data_points = json.dumps(list(zip(timestamps, precios)))

    t = Template("""{
        chart: {
            type: 'area',
            height: 360,
            fontFamily: '$font',
            toolbar: { show: false },
            animations: { enabled: true, easing: 'easeinout', speed: 400 },
            zoom: { enabled: false },
            offsetX: 0
        },
        series: [{
            name: 'Precio',
            data: $data
        }],
        stroke: {
            curve: 'smooth',
            width: 2.5,
            colors: ['#2F80ED']
        },
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.25,
                opacityTo: 0.05,
                stops: [0, 100]
            }
        },
        colors: ['#2F80ED'],
        markers: {
            size: 5,
            colors: ['#2F80ED'],
            strokeColors: '#fff',
            strokeWidth: 2,
            hover: { sizeOffset: 3 }
        },
        xaxis: {
            type: 'datetime',
            labels: {
                format: 'dd/MM/yy',
                style: { fontSize: '11px', colors: '#6B7280' },
                offsetX: 0
            },
            axisBorder: { color: '#E5E7EB' },
            axisTicks: { color: '#E5E7EB' }
        },
        yaxis: {
            title: {
                text: 'Precio (€)',
                style: { fontSize: '12px', color: '#6B7280', fontWeight: 500 }
            },
            labels: {
                style: { fontSize: '11px', colors: '#6B7280' },
                formatter: function(val) { return val.toFixed(2) + ' €'; }
            }
        },
        grid: {
            borderColor: '#EEF2F7',
            strokeDashArray: 4,
            padding: { right: 30, left: 10 },
            xaxis: { lines: { show: false } },
            yaxis: { lines: { show: true } }
        },
        tooltip: {
            theme: 'dark',
            x: { format: 'dd/MM/yyyy' },
            y: { formatter: function(val) { return val.toFixed(2) + ' €'; } }
        }
    }""")

    options_js = t.substitute(
        font=_FONT,
        data=data_points,
    )

    titulo = f"Evolucion de precio: {nombre_producto}" if nombre_producto else "Evolucion de precio"
    title_html = f'<div class="chart-title">{titulo}</div>'

    return _html_page("chart-hist", options_js).replace(
        '<div id="chart-hist"></div>',
        f'{title_html}<div id="chart-hist"></div>')


# ═══════════════════════════════════════════════════════════════════════
# 4) COMPARATIVA SUPERMERCADOS (multi-line)
# ═══════════════════════════════════════════════════════════════════════

def apex_comparativa_supermercados_html(df_historico_equiv):
    """Grafico de lineas comparando precios entre supermercados.

    Usa tooltip compartido, patrones de linea distintos y markers
    diferenciados para que se distingan series con precios similares.
    """
    if df_historico_equiv.empty:
        return _html_vacio("No hay datos para comparar")

    df = df_historico_equiv.copy()
    cf = _col_fecha(df)
    if cf is None:
        return _html_vacio("Columna de fecha no encontrada")

    df[cf] = pd.to_datetime(df[cf])

    # Patrones de linea y formas de marker por serie (hasta 5 supers)
    dash_patterns = [0, 5, [8, 4], [2, 2], [10, 2, 2, 2]]
    marker_shapes = ['circle', 'square', 'diamond', 'triangle', 'cross']

    series_list = []
    colors_list = []
    dash_list = []
    shape_list = []
    for i, s in enumerate(df['supermercado'].unique()):
        df_s = df[df['supermercado'] == s].sort_values(cf)
        timestamps = (df_s[cf].astype(np.int64) // 10**6).tolist()
        precios = [round(float(p), 2) for p in df_s['precio'].tolist()]
        data_points = list(zip(timestamps, precios))
        series_list.append({"name": s, "data": data_points})
        colors_list.append(COLORES_SUPERMERCADO.get(s, '#95A5A6'))
        dash_list.append(dash_patterns[i % len(dash_patterns)])
        shape_list.append(marker_shapes[i % len(marker_shapes)])

    series_json = json.dumps(series_list)
    colors_json = json.dumps(colors_list)
    dash_json = json.dumps(dash_list)

    # Calcular rango Y para mas granularidad
    all_prices = df['precio'].dropna()
    y_min = float(all_prices.min())
    y_max = float(all_prices.max())
    y_range = y_max - y_min
    # Si el rango es muy pequeno, forzar al menos 0.10€ de rango
    if y_range < 0.10:
        y_center = (y_min + y_max) / 2
        y_min = y_center - 0.05
        y_max = y_center + 0.05
    # Padding del 15% arriba y abajo
    y_padding = max(y_range * 0.15, 0.02)
    y_min_axis = round(y_min - y_padding, 2)
    y_max_axis = round(y_max + y_padding, 2)

    t = Template("""{
        chart: {
            type: 'line',
            height: 380,
            fontFamily: '$font',
            toolbar: { show: false },
            animations: { enabled: true, easing: 'easeinout', speed: 400 },
            zoom: { enabled: false }
        },
        series: $series,
        stroke: {
            curve: 'smooth',
            width: 3,
            dashArray: $dashArray
        },
        colors: $colors,
        markers: {
            size: 6,
            strokeColors: '#fff',
            strokeWidth: 2,
            hover: { sizeOffset: 3 },
            shape: ['circle', 'square', 'diamond', 'triangle']
        },
        xaxis: {
            type: 'datetime',
            labels: {
                format: 'dd/MM/yy',
                style: { fontSize: '11px', colors: '#6B7280' }
            },
            axisBorder: { color: '#E5E7EB' },
            axisTicks: { color: '#E5E7EB' }
        },
        yaxis: {
            min: $ymin,
            max: $ymax,
            tickAmount: 8,
            title: {
                text: 'Precio (€)',
                style: { fontSize: '12px', color: '#6B7280', fontWeight: 500 }
            },
            labels: {
                style: { fontSize: '11px', colors: '#6B7280' },
                formatter: function(val) { return val.toFixed(3) + ' €'; }
            }
        },
        grid: {
            borderColor: '#EEF2F7',
            strokeDashArray: 4,
            padding: { right: 20, left: 10 },
            xaxis: { lines: { show: false } },
            yaxis: { lines: { show: true } }
        },
        tooltip: {
            shared: true,
            intersect: false,
            theme: 'dark',
            x: { format: 'dd/MM/yyyy' },
            y: { formatter: function(val) {
                if (val === undefined || val === null) return '';
                return val.toFixed(2) + ' €';
            } }
        },
        legend: {
            position: 'top',
            horizontalAlign: 'left',
            fontSize: '12px',
            fontWeight: 500,
            labels: { colors: '#4B5563' },
            markers: { radius: 4 },
            itemMargin: { horizontal: 12 }
        }
    }""")

    options_js = t.substitute(
        font=_FONT,
        series=series_json,
        colors=colors_json,
        dashArray=dash_json,
        ymin=y_min_axis,
        ymax=y_max_axis,
    )

    title_html = '<div class="chart-title">Comparativa de precios entre supermercados</div>'
    subtitle_html = '<div class="chart-subtitle">Cada supermercado usa un patron de linea distinto para diferenciarlos</div>'

    return _html_page("chart-comp", options_js).replace(
        '<div id="chart-comp"></div>',
        f'{title_html}{subtitle_html}<div id="chart-comp"></div>')
