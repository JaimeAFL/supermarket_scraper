# Guía de estilos visuales (ApexCharts)

Esta guía define una base visual consistente para dashboards de precios y comparación entre supermercados usando **ApexCharts**.

## 1) Principios visuales

- Priorizar legibilidad por encima de decoración.
- Máximo contraste en datos clave (mediana, media, variación).
- Colores semánticos:
  - Azul: dato principal
  - Verde: mejora/ahorro
  - Ámbar: atención
  - Rojo: empeora/sobreprecio
- Evitar saturación visual: usar mucho espacio en blanco y bordes suaves.

## 2) Tokens de diseño

### Colores

- `--bg: #F7F9FC`
- `--surface: #FFFFFF`
- `--text: #1F2937`
- `--muted: #6B7280`
- `--border: #E5E7EB`
- `--primary: #2F80ED`
- `--success: #27AE60`
- `--warning: #F2C94C`
- `--danger: #EB5757`

### Tipografía

- Familia principal: `Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif`
- Títulos: 600
- Texto y ejes: 400–500

### Espaciado y radios

- Grid base: 8px
- Padding tarjetas: 16px / 20px
- Radius tarjetas: 12px
- Radius labels/etiquetas: 8px

## 3) Convenciones para gráficas

- Quitar ruido visual:
  - Sin sombras duras.
  - Grid horizontal sutil y sin grid vertical.
- Tooltips con fondo oscuro y texto claro.
- Etiquetas clave en caja (media, mediana, cobertura de datos).
- Leyenda superior y compacta.

## 4) Configuración base recomendada de ApexCharts

```js
const baseChartOptions = {
  chart: {
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    toolbar: { show: false },
    animations: { enabled: true, easing: "easeinout", speed: 350 }
  },
  grid: {
    borderColor: "#EEF2F7",
    strokeDashArray: 4,
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } }
  },
  dataLabels: { enabled: false },
  stroke: { curve: "smooth", width: 2 },
  colors: ["#2F80ED", "#27AE60", "#F2C94C", "#EB5757"],
  tooltip: {
    theme: "dark",
    x: { show: true },
    y: { formatter: (v) => `${v.toFixed(2)} €` }
  },
  legend: {
    position: "top",
    horizontalAlign: "left",
    fontSize: "12px",
    labels: { colors: "#4B5563" }
  }
};
```

## 5) Prueba visual incluida

Se incluye una demo HTML lista para abrir en navegador con:

- Histograma de distribución de precios con eje en intervalos de **5€**.
- Líneas de mediana y media (etiquetas sin número dentro de la gráfica).
- Tarjetas KPI inferiores con valores numéricos de mediana y media.
- Tarjeta KPI de cobertura (`X de X productos`).

Archivo: `docs/examples/apexcharts_style_demo.html`.

## 6) Siguientes pasos sugeridos para el proyecto

1. Unificar colores de supermercados y tokens en un único módulo de tema.
2. Crear wrapper utilitario para opciones comunes de ApexCharts.
3. Migrar primero gráficos más críticos (distribución y evolución de precios).
4. Mantener pruebas visuales por screenshot para evitar regresiones de UI.
