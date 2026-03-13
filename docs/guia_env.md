# Guía de variables de entorno (`.env`)

Este proyecto usa `python-dotenv`. Copia primero el archivo de ejemplo:

```bash
cp example.env .env
```

Edita `.env` con tus valores antes de ejecutar cualquier scraper.

## Variables soportadas

| Variable | Obligatoria | Usado por | Descripción |
|---|---|---|---|
| `DATABASE_URL` | **Sí** | Todos | Cadena de conexión a PostgreSQL. Formato: `postgresql://usuario:contraseña@host:5432/nombre_bd`. |
| `CODIGO_POSTAL` | Recomendada | Dia, Alcampo, Carrefour | Contexto geográfico para precios y disponibilidad de tienda. |
| `COOKIE_DIA` | Opcional* | Dia | Cookie de sesión. Normalmente se obtiene automáticamente con Playwright. |
| `COOKIE_CARREFOUR` | Opcional | Carrefour | Fallback manual para flujos legacy de verificación de cookies. |
| `TIMEOUT_MERCADONA_MIN` | Opcional | main.py | Timeout en minutos para el scraper de Mercadona (por defecto: 15). |
| `TIMEOUT_CARREFOUR_MIN` | Opcional | main.py | Timeout en minutos para Carrefour (por defecto: 40). |
| `TIMEOUT_DIA_MIN` | Opcional | main.py | Timeout en minutos para Dia (por defecto: 20). |
| `TIMEOUT_ALCAMPO_MIN` | Opcional | main.py | Timeout en minutos para Alcampo (por defecto: 45). |
| `TIMEOUT_EROSKI_MIN` | Opcional | main.py | Timeout en minutos para Eroski (por defecto: 110). |
| `TIMEOUT_CONSUM_MIN` | Opcional | main.py | Timeout en minutos para Consum (por defecto: 5). |

\* `dia.py` necesita `COOKIE_DIA` en runtime, pero `main.py` y `run_scraper.py dia` intentan obtenerla automáticamente vía `cookie_manager.py` antes de ejecutar el scraper.

## Configuración por entorno

### Desarrollo local

Mínimo recomendado:

```env
DATABASE_URL=postgresql://usuario:contraseña@host:5432/supermercados
CODIGO_POSTAL=28001
COOKIE_DIA=
COOKIE_CARREFOUR=
```

Con `COOKIE_DIA` vacío, el gestor de cookies intentará obtenerla automáticamente. Si ya tienes una cookie válida, puedes pegarla directamente para evitar el paso de Playwright.

### GitHub Actions / Codespaces

En lugar del archivo `.env`, configura los valores como **Secrets** en el repositorio:

`Settings → Secrets and variables → Actions → New repository secret`

Secrets recomendados:

| Secret | Necesidad |
|---|---|
| `DATABASE_URL` | **Obligatoria** |
| `CODIGO_POSTAL` | Recomendada |
| `COOKIE_DIA` | Opcional (fallback) |
| `COOKIE_CARREFOUR` | Opcional (fallback) |

El workflow escribe automáticamente un `.env` por job según los secrets disponibles. Los timeouts de scrapers se pueden sobreescribir como secrets adicionales si algún entorno de CI es más lento de lo habitual.

## Verificación rápida

```bash
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('DATABASE_URL:', 'OK' if os.getenv('DATABASE_URL') else 'NO DEFINIDA — requerida')
print('CODIGO_POSTAL:', os.getenv('CODIGO_POSTAL', 'NO DEFINIDO'))
print('COOKIE_DIA:', 'OK' if os.getenv('COOKIE_DIA') else 'AUTO/VACÍO')
print('COOKIE_CARREFOUR:', 'OK' if os.getenv('COOKIE_CARREFOUR') else 'NO DEFINIDA')
"
```

## Resolución de problemas

### `DATABASE_URL no definida` / error de conexión

Asegúrate de que `DATABASE_URL` está presente en tu `.env` o como secret de GitHub. La URL debe incluir credenciales válidas y apuntar a la instancia correcta de PostgreSQL. Ejemplo:

```env
DATABASE_URL=postgresql://usuario:contraseña@host:5432/supermercados
```

Si el host es Aiden, consulta el panel de administración del servicio para obtener la URL de conexión exacta.

### `Dia: No se encontró COOKIE_DIA`

1. Asegúrate de tener Playwright instalado:
   ```bash
   playwright install chromium
   playwright install-deps chromium
   ```
2. Reintenta `python run_scraper.py dia` para forzar obtención automática.
3. Si sigue fallando, obtén la cookie manualmente desde DevTools del navegador y añádela en `.env`:
   ```env
   COOKIE_DIA=tu_cookie_aqui
   ```

### Timeout de un scraper

Si un scraper se cancela por timeout, puedes ajustar el valor para ese scraper sin modificar el código:

```env
TIMEOUT_EROSKI_MIN=150
```
