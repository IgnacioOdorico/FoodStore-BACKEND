from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user, require_role
from app.modules.usuarios.schemas import UserPublic
from app.modules.categorias.schemas import CategoriaCreate, CategoriaUpdate, CategoriaPublic, PaginatedCategorias
from app.modules.categorias.service import CategoriaService

router = APIRouter(prefix="/api/v1/categorias", tags=["categorias"])


@router.get("/", response_model=PaginatedCategorias)
def list_categorias(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    parent_id: Annotated[
        Optional[int],
        Query(description="Filtrar por categoría padre (None = raíz)"),
    ] = None,
    skip: Annotated[int, Query(ge=0, description="Registros a saltear")] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description="Registros por página")] = 100,
):
    with uow:
        return CategoriaService(uow).list_all(parent_id=parent_id, skip=skip, limit=limit)


@router.get("/{categoria_id}", response_model=CategoriaPublic)
def get_categoria(
    categoria_id: int,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return CategoriaService(uow).get_by_id(categoria_id)


@router.post(
    "/",
    response_model=CategoriaPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_categoria(
    cat_in: CategoriaCreate,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return CategoriaService(uow).create(cat_in)


@router.patch("/{categoria_id}", response_model=CategoriaPublic)
def update_categoria(
    categoria_id: int,
    cat_in: CategoriaUpdate,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return CategoriaService(uow).update(categoria_id, cat_in)


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_categoria(
    categoria_id: int,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        CategoriaService(uow).delete(categoria_id)
