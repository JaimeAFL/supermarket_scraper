# Guía de configuración del archivo .env

Instrucciones paso a paso para configurar las variables de entorno
necesarias para ejecutar Supermarket Price Tracker.

## Resumen de variables

| Variable | Obligatoria | Valor por defecto | Descripción |
|---|---|---|---|
| `CODIGO_POSTAL` | Recomendada | `28001` (Madrid centro) | Geolocalización de precios |
| `COOKIE_CARREFOUR` | **Sí** | — | Cookie de sesión de Carrefour |
| `COOKIE_DIA` | No | Se obtiene automáticamente | Fallback si Playwright falla |
| `SUPERMARKET_DB_PATH` | No | `database/supermercados.db` | Ruta personalizada de la BD |

## Configuración inicial

1. Copia el archivo de ejemplo:

```bash
cp example.env .env
```

2. Abre `.env` con tu editor y rellena los valores siguiendo las
   instrucciones de abajo.

El archivo `.env` está incluido en `.gitignore` y nunca se sube al
repositorio. Contiene datos sensibles (cookies de sesión).

## Variables

### CODIGO_POSTAL

```
CODIGO_POSTAL=28001
```

Los supermercados muestran precios y disponibilidad según la zona
geográfica. Este código postal determina qué tienda/almacén sirve
los datos.

Usa el código postal de tu zona para obtener precios relevantes.
Si no lo configuras, se usa `28001` (Madrid centro) por defecto.

### COOKIE_CARREFOUR (obligatoria)

Carrefour es el único supermercado que requiere una cookie manual.
Mercadona, Alcampo y Eroski no necesitan cookies. Dia la obtiene
automáticamente con Playwright.

**Cómo obtener la cookie:**

1. Abre **https://www.carrefour.es/supermercado** en tu navegador
   (Chrome, Firefox, Edge).

2. Si es la primera vez, acepta las cookies del banner y selecciona
   tu código postal cuando te lo pida.

3. Navega a cualquier categoría de productos (por ejemplo, "Lácteos")
   para que la sesión se inicialice completamente.

4. Pulsa **F12** para abrir las herramientas de desarrollador.

5. Ve a la pestaña **Red** (Network).

6. Recarga la página con **F5**.

7. Haz clic en cualquier petición de la lista (preferiblemente una
   que vaya a `carrefour.es`).

8. En el panel derecho, busca la sección **Encabezados de solicitud**
   (Request Headers).

9. Busca la línea que dice **Cookie:** y copia **todo el valor**
   (es una cadena larga, puede tener varios cientos de caracteres).

10. Pega el valor en tu `.env`:

```
COOKIE_CARREFOUR=pega_aqui_todo_el_valor_de_la_cookie
```

**Notas importantes:**

- La cookie caduca aproximadamente cada 24 horas. Si el scraper de
  Carrefour falla con error 401, la cookie ha caducado y necesitas
  obtener una nueva.
- No incluyas comillas alrededor del valor.
- El valor empieza normalmente por algo como `SERVERID=...` o
  `_ga=...` y contiene múltiples pares `nombre=valor` separados
  por punto y coma.

**Ejemplo** (parcial, no funcional):

```
COOKIE_CARREFOUR=SERVERID=abc123; _ga=GA1.2.123456; userPrefLanguage=es; ...
```

### COOKIE_DIA (opcional)

```
COOKIE_DIA=
```

Dia obtiene su cookie **automáticamente** mediante Playwright. El
proceso es:

1. Playwright abre un navegador Chromium en modo headless.
2. Navega a `https://www.dia.es`.
3. Acepta el banner de cookies.
4. Introduce el código postal configurado.
5. Extrae la cookie de sesión del navegador.
6. La inyecta en `os.environ` para que el scraper la use.

Solo necesitas rellenar `COOKIE_DIA` manualmente si:

- Playwright no está instalado en tu entorno.
- La obtención automática falla (por ejemplo, Dia cambia su web).
- Estás en un entorno sin interfaz gráfica donde Playwright no
  puede ejecutarse.

En ese caso, sigue los mismos pasos que para Carrefour pero en
`https://www.dia.es`.

### SUPERMARKET_DB_PATH (opcional)

```
# SUPERMARKET_DB_PATH=/ruta/absoluta/a/tu/supermercados.db
```

Por defecto, la base de datos se guarda en `database/supermercados.db`
relativa a la raíz del proyecto. Esta variable permite usar una ruta
personalizada.

Casos de uso:

- Guardar la BD en un disco externo o volumen montado.
- Compartir la BD entre varias instalaciones del proyecto.
- Apuntar a una BD de producción diferente de la de desarrollo.

Si la usas, asegúrate de que es una **ruta absoluta**:

```
SUPERMARKET_DB_PATH=/home/usuario/datos/supermercados.db
```

## Configuración en GitHub Actions

Para la ejecución automática en GitHub Actions, las variables de
entorno se configuran como **Secrets** del repositorio:

1. Ve a tu repositorio en GitHub.
2. Settings → Secrets and variables → Actions.
3. Haz clic en **New repository secret**.
4. Añade cada variable:

| Name | Value |
|---|---|
| `CODIGO_POSTAL` | Tu código postal (ej: `28001`) |
| `COOKIE_CARREFOUR` | Cookie de Carrefour (valor completo) |
| `COOKIE_DIA` | Dejar vacío (se obtiene automáticamente) |

El workflow `scraper_semanal.yml` lee estos secrets y crea un archivo
`.env` temporal durante la ejecución:

```yaml
- name: Configurar .env
  run: |
    echo "CODIGO_POSTAL=${{ secrets.CODIGO_POSTAL }}" >> .env
    echo "COOKIE_CARREFOUR=${{ secrets.COOKIE_CARREFOUR }}" >> .env
```

**Renovación de la cookie de Carrefour en GitHub Actions:**

Como la cookie caduca cada ~24 horas y el scraper se ejecuta
semanalmente, necesitarás actualizar el secret `COOKIE_CARREFOUR`
antes de cada lunes (o el mismo lunes por la mañana antes de las
7:00 AM). Alternativas para automatizar esto:

- Usar Playwright en el propio workflow para obtener la cookie
  automáticamente (requiere modificar el scraper de Carrefour).
- Configurar un workflow auxiliar que renueve la cookie y la
  guarde como secret vía la API de GitHub.

## Verificación

Para verificar que tu configuración es correcta, ejecuta:

```bash
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('CODIGO_POSTAL:', os.getenv('CODIGO_POSTAL', '(no configurado)'))
print('COOKIE_CARREFOUR:', 'OK' if os.getenv('COOKIE_CARREFOUR', '').strip() and not os.getenv('COOKIE_CARREFOUR', '').startswith('TU_COOKIE') else 'FALTA')
print('COOKIE_DIA:', 'Manual' if os.getenv('COOKIE_DIA', '').strip() else 'Automática (Playwright)')
print('DB_PATH:', os.getenv('SUPERMARKET_DB_PATH', 'database/supermercados.db (default)'))
"
```

Resultado esperado:

```
CODIGO_POSTAL: 28001
COOKIE_CARREFOUR: OK
COOKIE_DIA: Automática (Playwright)
DB_PATH: database/supermercados.db (default)
```

## Supermercados que no necesitan configuración

| Supermercado | Razón |
|---|---|
| Mercadona | API pública, sin autenticación |
| Alcampo | Sesión gestionada por Playwright automáticamente |
| Eroski | Sesión gestionada por Playwright automáticamente |
