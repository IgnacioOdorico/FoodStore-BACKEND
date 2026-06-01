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
    AvanzarEstadoRequest,
    CancelarRequest,
    HistorialPublic,
)
from app.modules.pedidos.service import PedidoService

router = APIRouter(prefix="/api/v1/pedidos", tags=["pedidos"])


@router.post("/", response_model=PedidoPublic, status_code=status.HTTP_201_CREATED)
async def crear_pedido(
    data: PedidoCreate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return await PedidoService(uow).crear_pedido(current_user.id, data)


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
        return await PedidoService(uow).cancelar_cliente(pedido_id, current_user.id, data.motivo)


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
async def avanzar_estado(
    pedido_id: int,
    data: AvanzarEstadoRequest,
    staff: Annotated[UserPublic, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return await PedidoService(uow).avanzar_estado(
            pedido_id=pedido_id,
            estado_hacia=data.estado_hacia,
            usuario_id=staff.id,
            motivo=data.motivo,
        )


# ─── WebSocket — actualizaciones en tiempo real ──────────────────────────────

WS_ROLES = {"ADMIN", "PEDIDOS"}


@router.websocket("/ws")
async def websocket_pedidos(
    websocket: WebSocket,
):
    # WebSocket /api/v1/pedidos/ws — canal bidireccional para tiempo real.
    #
    # Flujo de seguridad en el handshake:
    #   1. Obtiene token JWT desde cookie HttpOnly "access_token"
    #   2. Decodifica y valida firma + expiración
    #   3. Extrae email del claim "sub" y busca usuario en BD
    #   4. Verifica que tenga rol ADMIN o PEDIDOS
    #   5. Registra en ConnectionManager para recibir broadcasts
    #   6. Mantiene conexión abierta escuchando desconexiones

    from app.core.websocket import manager

    # 1. Token desde cookie HttpOnly
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token de autenticación requerido")
        return

    # 2. Decodificar y validar JWT
    payload = decode_access_token(token)
    if not payload:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido o expirado")
        return

    # 3. Extraer email (claim 'sub') y buscar usuario en BD
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

        # 4. Verificar rol — usa get_roles_codes() que ya existe en el repo
        user_roles = set(repo.get_roles_codes(user.id))
        if not user_roles.intersection(WS_ROLES):
            await websocket.accept()
            await websocket.close(code=1008, reason="Permisos insuficientes")
            return

    # 5. Registrar y mantener conexión
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # detecta desconexiones
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
