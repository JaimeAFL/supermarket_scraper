"""api/routers/listas.py - Endpoints de listas de la compra."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_db, verify_api_key
from api.schemas import (
    ListaResumen,
    ListaCrear,
    ListaActualizar,
    ListaDuplicar,
    ListaProductoAnadir,
    ListaProductoCantidad,
    ListaProductoDetalle,
    ListaDetalleResponse,
    CestaItem,
)

router = APIRouter(prefix="/api/v1/listas", tags=["listas"])
limiter = Limiter(key_func=get_remote_address)


def _get_lista_or_404(db, lista_id: int) -> dict:
    """Verifica que una lista exista. Lanza 404 si no."""
    df = db.obtener_listas()
    if not df.empty:
        match = df[df["id"] == lista_id]
        if not match.empty:
            return match.iloc[0].to_dict()
    raise HTTPException(status_code=404, detail=f"Lista {lista_id} no encontrada.")


@router.get("", response_model=list[ListaResumen])
@limiter.limit("60/minute")
def listar_listas(
    request: Request,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Lista todas las listas de la compra con resumen."""
    df = db.obtener_listas()
    if df.empty:
        return []

    return [
        ListaResumen(
            id=int(row["id"]),
            nombre=row["nombre"],
            etiqueta=row.get("etiqueta"),
            notas=row.get("notas"),
            num_productos=int(row.get("num_productos", 0)),
            coste_total=float(row["coste_total"]) if row.get("coste_total") else None,
            fecha_creacion=row.get("fecha_creacion"),
            fecha_actualizacion=row.get("fecha_actualizacion"),
        )
        for _, row in df.iterrows()
    ]


@router.post("", response_model=ListaResumen, status_code=201)
@limiter.limit("20/minute")
def crear_lista(
    request: Request,
    body: ListaCrear,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Crea una nueva lista de la compra."""
    lista_id = db.crear_lista(body.nombre, body.etiqueta, body.notas)
    return ListaResumen(
        id=lista_id,
        nombre=body.nombre,
        etiqueta=body.etiqueta,
        notas=body.notas,
        num_productos=0,
        coste_total=0,
    )


@router.get("/{lista_id}", response_model=ListaDetalleResponse)
@limiter.limit("60/minute")
def obtener_lista(
    request: Request,
    lista_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Detalle de una lista con sus productos y precios actuales."""
    lista_data = _get_lista_or_404(db, lista_id)
    df = db.obtener_lista_detalle(lista_id)

    productos = []
    if not df.empty:
        for _, row in df.iterrows():
            productos.append(ListaProductoDetalle(
                lista_producto_id=int(row["lista_producto_id"]),
                producto_id=int(row["producto_id"]),
                nombre=row["nombre"],
                supermercado=row["supermercado"],
                marca=row.get("marca"),
                formato_normalizado=row.get("formato_normalizado"),
                categoria_normalizada=row.get("categoria_normalizada"),
                url=row.get("url"),
                url_imagen=row.get("url_imagen"),
                precio=row.get("precio"),
                precio_referencia=row.get("precio_referencia"),
                unidad_referencia=row.get("unidad_referencia"),
                cantidad=int(row.get("cantidad", 1)),
                notas_producto=row.get("notas_producto"),
            ))

    lista_resumen = ListaResumen(
        id=int(lista_data["id"]),
        nombre=lista_data["nombre"],
        etiqueta=lista_data.get("etiqueta"),
        notas=lista_data.get("notas"),
        num_productos=int(lista_data.get("num_productos", 0)),
        coste_total=float(lista_data["coste_total"]) if lista_data.get("coste_total") else None,
        fecha_creacion=lista_data.get("fecha_creacion"),
        fecha_actualizacion=lista_data.get("fecha_actualizacion"),
    )

    return ListaDetalleResponse(lista=lista_resumen, productos=productos)


@router.put("/{lista_id}", response_model=dict)
@limiter.limit("20/minute")
def actualizar_lista(
    request: Request,
    lista_id: int,
    body: ListaActualizar,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Actualiza nombre, etiqueta y/o notas de una lista."""
    _get_lista_or_404(db, lista_id)
    db.renombrar_lista(lista_id, body.nombre, body.etiqueta, body.notas)
    return {"detail": "Lista actualizada.", "lista_id": lista_id}


@router.delete("/{lista_id}", status_code=204)
@limiter.limit("20/minute")
def eliminar_lista(
    request: Request,
    lista_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Elimina una lista y todos sus productos."""
    _get_lista_or_404(db, lista_id)
    db.eliminar_lista(lista_id)
    return Response(status_code=204)


@router.post("/{lista_id}/duplicar", response_model=dict, status_code=201)
@limiter.limit("20/minute")
def duplicar_lista(
    request: Request,
    lista_id: int,
    body: ListaDuplicar,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Duplica una lista existente con un nuevo nombre."""
    _get_lista_or_404(db, lista_id)
    try:
        nuevo_id = db.duplicar_lista(lista_id, body.nuevo_nombre)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"detail": "Lista duplicada.", "nueva_lista_id": nuevo_id}


@router.post("/{lista_id}/productos", status_code=201)
@limiter.limit("20/minute")
def anadir_producto(
    request: Request,
    lista_id: int,
    body: ListaProductoAnadir,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Añade un producto a una lista (si ya existe, suma la cantidad)."""
    _get_lista_or_404(db, lista_id)
    producto = db.obtener_producto_por_id(body.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {body.producto_id} no encontrado.")
    ok = db.añadir_producto_a_lista(lista_id, body.producto_id, body.cantidad)
    if not ok:
        raise HTTPException(status_code=500, detail="Error al añadir producto a la lista.")
    return {"detail": "Producto añadido a la lista.", "lista_id": lista_id, "producto_id": body.producto_id}


@router.put("/{lista_id}/productos/{producto_id}", response_model=dict)
@limiter.limit("20/minute")
def actualizar_cantidad(
    request: Request,
    lista_id: int,
    producto_id: int,
    body: ListaProductoCantidad,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Actualiza la cantidad de un producto en una lista."""
    _get_lista_or_404(db, lista_id)
    ok = db.actualizar_cantidad_lista(lista_id, producto_id, body.cantidad)
    if not ok:
        raise HTTPException(status_code=500, detail="Error al actualizar cantidad.")
    return {"detail": "Cantidad actualizada.", "lista_id": lista_id, "producto_id": producto_id, "cantidad": body.cantidad}


@router.delete("/{lista_id}/productos/{producto_id}", status_code=204)
@limiter.limit("20/minute")
def quitar_producto(
    request: Request,
    lista_id: int,
    producto_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Elimina un producto de una lista."""
    _get_lista_or_404(db, lista_id)
    db.quitar_producto_de_lista(lista_id, producto_id)
    return Response(status_code=204)


@router.get("/{lista_id}/cesta", response_model=list[CestaItem])
@limiter.limit("60/minute")
def cargar_cesta(
    request: Request,
    lista_id: int,
    _auth=Depends(verify_api_key),
    db=Depends(get_db),
):
    """Carga una lista como cesta de la compra (con formato compatible con el dashboard)."""
    _get_lista_or_404(db, lista_id)
    items = db.cargar_lista_en_cesta(lista_id)
    return [
        CestaItem(
            producto_id=item["producto_id"],
            nombre=item["nombre"],
            supermercado=item["supermercado"],
            precio=item["precio"],
            formato_normalizado=item.get("formato_normalizado"),
            marca=item.get("marca"),
            url_imagen=item.get("url_imagen"),
            cantidad=item["cantidad"],
            alternativa_id=item.get("alternativa_id"),
            alternativa_nombre=item.get("alternativa_nombre"),
            alternativa_super=item.get("alternativa_super"),
            alternativa_precio=item.get("alternativa_precio"),
        )
        for item in items
    ]
