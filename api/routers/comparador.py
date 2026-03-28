"""api/routers/comparador.py - Endpoints del comparador de precios."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db, verify_api_key
from api.schemas import (
    ProductoComparado,
    ResumenSupermercado,
    ComparadorResponse,
    AlternativaResponse,
)

router = APIRouter(prefix="/api/v1", tags=["comparador"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/comparar", response_model=ComparadorResponse)
@limiter.limit("60/minute")
def comparar_precios(
    request: Request,
    q: str = Query(..., min_length=1, description="Texto de búsqueda"),
    limite_por_super: int = Query(30, ge=1, le=100),
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Compara precios unitarios entre supermercados para un producto."""
    df = db.buscar_para_comparar(q, limite_por_super=limite_por_super)
    if df.empty:
        return ComparadorResponse(
            query=q, total=0, productos=[], resumen_por_supermercado={},
        )

    productos = []
    for _, row in df.iterrows():
        productos.append(ProductoComparado(
            id=int(row["id"]),
            nombre=row["nombre"],
            supermercado=row["supermercado"],
            precio=row.get("precio"),
            precio_referencia=row.get("precio_referencia"),
            unidad_referencia=row.get("unidad_referencia"),
            formato_normalizado=row.get("formato_normalizado"),
            marca=row.get("marca"),
            tipo_producto=row.get("tipo_producto"),
            url=row.get("url"),
            url_imagen=row.get("url_imagen"),
            prioridad=row.get("prioridad"),
        ))

    # Resumen por supermercado
    resumen: dict[str, ResumenSupermercado] = {}
    for _, row in df.iterrows():
        s = row["supermercado"]
        p = row.get("precio")
        if s not in resumen:
            resumen[s] = {"min": p, "max": p, "count": 0}
        if p is not None:
            if resumen[s]["min"] is None or p < resumen[s]["min"]:
                resumen[s]["min"] = p
            if resumen[s]["max"] is None or p > resumen[s]["max"]:
                resumen[s]["max"] = p
        resumen[s]["count"] += 1

    resumen_response = {
        s: ResumenSupermercado(min=v["min"], max=v["max"], productos=v["count"])
        for s, v in resumen.items()
    }

    return ComparadorResponse(
        query=q,
        total=len(productos),
        productos=productos,
        resumen_por_supermercado=resumen_response,
    )


@router.get("/productos/{producto_id}/alternativa", response_model=AlternativaResponse)
@limiter.limit("60/minute")
def obtener_alternativa(
    request: Request,
    producto_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Busca la alternativa más barata en otro supermercado."""
    producto = db.obtener_producto_por_id(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado.")

    alt = db.buscar_alternativa_mas_barata(producto_id)
    if not alt:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró alternativa más barata para el producto {producto_id}.",
        )
    return AlternativaResponse(
        id=alt["id"],
        nombre=alt["nombre"],
        supermercado=alt["supermercado"],
        formato_normalizado=alt.get("formato_normalizado"),
        precio=alt["precio"],
    )
