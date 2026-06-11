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
        return await PedidoService(uow).avanzar_estado(
            pedido_id=pedido_id,
            estado_hacia=data.estado_hacia,
            usuario_id=staff.id,
            motivo=data.motivo,
        )


# =============================================================================
# WEBSOCKET — CANAL BIDIRECCIONAL CON ROOMS POR ROL Y POR PEDIDO
# =============================================================================
#
# ─── PROTOCOLO ────────────────────────────────────────────────────────────────
#
# El protocolo sobre WebSocket es JSON bidireccional:
#
#   Cliente → Backend (acciones):
#     {"action": "subscribe-order",   "order_id": 5}
#     {"action": "unsubscribe-order", "order_id": 5}
#
#   Backend → Cliente (eventos):
#     {"event": "PEDIDO_NUEVO",          "data": {...}}
#     {"event": "PEDIDO_CONFIRMADO",     "data": {...}}
#     {"event": "PEDIDO_EN_PREPARACION", "data": {...}}
#     {"event": "PEDIDO_EN_CAMINO",      "data": {...}}
#     {"event": "PEDIDO_CANCELADO",      "data": {...}}
#     {"event": "PEDIDO_ENTREGADO",      "data": {...}}
#     {"event": "SUBSCRIBED",            "data": {"order_id": 5}}
#     {"event": "ERROR",                 "data": {"detail": "..."}}
#
# ─── AUTENTICACIÓN ────────────────────────────────────────────────────────────
#
# El WebSocket NO soporta headers personalizados en el handshake desde el
# navegador. Por eso usamos cookies HttpOnly:
#   1. El frontend hace login via REST: POST /api/v1/auth/token
#   2. El backend setea una cookie HttpOnly con el JWT
#   3. Al abrir el WebSocket, el browser envía la cookie automáticamente
#   4. El backend lee el JWT de la cookie y lo valida
#
# ─── ROLES Y ROOMS ────────────────────────────────────────────────────────────
#
# Cualquier usuario autenticado puede conectarse. La diferencia está en
# qué room se le asigna y qué eventos recibe:
#
#   STAFF (ADMIN, PEDIDOS, COCINA):
#     - Se une a "role:{rol}" y recibe todos los eventos de su área
#     - Puede suscribirse a pedidos específicos también
#
#   CLIENTE (USER):
#     - Se une a "role:user" pero no recibe broadcasts generales
#     - Debe suscribirse a sus pedidos via subscribe-order
#     - Solo puede suscribirse a pedidos que le pertenecen
#
# ─── CÓDIGOS DE CIERRE WebSocket ─────────────────────────────────────────────
#
#   1000 → Close normal
#   1008 → Policy Violation (token inválido, usuario inactivo)
#   1001 → Going Away (cliente se desconecta voluntariamente)
#
# =============================================================================

# Roles de staff que pueden gestionar pedidos.
# Se usan para decidir si se valida propiedad del pedido en subscribe-order.
STAFF_ROLES = {"ADMIN", "PEDIDOS"}



@router.websocket("/ws")
async def websocket_pedidos(
    websocket: WebSocket,
):
    """
    WebSocket /api/v1/pedidos/ws — Canal bidireccional autenticado para tiempo real.

    Flujo completo:
      1. Handshake: valida JWT desde cookie HttpOnly
      2. Conexión: une el socket a la room de su rol (role:{rol})
      3. Escucha: procesa suscripciones a pedidos específicos
      4. Desconexión: limpia todas las rooms del socket
    """
    from app.core.websocket import manager

    # =========================================================================
    # PASO 1: EXTRAER TOKEN DE LA COOKIE HTTPONLY
    # =========================================================================
    # El browser envía automáticamente las cookies en el handshake WebSocket.
    # La cookie "access_token" contiene el JWT firmado.
    #
    # ¿Por qué cookie y no header?
    #   - El API WebSocket del navegador NO permite configurar headers
    #   - Las cookies HttpOnly no son accesibles desde JavaScript (protección XSS)
    #   - SameSite=lax previene ataques CSRF
    #
    token = websocket.cookies.get("access_token")
    if not token:
        # Sin token → rechazar con código 1008 (Policy Violation)
        # IMPORTANTE: debemos aceptar ANTES de close para que el cliente
        # reciba el código y la razón del rechazo
        await websocket.accept()
        await websocket.close(code=1008, reason="Token de autenticación requerido")
        return

    # =========================================================================
    # PASO 2: DECODIFICAR Y VALIDAR EL JWT
    # =========================================================================
    # decode_access_token() valida:
    #   - La firma HMAC (que no fue manipulado)
    #   - La expiración (exp claim)
    #   - Retorna el payload o None si es inválido
    #
    payload = decode_access_token(token)
    if not payload:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido o expirado")
        return

    # Extraer el "sub" del token — en este proyecto es el email del usuario
    email: str | None = payload.get("sub")
    if not email:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    # =========================================================================
    # PASO 3: VALIDAR USUARIO EN BASE DE DATOS
    # =========================================================================
    # Aunque el JWT sea válido, el usuario podría haber sido eliminado o
    # desactivado. Siempre validamos contra la BD para tener datos actuales.
    #
    # NOTA: Cualquier rol autenticado puede conectarse al WebSocket.
    # La diferenciación se hace via rooms:
    #   - role:admin   → recibe todos los eventos de administración
    #   - role:pedidos → recibe eventos de caja y gestión de pedidos
    #   - role:cocina  → recibe eventos de preparación
    #   - role:user    → solo recibe eventos de sus pedidos (via subscribe-order)
    #
    with Session(engine) as db_session:
        from app.modules.usuarios.repository import UsuarioRepository
        repo = UsuarioRepository(db_session)
        user = repo.get_by_email(email)

        if not user:
            await websocket.accept()
            await websocket.close(code=1008, reason="Usuario no encontrado")
            return

        # Extraer roles del usuario (multi-rol) y el ID.
        # Los roles están en uppercase (ej: ["ADMIN", "PEDIDOS"]).
        # Para la room usamos el primer rol en minúsculas; si tiene
        # múltiples roles de staff, el broadcast_to_roles cubre todos.
        user_roles_set: set[str] = set(repo.get_roles_codes(user.id))
        user_id: int = user.id

        # Determinar el rol principal para asignar la room inicial.
        # Prioridad: ADMIN > PEDIDOS > COCINA > USER (o el que venga)
        primary_role = "user"
        for r in ("ADMIN", "PEDIDOS", "COCINA"):
            if r in user_roles_set:
                primary_role = r.lower()
                break

    # =========================================================================
    # PASO 4: REGISTRAR EN EL CONNECTION MANAGER
    # =========================================================================
    # connect() acepta el handshake y une el socket a "role:{primary_role}"
    await manager.connect(websocket, role=primary_role, user_id=user_id)

    # =========================================================================
    # PASO 5: BUCLE DE ESCUCHA DE MENSAJES
    # =========================================================================
    # El WebSocket queda en un bucle infinito procesando mensajes del cliente.
    #
    # Soporta dos acciones:
    #   - subscribe-order:   suscribirse a actualizaciones de un pedido
    #   - unsubscribe-order: desuscribirse de un pedido
    #
    # El bucle se rompe con WebSocketDisconnect o con cualquier error.
    #
    try:
        while True:
            # Espera bloqueante: se rompe al recibir mensaje o al desconectar
            raw = await websocket.receive_text()

            # Parsear el mensaje JSON del cliente
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                # Mensaje malformado → ignorar y seguir escuchando
                continue

            action = msg.get("action")

            # ─── ACCIÓN: SUBSCRIBE-ORDER ──────────────────────────────────────
            # El cliente quiere suscribirse a las actualizaciones de un pedido.
            #
            # Para clientes (role:user):
            #   1. Valida que el pedido exista
            #   2. Valida que el pedido pertenezca al usuario
            #   3. Si es válido, une el socket a "order:{orderId}"
            #
            # Para staff (ADMIN/PEDIDOS/COCINA):
            #   Se suscribe directamente (el staff puede ver cualquier pedido)
            #
            if action == "subscribe-order":
                order_id = msg.get("order_id")
                if not order_id or not isinstance(order_id, int):
                    continue

                # Validación de propiedad: solo para clientes (no staff)
                is_staff = bool(user_roles_set.intersection(STAFF_ROLES))
                if not is_staff:
                    with Session(engine) as db_session:
                        from app.modules.pedidos.repository import PedidoRepository
                        pedido_repo = PedidoRepository(db_session)
                        pedido = pedido_repo.get_by_id(order_id)

                        # Validar que:
                        #   a. El pedido exista y no esté eliminado
                        #   b. El pedido pertenezca al usuario autenticado
                        if not pedido or pedido.deleted_at is not None or pedido.usuario_id != user_id:
                            await websocket.send_json({
                                "event": "ERROR",
                                "data": {"detail": "No autorizado para este pedido"}
                            })
                            continue

                # Todo válido → unir el socket a la room del pedido
                manager.join_order_room(websocket, order_id)

                # Confirmar al cliente que se suscribió exitosamente
                await websocket.send_json({
                    "event": "SUBSCRIBED",
                    "data": {"order_id": order_id}
                })

            # ─── ACCIÓN: UNSUBSCRIBE-ORDER ────────────────────────────────────
            # El cliente deja de escuchar un pedido específico.
            #
            elif action == "unsubscribe-order":
                order_id = msg.get("order_id")
                if order_id and isinstance(order_id, int):
                    manager.leave_order_room(websocket, order_id)

    except WebSocketDisconnect:
        # El cliente cerró la conexión limpiamente
        manager.disconnect(websocket)
    except Exception:
        # Error inesperado → limpiar la conexión
        manager.disconnect(websocket)
