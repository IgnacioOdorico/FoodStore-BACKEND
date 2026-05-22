from typing import Annotated, List

from fastapi import APIRouter, Depends, status

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user
from app.modules.usuarios.schemas import UserPublic
from app.modules.pagos.schemas import (
    PagoCreate,
    PagoPublic,
    PagoWebhookUpdate,
)
from app.modules.pagos.service import PagoService

router = APIRouter(prefix="/api/v1/pagos", tags=["pagos"])


@router.post("/", response_model=PagoPublic, status_code=status.HTTP_201_CREATED)
def crear_pago(
    data: PagoCreate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PagoService(uow).crear_pago(data, current_user.id)


@router.get("/pedido/{pedido_id}", response_model=List[PagoPublic])
def listar_pagos_de_pedido(
    pedido_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PagoService(uow).listar_por_pedido(
            pedido_id, current_user.id, current_user.roles
        )


@router.post("/webhook", response_model=PagoPublic)
def webhook_mercadopago(
    data: PagoWebhookUpdate,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):

    with uow:
        return PagoService(uow).webhook(data)
