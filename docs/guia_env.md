# Guía de variables de entorno (`.env`)

Este proyecto usa `python-dotenv`. Copia primero el ejemplo:

```bash
cp example.env .env
```

## Variables soportadas

| Variable | Obligatoria | Uso |
|---|---|---|
| `CODIGO_POSTAL` | Recomendada | Contexto geográfico para Dia/Alcampo y obtención automática de cookies. |
| `COOKIE_DIA` | Opcional* | Cookie de sesión de Dia (normalmente se autogenera). |
| `COOKIE_CARREFOUR` | Opcional | Fallback/manual para flujos legacy de verificación de cookies. |
| `SUPERMARKET_DB_PATH` | Opcional | Ruta absoluta personalizada para SQLite. |

\* En la práctica, `scraper/dia.py` necesita `COOKIE_DIA`, pero `main.py` y `run_scraper.py dia` intentan rellenarla automáticamente con `cookie_manager.py`.

## Recomendación por entorno

### Local (desarrollo)

Mínimo recomendado:

```env
CODIGO_POSTAL=28001
COOKIE_DIA=
COOKIE_CARREFOUR=
```

Con eso, el gestor de cookies intentará obtener `COOKIE_DIA` automáticamente cuando haga falta.

### GitHub Actions

Secrets recomendados:

- `CODIGO_POSTAL`
- `COOKIE_DIA` (opcional como fallback)
- `COOKIE_CARREFOUR` (opcional)

El workflow actual escribe `.env` por job según el supermercado.

## Verificación rápida

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('CP:', os.getenv('CODIGO_POSTAL')); print('COOKIE_DIA:', 'OK' if os.getenv('COOKIE_DIA') else 'AUTO/EMPTY'); print('DB_PATH:', os.getenv('SUPERMARKET_DB_PATH', 'database/supermercados.db'))"
```

## Resolución de problemas

### `Dia: No se encontró COOKIE_DIA`

1. Ejecuta primero con Playwright disponible:
   ```bash
   playwright install chromium
   ```
2. Reintenta `python run_scraper.py dia` para forzar obtención automática.
3. Si sigue fallando, añade manualmente `COOKIE_DIA` en `.env`.

### Error de base de datos/ruta

Si defines `SUPERMARKET_DB_PATH`, usa ruta absoluta y asegúrate de que la carpeta existe y tiene permisos de escritura.
