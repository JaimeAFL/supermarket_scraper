"""api/schemas.py - Modelos Pydantic para request/response de la API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Productos ─────────────────────────────────────────────────────────

class ProductoBase(BaseModel):
    id: int
    id_externo: str | None = None
    nombre: str
    supermercado: str
    tipo_producto: str | None = None
    marca: str | None = None
    categoria_normalizada: str | None = None
    formato_normalizado: str | None = None
    url: str | None = None
    url_imagen: str | None = None


class ProductoConPrecio(ProductoBase):
    precio: float | None = None
    precio_referencia: float | None = None
    unidad_referencia: str | None = None


class ProductoDetalle(ProductoConPrecio):
    nombre_normalizado: str | None = None
    categoria: str | None = None
    formato: str | None = None


class ProductoBusqueda(ProductoConPrecio):
    prioridad: int | None = None


class ProductoListado(BaseModel):
    total: int
    productos: list[ProductoConPrecio]


class ProductoBusquedaResponse(BaseModel):
    total: int
    productos: list[ProductoBusqueda]


# ── Precios ───────────────────────────────────────────────────────────

class PrecioRegistro(BaseModel):
    fecha: str
    precio: float
    precio_unidad: str | None = None


class HistoricoPreciosResponse(BaseModel):
    producto_id: int
    registros: list[PrecioRegistro]
    precio_min: float | None = None
    precio_max: float | None = None
    precio_actual: float | None = None


# ── Comparador ────────────────────────────────────────────────────────

class ProductoComparado(BaseModel):
    id: int
    nombre: str
    supermercado: str
    precio: float | None = None
    precio_referencia: float | None = None
    unidad_referencia: str | None = None
    formato_normalizado: str | None = None
    marca: str | None = None
    tipo_producto: str | None = None
    url: str | None = None
    url_imagen: str | None = None
    prioridad: int | None = None


class ResumenSupermercado(BaseModel):
    min: float | None = None
    max: float | None = None
    productos: int


class ComparadorResponse(BaseModel):
    query: str
    total: int
    productos: list[ProductoComparado]
    resumen_por_supermercado: dict[str, ResumenSupermercado]


class AlternativaResponse(BaseModel):
    id: int
    nombre: str
    supermercado: str
    formato_normalizado: str | None = None
    precio: float


# ── Favoritos ─────────────────────────────────────────────────────────

class FavoritoResponse(BaseModel):
    id: int
    nombre: str
    supermercado: str
    formato_normalizado: str | None = None
    tipo_producto: str | None = None
    marca: str | None = None
    categoria_normalizada: str | None = None
    url_imagen: str | None = None
    precio: float | None = None
    precio_referencia: float | None = None
    unidad_referencia: str | None = None
    fecha_agregado: str | None = None


class FavoritoCrear(BaseModel):
    producto_id: int


# ── Listas ────────────────────────────────────────────────────────────

class ListaResumen(BaseModel):
    id: int
    nombre: str
    etiqueta: str | None = None
    notas: str | None = None
    num_productos: int
    coste_total: float | None = None
    fecha_creacion: str | None = None
    fecha_actualizacion: str | None = None


class ListaCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    etiqueta: str = ""
    notas: str = ""


class ListaActualizar(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    etiqueta: str | None = None
    notas: str | None = None


class ListaDuplicar(BaseModel):
    nuevo_nombre: str = Field(..., min_length=1, max_length=100)


class ListaProductoAnadir(BaseModel):
    producto_id: int
    cantidad: int = Field(default=1, ge=1, le=99)


class ListaProductoCantidad(BaseModel):
    cantidad: int = Field(..., ge=1, le=99)


class ListaProductoDetalle(BaseModel):
    lista_producto_id: int
    producto_id: int
    nombre: str
    supermercado: str
    marca: str | None = None
    formato_normalizado: str | None = None
    categoria_normalizada: str | None = None
    url: str | None = None
    url_imagen: str | None = None
    precio: float | None = None
    precio_referencia: float | None = None
    unidad_referencia: str | None = None
    cantidad: int
    notas_producto: str | None = None


class ListaDetalleResponse(BaseModel):
    lista: ListaResumen
    productos: list[ListaProductoDetalle]


class CestaItem(BaseModel):
    producto_id: int
    nombre: str
    supermercado: str
    precio: float
    formato_normalizado: str | None = None
    marca: str | None = None
    url_imagen: str | None = None
    cantidad: int
    alternativa_id: int | None = None
    alternativa_nombre: str | None = None
    alternativa_super: str | None = None
    alternativa_precio: float | None = None


# ── Envíos ────────────────────────────────────────────────────────────

class EnvioResponse(BaseModel):
    supermercado: str
    coste_envio: float
    umbral_gratis: float | None = None
    pedido_minimo: float | None = None
    notas: str | None = None


# ── Estadísticas ──────────────────────────────────────────────────────

class EstadisticasResponse(BaseModel):
    total_productos: int
    total_registros_precios: int
    total_supermercados: int
    total_equivalencias: int
    productos_por_supermercado: dict[str, int]
    productos_por_categoria: dict[str, int]
    primera_captura: str | None = None
    ultima_captura: str | None = None
    dias_con_datos: int


class CategoriaResponse(BaseModel):
    nombre: str
    num_productos: int


# ── Rutas ─────────────────────────────────────────────────────────────

class GeocodificarRequest(BaseModel):
    direccion: str = Field(..., min_length=1)
    pais: str = "es"


class GeocodificarResponse(BaseModel):
    lat: float
    lon: float
    display_name: str


class SupermercadosCercanosRequest(BaseModel):
    lat: float
    lon: float
    supermercados: list[str] = Field(..., min_length=1)
    radio_metros: int = Field(default=5000, ge=500, le=20000)


class TiendaCercana(BaseModel):
    lat: float
    lon: float
    nombre: str
    direccion: str | None = None
    distancia_m: float


class SupermercadosCercanosResponse(BaseModel):
    tiendas: dict[str, list[TiendaCercana]]


class RutaOptimaRequest(BaseModel):
    direccion: str = Field(..., min_length=1)
    supermercados: list[str] = Field(..., min_length=1)
    radio_metros: int = Field(default=5000, ge=500, le=20000)
    modo: str = Field(default="driving", pattern="^(driving|walking|cycling)$")


class ParadaOrdenada(BaseModel):
    supermercado: str
    nombre: str
    lat: float
    lon: float
    distancia_m: float


class RutaOptimaResponse(BaseModel):
    origen: GeocodificarResponse
    paradas_ordenadas: list[ParadaOrdenada]
    distancia_total_km: float
    duracion_total_min: float
    geometria: list[list[float]] | None = None
