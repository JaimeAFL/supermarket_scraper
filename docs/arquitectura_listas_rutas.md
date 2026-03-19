# Arquitectura: Listas de la compra, Ruta óptima y Envíos

Documento de referencia para implementar tres nuevas funcionalidades en Supermarket Price Tracker. Diseñado para ser leído por Claude Code junto con el código existente del repositorio.

> **Regla general:** todo el código, comentarios, docstrings y nombres de variables van en **español**. Los archivos se generan completos, listos para copiar al repo. No se usan dependencias de pago.

---

## Índice

1. [Visión general](#1-visión-general)
2. [Fase 1 — Listas de la compra persistentes](#2-fase-1--listas-de-la-compra-persistentes)
3. [Fase 2 — Información de envíos](#3-fase-2--información-de-envíos)
4. [Fase 3 — Ruta óptima entre supermercados](#4-fase-3--ruta-óptima-entre-supermercados)
5. [Cambios en archivos existentes](#5-cambios-en-archivos-existentes)
6. [Dependencias nuevas](#6-dependencias-nuevas)
7. [Tests](#7-tests)
8. [Orden de implementación](#8-orden-de-implementación)

---

## 1. Visión general

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NUEVAS FUNCIONALIDADES                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FASE 1: Listas persistentes (PostgreSQL)                          │
│  ├─ Crear/editar/eliminar listas con nombre y etiqueta             │
│  ├─ Añadir productos desde Comparador, Histórico o búsqueda       │
│  ├─ Visualizar coste total por supermercado en cada lista          │
│  └─ Exportar lista como PDF / email (reutilizar export.py)        │
│                                                                     │
│  FASE 2: Información de envíos                                     │
│  ├─ Tabla estática con costes de envío y umbrales por super        │
│  ├─ Mostrar en la cesta: "Te faltan X€ para envío gratis"         │
│  └─ Coste total real = productos + envío                           │
│                                                                     │
│  FASE 3: Ruta óptima (OpenStreetMap + OSRM)                       │
│  ├─ Geocodificar dirección del usuario (Nominatim)                 │
│  ├─ Buscar tiendas cercanas por supermercado (Overpass API)        │
│  ├─ Calcular ruta óptima entre tiendas (OSRM /trip)               │
│  └─ Visualizar en mapa interactivo (Folium + streamlit-folium)    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Fase 1 — Listas de la compra persistentes

### 2.1. Nuevas tablas (añadir en `init_db.py`)

```sql
-- Listas de la compra del usuario
CREATE TABLE IF NOT EXISTS listas (
    id              SERIAL PRIMARY KEY,
    nombre          TEXT    NOT NULL,
    etiqueta        TEXT    DEFAULT '',       -- "mensual", "barbacoa", "bebe", etc.
    notas           TEXT    DEFAULT '',
    fecha_creacion  TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
    fecha_actualizacion TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);

-- Productos dentro de cada lista
CREATE TABLE IF NOT EXISTS lista_productos (
    id              SERIAL PRIMARY KEY,
    lista_id        INTEGER NOT NULL REFERENCES listas(id) ON DELETE CASCADE,
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        INTEGER NOT NULL DEFAULT 1,
    notas           TEXT    DEFAULT '',
    fecha_agregado  TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
    UNIQUE(lista_id, producto_id)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_lista_productos_lista ON lista_productos(lista_id);
CREATE INDEX IF NOT EXISTS idx_lista_productos_producto ON lista_productos(producto_id);
```

### 2.2. Nuevos métodos en `database_db_manager.py`

Añadir a la clase `DatabaseManager`:

```python
# ── Listas de la compra ───────────────────────────────────────────

def crear_lista(self, nombre: str, etiqueta: str = "", notas: str = "") -> int:
    """Crea una lista nueva. Devuelve el id de la lista creada."""
    cur = self._cursor()
    cur.execute("""
        INSERT INTO listas (nombre, etiqueta, notas)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (nombre, etiqueta, notas))
    lista_id = cur.fetchone()["id"]
    self._conn.commit()
    return lista_id

def obtener_listas(self) -> pd.DataFrame:
    """Devuelve todas las listas con conteo de productos y coste total."""
    cur = self._cursor()
    cur.execute("""
        SELECT l.id, l.nombre, l.etiqueta, l.notas,
               l.fecha_creacion, l.fecha_actualizacion,
               COUNT(lp.id) AS num_productos,
               COALESCE(SUM(
                   lp.cantidad * (
                       SELECT precio FROM precios
                       WHERE producto_id = lp.producto_id
                       ORDER BY fecha_captura DESC LIMIT 1
                   )
               ), 0) AS coste_total
        FROM listas l
        LEFT JOIN lista_productos lp ON lp.lista_id = l.id
        GROUP BY l.id
        ORDER BY l.fecha_actualizacion DESC
    """)
    rows = cur.fetchall()
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def obtener_lista_detalle(self, lista_id: int) -> pd.DataFrame:
    """Devuelve los productos de una lista con precio actual y supermercado."""
    cur = self._cursor()
    cur.execute("""
        SELECT lp.id AS lista_producto_id,
               lp.cantidad, lp.notas AS notas_producto,
               p.id AS producto_id, p.nombre, p.supermercado,
               p.marca, p.formato_normalizado, p.categoria_normalizada,
               p.url,
               (SELECT precio FROM precios
                WHERE producto_id = p.id
                ORDER BY fecha_captura DESC LIMIT 1
               ) AS precio
        FROM lista_productos lp
        JOIN productos p ON p.id = lp.producto_id
        WHERE lp.lista_id = %s
        ORDER BY p.supermercado, p.nombre
    """, (lista_id,))
    rows = cur.fetchall()
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def añadir_producto_a_lista(self, lista_id: int, producto_id: int, cantidad: int = 1) -> bool:
    """Añade un producto a una lista. Si ya existe, suma la cantidad."""
    cur = self._cursor()
    try:
        cur.execute("""
            INSERT INTO lista_productos (lista_id, producto_id, cantidad)
            VALUES (%s, %s, %s)
            ON CONFLICT (lista_id, producto_id) DO UPDATE SET
                cantidad = lista_productos.cantidad + EXCLUDED.cantidad,
                fecha_agregado = to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')
        """, (lista_id, producto_id, cantidad))
        # Actualizar timestamp de la lista
        cur.execute("""
            UPDATE listas SET fecha_actualizacion = to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')
            WHERE id = %s
        """, (lista_id,))
        self._conn.commit()
        return True
    except Exception as e:
        logger.error("añadir_producto_a_lista: %s", e)
        return False

def quitar_producto_de_lista(self, lista_id: int, producto_id: int) -> bool:
    """Elimina un producto de una lista."""
    cur = self._cursor()
    try:
        cur.execute(
            "DELETE FROM lista_productos WHERE lista_id=%s AND producto_id=%s",
            (lista_id, producto_id))
        cur.execute("""
            UPDATE listas SET fecha_actualizacion = to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')
            WHERE id = %s
        """, (lista_id,))
        self._conn.commit()
        return True
    except Exception as e:
        logger.error("quitar_producto_de_lista: %s", e)
        return False

def actualizar_cantidad_lista(self, lista_id: int, producto_id: int, cantidad: int) -> bool:
    """Actualiza la cantidad de un producto en una lista."""
    cur = self._cursor()
    try:
        cur.execute("""
            UPDATE lista_productos SET cantidad = %s
            WHERE lista_id = %s AND producto_id = %s
        """, (cantidad, lista_id, producto_id))
        self._conn.commit()
        return True
    except Exception as e:
        logger.error("actualizar_cantidad_lista: %s", e)
        return False

def eliminar_lista(self, lista_id: int) -> bool:
    """Elimina una lista y todos sus productos (CASCADE)."""
    cur = self._cursor()
    try:
        cur.execute("DELETE FROM listas WHERE id=%s", (lista_id,))
        self._conn.commit()
        return True
    except Exception as e:
        logger.error("eliminar_lista: %s", e)
        return False

def renombrar_lista(self, lista_id: int, nombre: str, etiqueta: str = None, notas: str = None):
    """Actualiza nombre, etiqueta y/o notas de una lista."""
    cur = self._cursor()
    sets = ["nombre = %s", "fecha_actualizacion = to_char(NOW(), 'YYYY-MM-DD\"T\"HH24:MI:SS')"]
    params = [nombre]
    if etiqueta is not None:
        sets.append("etiqueta = %s")
        params.append(etiqueta)
    if notas is not None:
        sets.append("notas = %s")
        params.append(notas)
    params.append(lista_id)
    cur.execute(f"UPDATE listas SET {', '.join(sets)} WHERE id = %s", params)
    self._conn.commit()

def duplicar_lista(self, lista_id: int, nuevo_nombre: str) -> int:
    """Duplica una lista existente con un nuevo nombre. Devuelve el id de la nueva lista."""
    cur = self._cursor()
    # Obtener datos de la lista original
    cur.execute("SELECT etiqueta, notas FROM listas WHERE id=%s", (lista_id,))
    orig = cur.fetchone()
    if not orig:
        raise ValueError(f"Lista {lista_id} no encontrada")
    
    nuevo_id = self.crear_lista(nuevo_nombre, orig["etiqueta"], orig["notas"])
    
    cur.execute(
        "SELECT producto_id, cantidad, notas FROM lista_productos WHERE lista_id=%s",
        (lista_id,))
    for row in cur.fetchall():
        cur.execute("""
            INSERT INTO lista_productos (lista_id, producto_id, cantidad, notas)
            VALUES (%s, %s, %s, %s)
        """, (nuevo_id, row["producto_id"], row["cantidad"], row["notas"]))
    self._conn.commit()
    return nuevo_id

def cargar_lista_en_cesta(self, lista_id: int) -> list:
    """Devuelve los productos de una lista en formato compatible con session_state['cesta'].
    
    Esto permite cargar una lista guardada directamente en la cesta activa
    para operar con ella (optimizar, exportar, calcular ruta, etc.).
    """
    df = self.obtener_lista_detalle(lista_id)
    if df.empty:
        return []
    
    cesta = []
    for _, row in df.iterrows():
        item = {
            'producto_id': int(row['producto_id']),
            'nombre': row.get('nombre', ''),
            'supermercado': row.get('supermercado', ''),
            'precio': float(row.get('precio', 0)) if row.get('precio') else 0,
            'formato_normalizado': row.get('formato_normalizado', ''),
            'marca': row.get('marca', ''),
            'cantidad': int(row.get('cantidad', 1)),
            'alternativa_id': None,
            'alternativa_nombre': None,
            'alternativa_super': None,
            'alternativa_precio': None,
            'original_id': None,
            'original_nombre': None,
            'original_super': None,
            'original_precio': None,
        }
        cesta.append(item)
    return cesta
```

### 2.3. Interfaz de usuario — Página `5_Listas.py`

Nueva página del dashboard. Estructura:

```
┌─────────────────────────────────────────────────────┐
│  ENCABEZADO: "Mis listas" (icono: list_alt)         │
├─────────────────────────────────────────────────────┤
│  SECCIÓN A: Crear nueva lista                       │
│  ├─ Input: nombre de la lista                       │
│  ├─ Selectbox: etiqueta predefinida o personalizada │
│  │   Opciones: Compra semanal, Compra mensual,      │
│  │   Barbacoa, Cumpleaños, Bebé, Dieta, Otra        │
│  ├─ Textarea: notas (opcional)                      │
│  └─ Botón: "Crear lista"                            │
├─────────────────────────────────────────────────────┤
│  SECCIÓN B: Mis listas (tarjetas)                   │
│  ├─ Tarjeta por lista con: nombre, etiqueta, #prod, │
│  │   coste total, fecha actualización               │
│  ├─ Botones: Ver/Editar | Cargar en cesta |         │
│  │   Duplicar | Eliminar                            │
│  └─ Al hacer clic en "Ver/Editar" se expande:       │
│      ├─ Tabla de productos con cantidad editable     │
│      ├─ Buscador para añadir productos               │
│      ├─ Desglose por supermercado                    │
│      └─ Botón eliminar producto individual           │
├─────────────────────────────────────────────────────┤
│  SECCIÓN C: Exportar lista seleccionada             │
│  ├─ PDF (reutilizar generar_pdf_cesta de export.py) │
│  └─ Email (reutilizar generar_enlaces_email)        │
└─────────────────────────────────────────────────────┘
```

**Etiquetas predefinidas** (con icono Material Icons Outlined):

| Etiqueta | Icono |
|---|---|
| Compra semanal | calendar_today |
| Compra mensual | date_range |
| Barbacoa | outdoor_grill |
| Cumpleaños | cake |
| Bebé | child_care |
| Dieta | monitor_weight |
| Otra | label |

**Integración con otras páginas:**

En `2_Comparador.py`, `1_Historico_precios.py` y `app.py` (búsqueda), añadir un botón "Añadir a lista" junto a cada producto. Al pulsarlo:
1. Mostrar selectbox con las listas existentes del usuario.
2. Llamar a `db.añadir_producto_a_lista(lista_id, producto_id)`.
3. Confirmar con `st.success()`.

**Flujo "Cargar en cesta":**

Al pulsar "Cargar en cesta" en una lista, se llama a `db.cargar_lista_en_cesta(lista_id)` y se asigna el resultado a `st.session_state['cesta']`. Después se redirige a la página 4_Cesta.py con `st.switch_page()`.

### 2.4. Reutilización de export.py

Las funciones `generar_pdf_cesta()` y `generar_enlaces_email()` ya reciben una lista de dicts con la estructura `{nombre, supermercado, precio, cantidad, formato_normalizado, ...}`. El formato que devuelve `cargar_lista_en_cesta()` es compatible, por lo que no hay que modificar `export.py`.

---

## 3. Fase 2 — Información de envíos

### 3.1. Nueva tabla (añadir en `init_db.py`)

```sql
CREATE TABLE IF NOT EXISTS envios (
    id                  SERIAL PRIMARY KEY,
    supermercado        TEXT    NOT NULL UNIQUE,
    coste_envio         REAL    NOT NULL,       -- Coste estándar en euros
    umbral_gratis       REAL,                    -- Compra mínima para envío gratis (NULL = no hay)
    pedido_minimo       REAL,                    -- Pedido mínimo obligatorio (NULL = no hay)
    notas               TEXT    DEFAULT '',
    fecha_verificacion  TEXT    NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);
```

### 3.2. Datos iniciales

Insertar al inicializar la BD (en `init_db.py`, después de crear la tabla). Estos datos son orientativos y se actualizan manualmente:

```sql
INSERT INTO envios (supermercado, coste_envio, umbral_gratis, pedido_minimo, notas)
VALUES
    ('Mercadona', 7.70, NULL, 50.0, 'Pedido mínimo 50€. Sin envío gratis.'),
    ('Carrefour', 7.95, 99.0, NULL, 'Envío gratis a partir de 99€.'),
    ('Dia',       3.99, 39.0, NULL, 'Envío gratis a partir de 39€ con Club Dia.'),
    ('Alcampo',   6.90, 80.0, NULL, 'Envío gratis a partir de 80€.'),
    ('Eroski',    5.95, 50.0, NULL, 'Envío gratis a partir de 50€.'),
    ('Consum',    7.50, 60.0, NULL, 'Envío gratis a partir de 60€ en muchas zonas.'),
    ('Condis',    4.99, 49.0, NULL, 'Envío gratis a partir de 49€.')
ON CONFLICT (supermercado) DO NOTHING;
```

> **Importante:** estos valores son aproximados y pueden variar por zona. Incluir un disclaimer visible en la UI.

### 3.3. Nuevos métodos en `database_db_manager.py`

```python
def obtener_envios(self) -> pd.DataFrame:
    """Devuelve la tabla de costes de envío de todos los supermercados."""
    cur = self._cursor()
    cur.execute("SELECT * FROM envios ORDER BY supermercado")
    rows = cur.fetchall()
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def obtener_envio_supermercado(self, supermercado: str) -> dict:
    """Devuelve los datos de envío de un supermercado concreto."""
    cur = self._cursor()
    cur.execute("SELECT * FROM envios WHERE supermercado=%s", (supermercado,))
    row = cur.fetchone()
    return dict(row) if row else None
```

### 3.4. Integración en `4_Cesta.py`

En la sección "Desglose por supermercado" de la cesta, añadir por cada supermercado:

```
Mercadona:  3 productos | 42,50€ | Envío: 7,70€ | Total: 50,20€
Carrefour:  2 productos | 87,30€ | Te faltan 11,70€ para envío gratis | Envío: 7,95€
Dia:        1 producto  | 45,00€ | Envío gratis                       | Envío: 0,00€
```

Lógica por supermercado:
```python
envio = db.obtener_envio_supermercado(supermercado)
if envio:
    subtotal = ...  # suma de productos de ese super en la cesta
    if envio['pedido_minimo'] and subtotal < envio['pedido_minimo']:
        # Mostrar warning: "Pedido mínimo: X€. Te faltan Y€."
    elif envio['umbral_gratis'] and subtotal >= envio['umbral_gratis']:
        coste_envio = 0  # Envío gratis
    else:
        coste_envio = envio['coste_envio']
        if envio['umbral_gratis']:
            faltan = envio['umbral_gratis'] - subtotal
            # Mostrar: "Te faltan {faltan:.2f}€ para envío gratis"
```

Añadir una fila al final del resumen con el coste total incluyendo envíos.

---

## 4. Fase 3 — Ruta óptima entre supermercados

### 4.1. Nuevo módulo: `routing.py` (raíz del proyecto)

Este módulo encapsula toda la lógica de geolocalización y rutas. No toca la base de datos.

```python
"""routing.py - Geolocalización y cálculo de rutas con APIs gratuitas.

APIs utilizadas (todas gratuitas, sin API key):
- Nominatim (OpenStreetMap): geocodificación de direcciones
- Overpass API (OpenStreetMap): búsqueda de supermercados cercanos
- OSRM demo server: cálculo de rutas y optimización de paradas

Restricciones de uso responsable:
- Nominatim: máximo 1 petición/segundo, incluir User-Agent con email
- Overpass: no abusar (cachear resultados cuando sea posible)
- OSRM demo: solo para proyectos pequeños / demo
"""

import requests
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────

# User-Agent obligatorio para Nominatim (poner email del desarrollador)
_USER_AGENT = "SupermarketPriceTracker/1.0 (contacto@ejemplo.com)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OSRM_URL = "https://router.project-osrm.org"

# Nombres de supermercados tal como aparecen en OpenStreetMap
# Clave = nombre en nuestra BD, Valor = posibles nombres en OSM
NOMBRES_OSM = {
    "Mercadona":  ["Mercadona"],
    "Carrefour":  ["Carrefour", "Carrefour Express", "Carrefour Market"],
    "Dia":        ["Dia", "Dia %", "DIA"],
    "Alcampo":    ["Alcampo", "Alcampo Supermercado"],
    "Eroski":     ["Eroski", "Eroski City", "Eroski Center"],
    "Consum":     ["Consum", "Consum Bàsic"],
    "Condis":     ["Condis", "Condis Express"],
}


# ── Geocodificación (Nominatim) ───────────────────────────────────

def geocodificar(direccion: str, pais: str = "es") -> Optional[dict]:
    """Convierte una dirección o código postal en coordenadas.
    
    Args:
        direccion: Dirección completa o código postal.
        pais: Código ISO del país (default: "es" para España).
    
    Returns:
        dict con claves "lat", "lon", "display_name" o None si no se encontró.
    """
    try:
        resp = requests.get(
            f"{_NOMINATIM_URL}/search",
            params={
                "q": direccion,
                "format": "json",
                "limit": 1,
                "countrycodes": pais,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json()
        if not resultados:
            return None
        r = resultados[0]
        return {
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "display_name": r.get("display_name", ""),
        }
    except Exception as e:
        logger.error("geocodificar: %s", e)
        return None
    finally:
        time.sleep(1)  # Respetar límite de 1 req/seg


# ── Búsqueda de supermercados cercanos (Overpass) ──────────────────

def buscar_supermercados_cercanos(
    lat: float, lon: float,
    supermercados: list[str],
    radio_metros: int = 5000,
) -> dict[str, list[dict]]:
    """Busca tiendas físicas de los supermercados indicados cerca de un punto.
    
    Args:
        lat, lon: Coordenadas del usuario.
        supermercados: Lista de nombres de supermercados (e.g. ["Mercadona", "Dia"]).
        radio_metros: Radio de búsqueda en metros (default: 5000 = 5 km).
    
    Returns:
        dict donde la clave es el nombre del supermercado y el valor es una lista
        de tiendas, cada una con "lat", "lon", "nombre", "direccion".
        Solo devuelve la tienda más cercana por supermercado.
    """
    # Construir query Overpass con todas las marcas a la vez
    filtros = []
    for super_nombre in supermercados:
        nombres_osm = NOMBRES_OSM.get(super_nombre, [super_nombre])
        for nombre_osm in nombres_osm:
            filtros.append(
                f'node["shop"="supermarket"]["name"="{nombre_osm}"](around:{radio_metros},{lat},{lon});'
            )
            # Algunos supermercados están mapeados como way, no como node
            filtros.append(
                f'way["shop"="supermarket"]["name"="{nombre_osm}"](around:{radio_metros},{lat},{lon});'
            )
    
    query = f"""
    [out:json][timeout:25];
    (
        {"".join(filtros)}
    );
    out center;
    """
    
    try:
        resp = requests.post(
            _OVERPASS_URL,
            data={"data": query},
            timeout=30,
        )
        resp.raise_for_status()
        datos = resp.json()
    except Exception as e:
        logger.error("buscar_supermercados_cercanos: %s", e)
        return {s: [] for s in supermercados}
    
    # Agrupar resultados por supermercado y quedarse con el más cercano
    import math
    
    def _distancia(lat1, lon1, lat2, lon2):
        """Distancia Haversine aproximada en metros."""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    resultados = {s: [] for s in supermercados}
    
    for elemento in datos.get("elements", []):
        # Obtener coordenadas (center para ways, directo para nodes)
        e_lat = elemento.get("lat") or elemento.get("center", {}).get("lat")
        e_lon = elemento.get("lon") or elemento.get("center", {}).get("lon")
        if not e_lat or not e_lon:
            continue
        
        nombre_osm = elemento.get("tags", {}).get("name", "")
        direccion_parts = []
        tags = elemento.get("tags", {})
        for tag in ["addr:street", "addr:housenumber", "addr:city"]:
            if tags.get(tag):
                direccion_parts.append(tags[tag])
        direccion = ", ".join(direccion_parts) if direccion_parts else ""
        
        # Identificar a qué supermercado pertenece
        for super_nombre in supermercados:
            nombres_osm_validos = NOMBRES_OSM.get(super_nombre, [super_nombre])
            if any(nombre_osm.lower().startswith(n.lower().replace("%", "")) 
                   for n in nombres_osm_validos):
                dist = _distancia(lat, lon, e_lat, e_lon)
                resultados[super_nombre].append({
                    "lat": e_lat,
                    "lon": e_lon,
                    "nombre": nombre_osm,
                    "direccion": direccion,
                    "distancia_m": round(dist),
                })
                break
    
    # Ordenar por distancia y quedarse con la más cercana de cada super
    for super_nombre in supermercados:
        tiendas = sorted(resultados[super_nombre], key=lambda x: x["distancia_m"])
        resultados[super_nombre] = tiendas[:1]  # Solo la más cercana
    
    return resultados


# ── Ruta óptima (OSRM) ────────────────────────────────────────────

def calcular_ruta_optima(
    origen: dict,
    paradas: list[dict],
    modo: str = "driving",
) -> Optional[dict]:
    """Calcula la ruta óptima pasando por todas las paradas.
    
    Usa OSRM /trip que resuelve el Travelling Salesman Problem.
    
    Args:
        origen: dict con "lat" y "lon" del punto de partida (casa del usuario).
        paradas: lista de dicts con "lat", "lon", "nombre", "supermercado".
        modo: "driving" (default), "walking", "cycling".
    
    Returns:
        dict con:
        - "paradas_ordenadas": lista de paradas en el orden óptimo
        - "distancia_total_km": distancia total del recorrido
        - "duracion_total_min": duración estimada en minutos
        - "geometria": lista de [lon, lat] para pintar la ruta en Folium
        - "tramos": lista de dicts con distancia y duración por tramo
        O None si no se pudo calcular.
    """
    if not paradas:
        return None
    
    # Construir coordenadas: origen + paradas
    # OSRM espera lon,lat (no lat,lon)
    coords = f"{origen['lon']},{origen['lat']}"
    for p in paradas:
        coords += f";{p['lon']},{p['lat']}"
    
    profile = {"driving": "car", "walking": "foot", "cycling": "bike"}.get(modo, "car")
    
    try:
        resp = requests.get(
            f"{_OSRM_URL}/trip/v1/{profile}/{coords}",
            params={
                "source": "first",          # El origen es el primer punto
                "destination": "last",       # Volver al origen (roundtrip por defecto)
                "roundtrip": "true",
                "geometries": "geojson",     # Para Folium
                "overview": "full",
                "steps": "true",
            },
            timeout=15,
        )
        resp.raise_for_status()
        datos = resp.json()
    except Exception as e:
        logger.error("calcular_ruta_optima: %s", e)
        return None
    
    if datos.get("code") != "Ok" or not datos.get("trips"):
        logger.warning("OSRM no devolvió ruta válida: %s", datos.get("code"))
        return None
    
    trip = datos["trips"][0]
    waypoints = datos.get("waypoints", [])
    
    # Reconstruir orden óptimo de paradas
    # waypoints[0] es el origen, el resto son las paradas
    # Cada waypoint tiene "waypoint_index" que indica su posición en el trip
    paradas_con_orden = []
    for i, wp in enumerate(waypoints):
        if i == 0:
            continue  # Saltar origen
        parada_original = paradas[i - 1]
        paradas_con_orden.append({
            **parada_original,
            "orden_trip": wp.get("waypoint_index", i),
        })
    paradas_con_orden.sort(key=lambda x: x["orden_trip"])
    
    # Extraer geometría para Folium
    geometria = trip.get("geometry", {}).get("coordinates", [])
    
    # Extraer tramos
    tramos = []
    for leg in trip.get("legs", []):
        tramos.append({
            "distancia_km": round(leg["distance"] / 1000, 1),
            "duracion_min": round(leg["duration"] / 60, 1),
        })
    
    return {
        "paradas_ordenadas": paradas_con_orden,
        "distancia_total_km": round(trip["distance"] / 1000, 1),
        "duracion_total_min": round(trip["duration"] / 60, 1),
        "geometria": geometria,  # Lista de [lon, lat]
        "tramos": tramos,
    }
```

### 4.2. Integración en `4_Cesta.py`

Añadir una nueva sección al final de la página de cesta:

```
┌─────────────────────────────────────────────────────┐
│  SECCIÓN E: Ruta de compra (icono: route)           │
├─────────────────────────────────────────────────────┤
│  Input: "Tu dirección o código postal"              │
│  Selectbox: Modo de transporte (Coche/A pie/Bici)   │
│  Slider: Radio de búsqueda (1-15 km, default 5 km)  │
│  Botón: "Calcular ruta"                             │
│                                                     │
│  Al pulsar:                                         │
│  1. Geocodificar dirección (Nominatim)              │
│  2. Identificar qué supermercados hay en la cesta   │
│  3. Buscar la tienda más cercana de cada uno         │
│  4. Calcular ruta óptima (OSRM /trip)               │
│  5. Mostrar mapa con Folium:                        │
│     - Marcador casa (icono home, negro)              │
│     - Marcador por tienda (color del supermercado)   │
│     - Línea de ruta entre paradas                    │
│     - Popup con nombre tienda y dirección            │
│  6. Mostrar debajo del mapa:                        │
│     - Orden de paradas (1. Mercadona → 2. Dia → ...) │
│     - Distancia total y duración estimada            │
│     - Distancia y duración por tramo                 │
│                                                     │
│  Casos especiales:                                   │
│  - Si no encuentra tienda de un super → aviso        │
│  - Si la cesta tiene un solo super → ruta directa    │
│  - Si la dirección no se geocodifica → error claro   │
│  - Si OSRM falla → mensaje de error + fallback sin   │
│    optimización (mostrar tiendas en mapa sin ruta)   │
└─────────────────────────────────────────────────────┘
```

**Código Folium para el mapa:**

```python
import folium
from streamlit_folium import st_folium

def generar_mapa_ruta(origen, tiendas, ruta_datos, colores_super):
    """Genera un mapa Folium con la ruta de compra.
    
    Args:
        origen: dict con "lat", "lon"
        tiendas: lista de dicts con "lat", "lon", "nombre", "supermercado"
        ruta_datos: resultado de calcular_ruta_optima() o None
        colores_super: dict COLORES_SUPERMERCADO de styles.py
    
    Returns:
        folium.Map listo para st_folium()
    """
    mapa = folium.Map(
        location=[origen["lat"], origen["lon"]],
        zoom_start=14,
        tiles="OpenStreetMap",
    )
    
    # Marcador de casa
    folium.Marker(
        location=[origen["lat"], origen["lon"]],
        popup="Tu ubicación",
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(mapa)
    
    # Marcadores de tiendas
    for tienda in tiendas:
        color_hex = colores_super.get(tienda["supermercado"], "#95A5A6")
        folium.Marker(
            location=[tienda["lat"], tienda["lon"]],
            popup=f"{tienda['nombre']}<br>{tienda.get('direccion', '')}",
            icon=folium.Icon(
                color="green",  # Color base del marcador Folium
                icon="shopping-cart",
                prefix="fa",
                icon_color=color_hex,
            ),
        ).add_to(mapa)
    
    # Línea de ruta
    if ruta_datos and ruta_datos.get("geometria"):
        # GeoJSON viene en [lon, lat], Folium espera [lat, lon]
        puntos_ruta = [[p[1], p[0]] for p in ruta_datos["geometria"]]
        folium.PolyLine(
            locations=puntos_ruta,
            color="#1565C0",
            weight=4,
            opacity=0.8,
        ).add_to(mapa)
    
    # Ajustar zoom para que se vean todos los puntos
    todos_puntos = [[origen["lat"], origen["lon"]]]
    for t in tiendas:
        todos_puntos.append([t["lat"], t["lon"]])
    mapa.fit_bounds(todos_puntos)
    
    return mapa
```

**Uso en 4_Cesta.py:**

```python
from routing import geocodificar, buscar_supermercados_cercanos, calcular_ruta_optima

# En la sección E de la cesta:
mapa = generar_mapa_ruta(origen, tiendas_encontradas, ruta, COLORES_SUPERMERCADO)
st_folium(mapa, width=700, height=450)
```

### 4.3. Cacheo con `st.session_state`

Para evitar llamadas innecesarias a APIs externas, cachear los resultados:

```python
# Guardar en session_state para no recalcular al interactuar con la página
if 'ruta_cache' not in st.session_state:
    st.session_state['ruta_cache'] = {
        'direccion': None,
        'tiendas': None,
        'ruta': None,
    }

# Solo recalcular si la dirección o la cesta cambiaron
if (direccion_input != st.session_state['ruta_cache']['direccion']
        or supermercados_en_cesta != supermercados_anteriores):
    # Recalcular...
    st.session_state['ruta_cache'] = { ... }
```

---

## 5. Cambios en archivos existentes

| Archivo | Cambio |
|---|---|
| `init_db.py` | Añadir tablas `listas`, `lista_productos`, `envios` + datos iniciales de envíos + índices |
| `database_db_manager.py` | Añadir métodos de listas (crear, obtener, añadir producto, quitar, etc.) + métodos de envíos |
| `4_Cesta.py` | Añadir sección de envíos en desglose + sección de ruta óptima con Folium |
| `2_Comparador.py` | Añadir botón "Añadir a lista" junto a cada producto |
| `1_Historico_precios.py` | Añadir botón "Añadir a lista" junto al producto seleccionado |
| `app.py` | Añadir botón "Añadir a lista" en resultados de búsqueda |
| `styles.py` | Añadir color de Condis (`'Condis': '#C0392B'`) al dict `COLORES_SUPERMERCADO` |
| `requirements.txt` | Añadir `folium` y `streamlit-folium` |
| `CHANGELOG.md` | Documentar nuevas funcionalidades |

### Archivos nuevos

| Archivo | Descripción |
|---|---|
| `5_Listas.py` | Nueva página del dashboard: gestión de listas de la compra |
| `routing.py` | Módulo de geolocalización y rutas (Nominatim + Overpass + OSRM) |

---

## 6. Dependencias nuevas

Añadir a `requirements.txt`:

```
# =============================================================================
# Mapas y geolocalización
# =============================================================================
folium>=0.15.0
streamlit-folium>=0.18.0
```

No se necesitan API keys ni servicios de pago. Todas las APIs son públicas y gratuitas.

---

## 7. Tests

### `test_routing.py`

```python
"""Tests para el módulo de routing (geolocalización y rutas)."""

import pytest
from unittest.mock import patch, MagicMock

# Importar funciones a testear
from routing import geocodificar, buscar_supermercados_cercanos, calcular_ruta_optima


class TestGeocodificar:
    """Tests de geocodificación con Nominatim."""

    @patch("routing.requests.get")
    def test_geocodificar_direccion_valida(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"lat": "41.3874", "lon": "2.1686", "display_name": "Barcelona"}]
        )
        resultado = geocodificar("Barcelona, España")
        assert resultado is not None
        assert abs(resultado["lat"] - 41.3874) < 0.01
        assert abs(resultado["lon"] - 2.1686) < 0.01

    @patch("routing.requests.get")
    def test_geocodificar_sin_resultados(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
        resultado = geocodificar("zzzzzzzzz")
        assert resultado is None

    @patch("routing.requests.get")
    def test_geocodificar_error_red(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        resultado = geocodificar("Barcelona")
        assert resultado is None


class TestBuscarSupermercados:
    """Tests de búsqueda de supermercados con Overpass."""

    @patch("routing.requests.post")
    def test_buscar_supermercados_ok(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "elements": [
                    {
                        "type": "node",
                        "lat": 41.388,
                        "lon": 2.169,
                        "tags": {"name": "Mercadona", "shop": "supermarket"},
                    }
                ]
            }
        )
        resultado = buscar_supermercados_cercanos(41.387, 2.168, ["Mercadona"])
        assert "Mercadona" in resultado
        assert len(resultado["Mercadona"]) == 1

    @patch("routing.requests.post")
    def test_buscar_supermercados_sin_resultados(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"elements": []})
        resultado = buscar_supermercados_cercanos(0.0, 0.0, ["Mercadona"])
        assert resultado["Mercadona"] == []


class TestCalcularRuta:
    """Tests de cálculo de ruta con OSRM."""

    @patch("routing.requests.get")
    def test_ruta_optima_ok(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "code": "Ok",
                "trips": [{
                    "distance": 5000,
                    "duration": 600,
                    "geometry": {"coordinates": [[2.168, 41.387], [2.170, 41.390]]},
                    "legs": [
                        {"distance": 2500, "duration": 300},
                        {"distance": 2500, "duration": 300},
                    ],
                }],
                "waypoints": [
                    {"waypoint_index": 0},
                    {"waypoint_index": 1},
                ],
            }
        )
        resultado = calcular_ruta_optima(
            {"lat": 41.387, "lon": 2.168},
            [{"lat": 41.390, "lon": 2.170, "nombre": "Mercadona", "supermercado": "Mercadona"}]
        )
        assert resultado is not None
        assert resultado["distancia_total_km"] == 5.0
        assert resultado["duracion_total_min"] == 10.0

    def test_ruta_sin_paradas(self):
        resultado = calcular_ruta_optima({"lat": 41.387, "lon": 2.168}, [])
        assert resultado is None
```

### `test_listas.py`

```python
"""Tests para los métodos de listas en DatabaseManager."""

# Testear con la misma estructura que test_db.py existente.
# Mockear la conexión a PostgreSQL o usar una BD de test.
# Cubrir: crear_lista, obtener_listas, añadir_producto_a_lista,
#         quitar_producto_de_lista, eliminar_lista, duplicar_lista,
#         cargar_lista_en_cesta.
```

---

## 8. Orden de implementación

Implementar en este orden para minimizar dependencias entre fases:

```
FASE 1: Listas (prioridad alta, base para todo lo demás)
├─ Paso 1.1: Tablas listas + lista_productos en init_db.py
├─ Paso 1.2: Métodos CRUD en database_db_manager.py
├─ Paso 1.3: Página 5_Listas.py con UI completa
├─ Paso 1.4: Botón "Añadir a lista" en Comparador, Histórico y app.py
├─ Paso 1.5: Tests test_listas.py
└─ Paso 1.6: Añadir color Condis a COLORES_SUPERMERCADO en styles.py

FASE 2: Envíos (rápida, datos estáticos)
├─ Paso 2.1: Tabla envios + datos iniciales en init_db.py
├─ Paso 2.2: Métodos de envío en database_db_manager.py
├─ Paso 2.3: Integrar en desglose de 4_Cesta.py
└─ Paso 2.4: Tests

FASE 3: Rutas (la más compleja, depende de la cesta)
├─ Paso 3.1: Crear routing.py con las tres funciones
├─ Paso 3.2: Tests test_routing.py (con mocks)
├─ Paso 3.3: Añadir folium + streamlit-folium a requirements.txt
├─ Paso 3.4: Integrar sección de ruta en 4_Cesta.py
└─ Paso 3.5: Probar con direcciones reales

FINAL: Documentación
├─ Actualizar README.md
├─ Actualizar arquitectura.md
└─ Actualizar CHANGELOG.md (v4.0.0)
```

---

## Notas para Claude Code

- **Paths:** el proyecto usa estructura plana. Los archivos de páginas (`5_Listas.py`) van en la raíz, no en `pages/`.
- **Imports:** usar `sys.path.insert(0, ...)` igual que en las otras páginas (ver `4_Cesta.py` líneas 5-12).
- **Estilos:** llamar a `inyectar_estilos()` al inicio de cada página nueva. Usar `encabezado()`, `fila_metricas()`, `estado_vacio()` de `components.py`.
- **Material Icons:** usar `material-icons-outlined` (ya incluido en `inyectar_estilos()`). Sin emojis.
- **Colores:** respetar `COLORES_SUPERMERCADO` de `styles.py`. Falta Condis (`#C0392B`).
- **DB:** todas las consultas van a PostgreSQL vía `psycopg2`. Usar `self._cursor()` que ya hace reconnect automático.
- **Session state:** la cesta actual funciona con `st.session_state['cesta']`. Las listas se persisten en BD, la cesta sigue siendo temporal en sesión.
- **User-Agent de Nominatim:** el desarrollador debe cambiar el email en `routing.py` antes de usar en producción.
- **Tests:** colocar en la raíz del proyecto junto a los demás test_*.py. Usar `sys.path.insert(0, ...)` para imports.
