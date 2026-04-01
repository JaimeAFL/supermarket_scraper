"""api/routers/precios.py - Endpoint de histórico de precios."""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db, verify_api_key
from api.schemas import PrecioRegistro, HistoricoPreciosResponse

router = APIRouter(prefix="/api/v1/productos", tags=["precios"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{producto_id}/precios", response_model=HistoricoPreciosResponse)
@limiter.limit("60/minute")
def obtener_historico_precios(
    request: Request,
    producto_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Devuelve el histórico de precios de un producto."""
    producto = db.obtener_producto_por_id(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado.")

    df = db.obtener_historico_precios(producto_id)
    if df.empty:
        return HistoricoPreciosResponse(
            producto_id=producto_id, registros=[],
            precio_min=None, precio_max=None, precio_actual=None,
        )

    registros = [
        PrecioRegistro(
            fecha=str(row["fecha_captura"]),
            precio=float(row["precio"]),
            precio_unidad=row.get("precio_unidad"),
        )
        for _, row in df.iterrows()
    ]
    precios = df["precio"].dropna().tolist()
    return HistoricoPreciosResponse(
        producto_id=producto_id,
        registros=registros,
        precio_min=min(precios) if precios else None,
        precio_max=max(precios) if precios else None,
        precio_actual=precios[-1] if precios else None,
    )
