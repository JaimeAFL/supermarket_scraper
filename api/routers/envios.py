"""api/routers/envios.py - Endpoints de costes de envío."""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db
from api.schemas import EnvioResponse

router = APIRouter(prefix="/api/v1/envios", tags=["envíos"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=list[EnvioResponse])
@limiter.limit("60/minute")
def listar_envios(
    request: Request,
    db=Depends(get_db),
):
    """Lista los costes de envío de todos los supermercados. Endpoint público."""
    df = db.obtener_envios()
    if df.empty:
        return []

    return [
        EnvioResponse(
            supermercado=row["supermercado"],
            coste_envio=float(row["coste_envio"]),
            umbral_gratis=row.get("umbral_gratis"),
            pedido_minimo=row.get("pedido_minimo"),
            notas=row.get("notas"),
        )
        for _, row in df.iterrows()
    ]


@router.get("/{supermercado}", response_model=EnvioResponse)
@limiter.limit("60/minute")
def obtener_envio(
    request: Request,
    supermercado: str,
    db=Depends(get_db),
):
    """Devuelve los datos de envío de un supermercado concreto. Endpoint público."""
    envio = db.obtener_envio_supermercado(supermercado)
    if not envio:
        raise HTTPException(
            status_code=404,
            detail=f"Supermercado '{supermercado}' no encontrado en datos de envío.",
        )
    return EnvioResponse(
        supermercado=envio["supermercado"],
        coste_envio=float(envio["coste_envio"]),
        umbral_gratis=envio.get("umbral_gratis"),
        pedido_minimo=envio.get("pedido_minimo"),
        notas=envio.get("notas"),
    )
