# Guía de configuración del archivo .env

Esta guía explica cómo obtener las cookies necesarias para los supermercados
que requieren autenticación (Carrefour y Dia).

## ¿Por qué se necesitan cookies?

Mercadona tiene una API pública que no requiere autenticación. Sin embargo,
Carrefour y Dia requieren una cookie de sesión para acceder a sus APIs internas.
Esta cookie simula que eres un navegador que ha visitado la web normalmente.

## Pasos para obtener una cookie

El proceso es el mismo para Carrefour y Dia:

### 1. Abre la web del supermercado en tu navegador

- **Carrefour:** https://www.carrefour.es/supermercado/
- **Dia:** https://www.dia.es/compra-online/

### 2. Navega un poco por la web

Añade algún producto al carrito o simplemente navega por categorías.
Esto asegura que el servidor te asigna una cookie de sesión completa.

### 3. Abre las herramientas de desarrollador

Pulsa `F12` (o `Ctrl+Shift+I` en Windows, `Cmd+Option+I` en Mac).

### 4. Ve a la pestaña "Network" (Red)

Filtra por **XHR** o **Fetch** para ver solo las peticiones a APIs.

### 5. Haz clic en cualquier petición

Busca una petición que devuelva datos (productos, categorías, etc.).

### 6. Copia la cookie

En los **Headers** de la petición, busca el campo `Cookie` dentro de
**Request Headers**. Haz clic derecho → "Copy value".

La cookie es un texto largo que puede tener este aspecto:
```
JSESSIONID=abc123; _ga=GA1.2.123456; consent=true; ...
```

### 7. Pega en tu archivo .env

Abre el archivo `.env` en la raíz del proyecto y pega la cookie:

```env
COOKIE_CARREFOUR=JSESSIONID=abc123; _ga=GA1.2.123456; ...
COOKIE_DIA=dtCookie=v_4_srv_1_sn_abc; ...
```

## Renovación de cookies

Las cookies caducan periódicamente (cada pocas horas o días, depende del
supermercado). Cuando una cookie caduca, el scraper mostrará un aviso en
los logs y los datos de ese supermercado no se actualizarán.

Para renovar, simplemente repite el proceso anterior.

### Verificar estado de cookies

El sistema incluye verificación automática al ejecutarse. También puedes
verificar manualmente:

```python
from scraper.cookie_manager import verificar_todas_las_cookies
verificar_todas_las_cookies()
```

## Configuración en GitHub Codespaces

Si usas GitHub Codespaces, **no edites el .env directamente** en el repositorio
(sería público). En su lugar:

1. Ve a tu repositorio en GitHub.
2. Settings → Secrets and variables → Codespaces.
3. Crea dos secretos:
   - `COOKIE_CARREFOUR` con el valor de la cookie.
   - `COOKIE_DIA` con el valor de la cookie.
4. Estos secretos se inyectan automáticamente como variables de entorno
   en tu Codespace.

## Configuración en GitHub Actions

Mismo proceso pero en:

1. Settings → Secrets and variables → Actions.
2. Crear los mismos secretos: `COOKIE_CARREFOUR` y `COOKIE_DIA`.
3. El workflow `scraper_diario.yml` ya está configurado para usarlos.

## Solución de problemas

| Problema | Solución |
|----------|----------|
| "Cookie no válida" al ejecutar | La cookie ha caducado. Obtén una nueva. |
| El scraper devuelve 0 productos | Puede ser cookie caducada o cambio en la API. |
| "Variable no encontrada" | Asegúrate de que el `.env` está en la raíz del proyecto. |
| Funciona en local pero no en Actions | Verifica que los Secrets están bien configurados en GitHub. |
