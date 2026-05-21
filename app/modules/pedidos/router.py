from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user, require_role
from app.modules.usuarios.model import UserPublic
from app.modules.pedidos.models import (
    PedidoCreate,
    PedidoPublic,
    AvanzarEstadoRequest,
    CancelarRequest,
    HistorialPublic,
)
from app.modules.pedidos.service import PedidoService

router = APIRouter(prefix="/api/v1/pedidos", tags=["pedidos"])


@router.post("/", response_model=PedidoPublic, status_code=status.HTTP_201_CREATED)
def crear_pedido(
    data: PedidoCreate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PedidoService(uow).crear_pedido(current_user.id, data)


@router.get("/me", response_model=List[PedidoPublic])
def mis_pedidos(
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PedidoService(uow).listar_mis_pedidos(current_user.id)


@router.patch("/{pedido_id}/cancelar", response_model=PedidoPublic)
def cancelar_mi_pedido(
    pedido_id: int,
    data: CancelarRequest,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PedidoService(uow).cancelar_cliente(pedido_id, current_user.id, data.motivo)


@router.get("/{pedido_id}", response_model=PedidoPublic)
def obtener_pedido(
    pedido_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PedidoService(uow).get_pedido_para_usuario(
            pedido_id, current_user.id, current_user.roles
        )


@router.get("/{pedido_id}/historial", response_model=List[HistorialPublic])
def obtener_historial(
    pedido_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        pedido = PedidoService(uow).get_pedido_para_usuario(
            pedido_id, current_user.id, current_user.roles
        )
        return pedido.historial



@router.get("/admin/listado", response_model=List[PedidoPublic])
def listar_todos_pedidos(
    _staff: Annotated[UserPublic, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    estado: Annotated[Optional[str], Query(description="Filtrar por estado_codigo")] = None,
):
    with uow:
        return PedidoService(uow).listar_todos(estado_codigo=estado)


@router.patch("/{pedido_id}/avanzar", response_model=PedidoPublic)
def avanzar_estado(
    pedido_id: int,
    data: AvanzarEstadoRequest,
    staff: Annotated[UserPublic, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PedidoService(uow).avanzar_estado(
            pedido_id=pedido_id,
            estado_hacia=data.estado_hacia,
            usuario_id=staff.id,
            motivo=data.motivo,
        )
