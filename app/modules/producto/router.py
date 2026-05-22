from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import require_role
from app.modules.usuarios.schemas import UserPublic
from app.modules.producto.schemas import (
    ProductoCreate,
    ProductoUpdate,
    ProductoDisponibilidadUpdate,
    ProductoReadWithDetails,
)
from app.modules.producto.service import ProductoService

router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])


@router.get("/", response_model=List[ProductoReadWithDetails])
def list_productos(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    nombre: Annotated[Optional[str], Query(description="Búsqueda por texto en nombre")] = None,
    disponible: Annotated[Optional[bool], Query(description="Filtrar por disponibilidad")] = None,
    categoria_id: Annotated[Optional[int], Query(description="Filtrar por categoría")] = None,
    skip: Annotated[int, Query(ge=0, description="Paginación: offset")] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description="Paginación: tamaño página")] = 50,
):
    with uow:
        return ProductoService(uow).list_productos(
            nombre=nombre,
            disponible=disponible,
            categoria_id=categoria_id,
            skip=skip,
            limit=limit,
        )


@router.get("/{id}", response_model=ProductoReadWithDetails)
def get_producto(
    id: int,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        producto = ProductoService(uow).get_producto(id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto


@router.post("/", response_model=ProductoReadWithDetails, status_code=status.HTTP_201_CREATED)
def create_producto(
    data: ProductoCreate,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Solo ADMIN puede crear."""
    with uow:
        return ProductoService(uow).create_producto(data)


@router.patch("/{id}", response_model=ProductoReadWithDetails)
def update_producto(
    id: int,
    data: ProductoUpdate,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Solo ADMIN puede actualizar."""
    with uow:
        producto = ProductoService(uow).update_producto(id, data)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto


@router.patch("/{id}/disponibilidad", response_model=ProductoReadWithDetails)
def patch_disponibilidad(
    id: int,
    data: ProductoDisponibilidadUpdate,
    _user: Annotated[UserPublic, Depends(require_role(["ADMIN", "STOCK"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """ADMIN o STOCK pueden alternar disponibilidad."""
    with uow:
        return ProductoService(uow).set_disponibilidad(id, data.disponible)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_producto(
    id: int,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Soft delete. Solo ADMIN."""
    with uow:
        success = ProductoService(uow).delete_producto(id)
    if not success:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
