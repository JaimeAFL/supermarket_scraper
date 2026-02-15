# Guía de configuración del archivo .env

Este documento explica cómo obtener las cookies necesarias para los supermercados que requieren sesión.

## Requisitos previos

- Navegador Google Chrome (u otro con herramientas de desarrollador)
- Archivo `.env` creado a partir de `example.env`

## Mercadona

**No necesita configuración.** La API de Mercadona es accesible sin cookies ni autenticación.

## Carrefour

1. Abre en tu navegador: `https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu/`
2. Pulsa **F12** para abrir las herramientas de desarrollador.
3. Ve a la pestaña **Red** (Network).
4. Pulsa **F5** para recargar la página.
5. En la lista de peticiones, busca la que se llama **menu/**.
6. Haz clic sobre ella y busca en **Encabezados de solicitud** el campo **Cookie**.
7. Copia todo el texto del campo Cookie.
8. Pégalo en tu archivo `.env`:

```
COOKIE_CARREFOUR=tu_texto_copiado_aquí
```

## Dia

1. Abre en tu navegador: `https://www.dia.es/api/v1/plp-insight/initial_analytics/charcuteria-y-quesos/jamon-cocido-lacon-fiambres-y-mortadela/c/L2001?navigation=L2001`
2. Pulsa **F12** para abrir las herramientas de desarrollador.
3. Ve a la pestaña **Red** (Network).
4. Pulsa **F5** para recargar la página.
5. En la lista de peticiones, busca la que se llama **L2001?navigation=L2001**.
6. Haz clic sobre ella y busca en **Encabezados de solicitud** el campo **Cookie**.
7. Copia todo el texto del campo Cookie.
8. Pégalo en tu archivo `.env`:

```
COOKIE_DIA=tu_texto_copiado_aquí
```

## Caducidad de las cookies

Las cookies de Carrefour y Dia caducan periódicamente. Cuando el scraper muestre un error de tipo "cookie caducada", repite el proceso de arriba para obtener una cookie nueva.

## GitHub Codespaces

Si usas Codespaces, en lugar de crear un archivo `.env`, puedes configurar las cookies como **Secrets**:

1. Ve a tu repositorio en GitHub.
2. Entra en **Settings > Secrets and variables > Codespaces**.
3. Añade `COOKIE_CARREFOUR` y `COOKIE_DIA` con sus valores.

Estas variables estarán disponibles automáticamente como variables de entorno en tu Codespace.
