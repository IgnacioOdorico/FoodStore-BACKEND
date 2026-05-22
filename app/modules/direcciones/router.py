from typing import Annotated, List

from fastapi import APIRouter, Depends, status

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user
from app.modules.usuarios.schemas import UserPublic
from app.modules.direcciones.schemas import (
    DireccionCreate,
    DireccionUpdate,
    DireccionPublic,
)
from app.modules.direcciones.service import DireccionService

router = APIRouter(prefix="/api/v1/direcciones", tags=["direcciones"])


@router.get("/", response_model=List[DireccionPublic])
def listar_mis_direcciones(
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return DireccionService(uow).list_mine(current_user.id)


@router.get("/{direccion_id}", response_model=DireccionPublic)
def obtener_direccion(
    direccion_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return DireccionService(uow).get_mine(current_user.id, direccion_id)


@router.post("/", response_model=DireccionPublic, status_code=status.HTTP_201_CREATED)
def crear_direccion(
    data: DireccionCreate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return DireccionService(uow).create(current_user.id, data)


@router.patch("/{direccion_id}", response_model=DireccionPublic)
def actualizar_direccion(
    direccion_id: int,
    data: DireccionUpdate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return DireccionService(uow).update(current_user.id, direccion_id, data)


@router.patch("/{direccion_id}/principal", response_model=DireccionPublic)
def marcar_principal(
    direccion_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return DireccionService(uow).set_principal(current_user.id, direccion_id)


@router.delete("/{direccion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_direccion(
    direccion_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        DireccionService(uow).delete(current_user.id, direccion_id)
