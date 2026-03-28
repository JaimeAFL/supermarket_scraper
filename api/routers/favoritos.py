"""api/routers/favoritos.py - Endpoints de favoritos."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db, verify_api_key
from api.schemas import FavoritoResponse, FavoritoCrear

router = APIRouter(prefix="/api/v1/favoritos", tags=["favoritos"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=list[FavoritoResponse])
@limiter.limit("60/minute")
def listar_favoritos(
    request: Request,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Lista todos los productos marcados como favoritos."""
    df = db.obtener_favoritos()
    if df.empty:
        return []

    return [
        FavoritoResponse(
            id=int(row["id"]),
            nombre=row["nombre"],
            supermercado=row["supermercado"],
            formato_normalizado=row.get("formato_normalizado"),
            tipo_producto=row.get("tipo_producto"),
            marca=row.get("marca"),
            categoria_normalizada=row.get("categoria_normalizada"),
            url_imagen=row.get("url_imagen"),
            precio=row.get("precio"),
            precio_referencia=row.get("precio_referencia"),
            unidad_referencia=row.get("unidad_referencia"),
            fecha_agregado=row.get("fecha_agregado"),
        )
        for _, row in df.iterrows()
    ]


@router.post("", status_code=201)
@limiter.limit("20/minute")
def agregar_favorito(
    request: Request,
    body: FavoritoCrear,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Añade un producto a favoritos."""
    producto = db.obtener_producto_por_id(body.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {body.producto_id} no encontrado.")
    db.agregar_favorito(body.producto_id)
    return {"detail": "Favorito añadido.", "producto_id": body.producto_id}


@router.delete("/{producto_id}", status_code=204)
@limiter.limit("20/minute")
def eliminar_favorito(
    request: Request,
    producto_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Elimina un producto de favoritos."""
    db.eliminar_favorito(producto_id)
    return Response(status_code=204)
