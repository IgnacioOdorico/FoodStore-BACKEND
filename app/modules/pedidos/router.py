import json
import math
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user, require_role
from app.core.security import decode_access_token
from app.core.database import engine
from app.modules.usuarios.schemas import UserPublic
from app.modules.pedidos.schemas import (
    PedidoCreate,
    PedidoPublic,
    PaginatedPedidos,
    AvanzarEstadoRequest,
    CancelarRequest,
    HistorialPublic,
)
from app.modules.pedidos.service import PedidoService, EVENTOS_WS, ROLES_POR_TRANSICION, _pedido_to_ws_dict
from app.core.websocket import manager

router = APIRouter(prefix="/api/v1/pedidos", tags=["pedidos"])


@router.post("/", response_model=PedidoPublic, status_code=status.HTTP_201_CREATED)
async def crear_pedido(
    data: PedidoCreate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        result = PedidoService(uow).crear_pedido(current_user.id, data)
    
    await manager.broadcast_to_order(result.id, "PEDIDO_NUEVO", _pedido_to_ws_dict(result))
    roles_a_notificar = ROLES_POR_TRANSICION.get("PENDIENTE", [])
    if roles_a_notificar:
        await manager.broadcast_to_roles(roles_a_notificar, "PEDIDO_NUEVO", _pedido_to_ws_dict(result))
    return result


@router.get("/me", response_model=List[PedidoPublic])
def mis_pedidos(
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PedidoService(uow).listar_mis_pedidos(current_user.id)


@router.patch("/{pedido_id}/cancelar", response_model=PedidoPublic)
async def cancelar_mi_pedido(
    pedido_id: int,
    data: CancelarRequest,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        result = PedidoService(uow).cancelar_cliente(pedido_id, current_user.id, data.motivo)
    
    event_type = EVENTOS_WS.get("CANCELADO")
    if event_type:
        data_ws = _pedido_to_ws_dict(result)
        await manager.broadcast_to_order(pedido_id, event_type, data_ws)
        roles = ROLES_POR_TRANSICION.get("CANCELADO", [])
        if roles:
            await manager.broadcast_to_roles(roles, event_type, data_ws)
    return result


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



@router.get("/admin/listado", response_model=PaginatedPedidos)
def listar_todos_pedidos(
    _staff: Annotated[UserPublic, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    estado: Annotated[Optional[str], Query(description="Filtrar por estado_codigo")] = None,
    page: Annotated[int, Query(ge=1, description="Número de página")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Tamaño de página")] = 20,
):
    with uow:
        items, total = PedidoService(uow).listar_todos(estado_codigo=estado, page=page, size=size)
    pages = max(1, math.ceil(total / size))
    return PaginatedPedidos(items=items, total=total, page=page, size=size, pages=pages)


@router.patch("/{pedido_id}/avanzar", response_model=PedidoPublic)
async def avanzar_estado(
    pedido_id: int,
    data: AvanzarEstadoRequest,
    staff: Annotated[UserPublic, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        result = PedidoService(uow).avanzar_estado(
            pedido_id=pedido_id,
            estado_hacia=data.estado_hacia,
            usuario_id=staff.id,
            motivo=data.motivo,
        )
    
    event_type = EVENTOS_WS.get(data.estado_hacia)
    if event_type:
        data_ws = _pedido_to_ws_dict(result)
        await manager.broadcast_to_order(pedido_id, event_type, data_ws)
        roles = ROLES_POR_TRANSICION.get(data.estado_hacia, [])
        if roles:
            await manager.broadcast_to_roles(roles, event_type, data_ws)
    return result


STAFF_ROLES = {"ADMIN", "PEDIDOS"}

@router.websocket("/ws")
async def websocket_pedidos(
    websocket: WebSocket,
):
    from app.core.websocket import manager

    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token de autenticación requerido")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido o expirado")
        return

    email: str | None = payload.get("sub")
    if not email:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    with Session(engine) as db_session:
        from app.modules.usuarios.repository import UsuarioRepository
        repo = UsuarioRepository(db_session)
        user = repo.get_by_email(email)

        if not user:
            await websocket.accept()
            await websocket.close(code=1008, reason="Usuario no encontrado")
            return

        user_roles_set: set[str] = set(repo.get_roles_codes(user.id))
        user_id: int = user.id

        primary_role = "user"
        for r in ("ADMIN", "PEDIDOS", "COCINA"):
            if r in user_roles_set:
                primary_role = r.lower()
                break

    await manager.connect(websocket, role=primary_role, user_id=user_id)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")

            if action == "subscribe-order":
                order_id = msg.get("order_id")
                if not order_id or not isinstance(order_id, int):
                    continue

                is_staff = bool(user_roles_set.intersection(STAFF_ROLES))
                if not is_staff:
                    with Session(engine) as db_session:
                        from app.modules.pedidos.repository import PedidoRepository
                        pedido_repo = PedidoRepository(db_session)
                        pedido = pedido_repo.get_by_id(order_id)

                        if not pedido or pedido.deleted_at is not None or pedido.usuario_id != user_id:
                            await websocket.send_json({
                                "event": "ERROR",
                                "data": {"detail": "No autorizado para este pedido"}
                            })
                            continue

                manager.join_order_room(websocket, order_id)

                await websocket.send_json({
                    "event": "SUBSCRIBED",
                    "data": {"order_id": order_id}
                })

            elif action == "unsubscribe-order":
                order_id = msg.get("order_id")
                if order_id and isinstance(order_id, int):
                    manager.leave_order_room(websocket, order_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
