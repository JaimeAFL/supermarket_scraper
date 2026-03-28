"""api/routers/estadisticas.py - Endpoints de estadísticas y categorías."""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db
from api.schemas import EstadisticasResponse, CategoriaResponse

router = APIRouter(prefix="/api/v1", tags=["estadísticas"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/estadisticas", response_model=EstadisticasResponse)
@limiter.limit("60/minute")
def obtener_estadisticas(
    request: Request,
    db=Depends(get_db),
):
    """Métricas globales de la base de datos. Endpoint público."""
    stats = db.obtener_estadisticas()
    return EstadisticasResponse(
        total_productos=stats["total_productos"],
        total_registros_precios=stats["total_registros_precios"],
        total_supermercados=stats["total_supermercados"],
        total_equivalencias=stats["total_equivalencias"],
        productos_por_supermercado=stats["productos_por_supermercado"],
        productos_por_categoria=stats.get("productos_por_categoria", {}),
        primera_captura=stats.get("primera_captura"),
        ultima_captura=stats.get("ultima_captura"),
        dias_con_datos=stats.get("dias_con_datos", 0),
    )


@router.get("/categorias", response_model=list[CategoriaResponse])
@limiter.limit("60/minute")
def listar_categorias(
    request: Request,
    db=Depends(get_db),
):
    """Lista las categorías normalizadas con el número de productos. Endpoint público."""
    categorias = db.obtener_categorias()
    return [
        CategoriaResponse(nombre=nombre, num_productos=cnt)
        for nombre, cnt in categorias
    ]
