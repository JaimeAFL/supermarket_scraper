# Supermarket Price Tracker

Comparador y rastreador de precios de supermercados en España. Extrae datos de las APIs internas de los principales supermercados, almacena un histórico de precios en base de datos y ofrece un dashboard interactivo para comparar precios entre cadenas.

## Supermercados soportados

| Supermercado | Estado | Autenticación |
|---|---|---|
| Mercadona | Funcional | No requiere (API pública) |
| Carrefour | Funcional | Cookie de sesión |
| Dia | Funcional | Cookie de sesión |
| Alcampo | En desarrollo | Cookie de sesión |
| Eroski | En desarrollo | Cookie de sesión |

## Tecnologías

**Extracción:** Python, Requests, Pandas

**Base de datos:** SQLite

**Dashboard:** Streamlit, Plotly

**Automatización:** GitHub Actions (ejecución diaria)

**Comparación de productos:** RapidFuzz (similitud de texto)

## Estructura del proyecto

```
supermarket-price-tracker/
├── .github/workflows/
│   └── scraper_diario.yml      # Ejecución automática diaria
├── scraper/
│   ├── mercadona.py             # API de Mercadona
│   ├── carrefour.py             # API de Carrefour
│   ├── dia.py                   # API de Dia
│   ├── alcampo.py               # API de Alcampo (en desarrollo)
│   ├── eroski.py                # API de Eroski (en desarrollo)
│   └── cookie_manager.py        # Gestión y verificación de cookies
├── database/                     # Base de datos SQLite (próximamente)
├── matching/                     # Equivalencia entre productos (próximamente)
├── dashboard/                    # Dashboard Streamlit (próximamente)
├── main.py                      # Punto de entrada
├── requirements.txt             # Dependencias
├── example.env                  # Plantilla de configuración
└── README.md
```

## Instalación

### Requisitos previos

- Python 3.9 o superior
- Git

### Pasos

1. Clona el repositorio:
```bash
git clone https://github.com/tu-usuario/supermarket-price-tracker.git
cd supermarket-price-tracker
```

2. Crea y activa un entorno virtual:
```bash
python -m venv venv

# Linux / Mac / Codespaces
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Configura las cookies:
```bash
cp example.env .env
```
Edita el archivo `.env` con tus cookies reales. Consulta la guía en `docs/guia_env.md` para obtenerlas.

5. Ejecuta el scraper:
```bash
python main.py
```

## Configuración de cookies

Mercadona no necesita cookies. Para Carrefour y Dia:

1. Abre la web del supermercado en el navegador.
2. Pulsa F12 para abrir las herramientas de desarrollador.
3. Ve a la pestaña Red (Network).
4. Recarga la página (F5).
5. Haz clic en cualquier petición y busca "Cookie" en los encabezados de solicitud.
6. Copia el valor completo y pégalo en tu archivo `.env`.

Para más detalles, consulta `docs/guia_env.md`.

### Codespaces / GitHub Actions

En lugar del archivo `.env`, configura las cookies como **Secrets** en tu repositorio de GitHub:

Settings > Secrets and variables > Actions > New repository secret

## Uso

### Ejecución manual
```bash
python main.py
```

### Ejecución automática (GitHub Actions)

El workflow en `.github/workflows/scraper_diario.yml` se ejecuta automáticamente cada día a las 7:00 AM (hora española). También puedes lanzarlo manualmente desde la pestaña Actions del repositorio.

## Cómo funciona

1. **Extracción:** Cada scraper llama a la API interna del supermercado, obtiene el árbol de categorías y recorre cada una para extraer todos los productos con sus precios.

2. **Almacenamiento:** Los datos se guardan en una base de datos SQLite con timestamp, permitiendo construir un histórico de precios.

3. **Comparación:** Un sistema de equivalencias vincula el mismo producto entre distintos supermercados (por nombre, código de barras o manualmente).

4. **Visualización:** Un dashboard interactivo permite ver la evolución de precios y comparar entre cadenas.

## Roadmap

- [x] Scraper de Mercadona
- [x] Scraper de Carrefour
- [x] Scraper de Dia
- [x] GitHub Actions para ejecución diaria
- [x] Sistema de logging
- [ ] Base de datos SQLite con histórico
- [ ] Scraper de Alcampo
- [ ] Scraper de Eroski
- [ ] Sistema de equivalencias entre productos
- [ ] Dashboard con Streamlit
- [ ] Gráficos de evolución de precios con Plotly
- [ ] Comparador entre supermercados
- [ ] Sistema de favoritos
- [ ] Alertas de bajadas de precio

## Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## Disclaimer

Este proyecto es exclusivamente educativo y de uso personal. Los datos extraídos son de acceso público. Consulta los términos de uso de cada supermercado antes de usar esta herramienta. Se recomienda usar pausas entre peticiones para no sobrecargar los servidores.
