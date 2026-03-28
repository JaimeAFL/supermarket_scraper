"""api/routers/productos.py - Endpoints de productos."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db, verify_api_key
from api.schemas import (
    ProductoConPrecio,
    ProductoDetalle,
    ProductoBusqueda,
    ProductoListado,
    ProductoBusquedaResponse,
)

router = APIRouter(prefix="/api/v1/productos", tags=["productos"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=ProductoListado)
@limiter.limit("60/minute")
def listar_productos(
    request: Request,
    supermercado: str | None = Query(None, description="Filtrar por supermercado"),
    limite: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Lista productos con su precio más reciente."""
    df = db.obtener_productos_con_precio_actual(supermercado)
    total = len(df)
    if df.empty:
        return ProductoListado(total=0, productos=[])

    df = df.iloc[offset:offset + limite]
    productos = []
    for _, row in df.iterrows():
        productos.append(ProductoConPrecio(
            id=int(row["id"]),
            id_externo=row.get("retailer_id"),
            nombre=row["nombre"],
            supermercado=row["supermercado"],
            tipo_producto=row.get("tipo_producto"),
            marca=row.get("marca"),
            categoria_normalizada=row.get("categoria_normalizada"),
            formato_normalizado=row.get("formato_normalizado"),
            url=row.get("url"),
            url_imagen=row.get("url_imagen"),
            precio=row.get("precio"),
            precio_referencia=row.get("precio_referencia"),
            unidad_referencia=row.get("unidad_referencia"),
        ))
    return ProductoListado(total=total, productos=productos)


@router.get("/buscar", response_model=ProductoBusquedaResponse)
@limiter.limit("60/minute")
def buscar_productos(
    request: Request,
    q: str = Query(..., min_length=1, description="Texto de búsqueda"),
    supermercado: str | None = Query(None),
    limite: int = Query(25, ge=1, le=200),
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Búsqueda inteligente: prioriza tipo_producto, luego nombre completo."""
    df = db.buscar_productos(nombre=q, supermercado=supermercado, limite=limite)
    if df.empty:
        return ProductoBusquedaResponse(total=0, productos=[])

    productos = []
    for _, row in df.iterrows():
        productos.append(ProductoBusqueda(
            id=int(row["id"]),
            nombre=row["nombre"],
            supermercado=row["supermercado"],
            tipo_producto=row.get("tipo_producto"),
            marca=row.get("marca"),
            categoria_normalizada=row.get("categoria_normalizada"),
            formato_normalizado=row.get("formato_normalizado"),
            precio=row.get("precio"),
            prioridad=row.get("prioridad"),
        ))
    return ProductoBusquedaResponse(total=len(productos), productos=productos)


@router.get("/{producto_id}", response_model=ProductoDetalle)
@limiter.limit("60/minute")
def obtener_producto(
    request: Request,
    producto_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Detalle completo de un producto con su precio actual."""
    producto = db.obtener_producto_por_id(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado.")
    return ProductoDetalle(
        id=producto["id"],
        id_externo=producto.get("id_externo"),
        nombre=producto["nombre"],
        supermercado=producto["supermercado"],
        tipo_producto=producto.get("tipo_producto"),
        marca=producto.get("marca"),
        nombre_normalizado=producto.get("nombre_normalizado"),
        categoria_normalizada=producto.get("categoria_normalizada"),
        formato_normalizado=producto.get("formato_normalizado"),
        url=producto.get("url"),
        url_imagen=producto.get("url_imagen"),
        precio=producto.get("precio"),
        precio_referencia=producto.get("precio_referencia"),
        unidad_referencia=producto.get("unidad_referencia"),
    )
