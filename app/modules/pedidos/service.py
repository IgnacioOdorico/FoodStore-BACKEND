from datetime import datetime, timezone
from typing import Any, List, Optional, Set, Tuple

from fastapi import HTTPException, status

from app.core.uow import UnitOfWork
from app.modules.pedidos.models import (
    Pedido,
    DetallePedido,
    HistorialEstadoPedido,
)
from app.modules.pedidos.schemas import (
    PedidoCreate,
    PedidoPublic,
    PaginatedPedidos,
    DetallePedidoPublic,
    HistorialPublic,
)


EVENTOS_WS: dict[str, str] = {
    "PENDIENTE": "PEDIDO_NUEVO",
    "CONFIRMADO": "PEDIDO_CONFIRMADO",
    "EN_PREP": "PEDIDO_EN_PREPARACION",
    "ENTREGADO": "PEDIDO_ENTREGADO",
    "CANCELADO": "PEDIDO_CANCELADO",
}

ROLES_POR_TRANSICION: dict[str, list[str]] = {
    "PENDIENTE": ["PEDIDOS", "ADMIN"],
    "CONFIRMADO": ["PEDIDOS", "ADMIN"],
    "EN_PREP": ["PEDIDOS", "ADMIN"],
    "ENTREGADO": ["PEDIDOS", "ADMIN"],
    "CANCELADO": ["PEDIDOS", "ADMIN"],
}


FSM: dict[str, Set[str]] = {
    "PENDIENTE": {"CONFIRMADO", "CANCELADO"},
    "CONFIRMADO": {"EN_PREP", "CANCELADO"},
    "EN_PREP": {"ENTREGADO", "CANCELADO"},
    "ENTREGADO": set(),  # terminal
    "CANCELADO": set(),  # terminal
}

ESTADOS_CANCELABLES_POR_CLIENTE = {"PENDIENTE", "CONFIRMADO"}


class PedidoService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def crear_pedido(self, usuario_id: int, data: PedidoCreate) -> PedidoPublic:

        fp = self.uow.formas_pago.get_by_codigo(data.forma_pago_codigo)
        if not fp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Forma de pago '{data.forma_pago_codigo}' inexistente",
            )
        if not fp.habilitado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La forma de pago '{fp.codigo}' está deshabilitada",
            )

        if data.direccion_id is not None:
            direccion = self.uow.direcciones.get_by_id(data.direccion_id)
            if (
                not direccion
                or direccion.deleted_at is not None
                or direccion.usuario_id != usuario_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Dirección inválida o no pertenece al usuario",
                )

        items: list[DetallePedido] = []
        subtotal = 0.0
        for it in data.detalles:
            producto = self.uow.productos.get_by_id(it.producto_id)
            if not producto or producto.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Producto {it.producto_id} no encontrado",
                )
            if not producto.disponible:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El producto '{producto.nombre}' no está disponible",
                )

            if producto.stock_cantidad < it.cantidad:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock insuficiente para el producto '{producto.nombre}'",
                )

            # Descontar stock
            producto.stock_cantidad -= it.cantidad
            if producto.stock_cantidad == 0:
                producto.disponible = False
            self.uow.productos.update(producto)

            sub = float(producto.precio_base) * it.cantidad
            items.append(
                DetallePedido(
                    producto_id=producto.id,
                    cantidad=it.cantidad,
                    nombre_snapshot=producto.nombre,
                    precio_snapshot=float(producto.precio_base),
                    subtotal_snap=sub,
                    personalizacion=it.personalizacion,
                )
            )
            subtotal += sub

        total = subtotal - float(data.descuento) + float(data.costo_envio)
        if total < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El total no puede ser negativo",
            )

        # 3. INSERT Pedido (estado inicial PENDIENTE)
        pedido = Pedido(
            usuario_id=usuario_id,
            direccion_id=data.direccion_id,
            estado_codigo="PENDIENTE",
            forma_pago_codigo=fp.codigo,
            subtotal=subtotal,
            descuento=float(data.descuento),
            costo_envio=float(data.costo_envio),
            total=total,
            notas=data.notas,
        )
        self.uow.pedidos.add(pedido)
        self.uow.session.flush()

        # 4. INSERT detalles
        for d in items:
            d.pedido_id = pedido.id
            self.uow.session.add(d)

        # 5. INSERT en audit trail de estados
        self.uow.historial_pedidos.add(
            HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_desde=None,
                estado_hacia="PENDIENTE",
                usuario_id=usuario_id,
                motivo="Creación del pedido",
            )
        )

        result = self._to_public(pedido.id)

        from app.core.websocket import manager

        await manager.broadcast_to_order(
            pedido.id, "PEDIDO_NUEVO", _pedido_to_ws_dict(result)
        )
        roles_a_notificar = ROLES_POR_TRANSICION.get("PENDIENTE", [])
        if roles_a_notificar:
            await manager.broadcast_to_roles(
                roles_a_notificar, "PEDIDO_NUEVO", _pedido_to_ws_dict(result)
            )

        return result

    async def avanzar_estado(
        self,
        pedido_id: int,
        estado_hacia: str,
        usuario_id: Optional[int],
        motivo: Optional[str],
    ) -> PedidoPublic:

        pedido = self._get_pedido_or_404(pedido_id)

        estado_desde = pedido.estado_codigo
        permitidos = FSM.get(estado_desde, set())

        if estado_hacia not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transición inválida: {estado_desde} → {estado_hacia}",
            )

        if estado_hacia == "CANCELADO" and not motivo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere motivo para cancelar el pedido",
            )

        pedido.estado_codigo = estado_hacia
        pedido.updated_at = datetime.now(timezone.utc)
        self.uow.pedidos.update(pedido)

        # Restaurar stock si se cancela
        if estado_hacia == "CANCELADO":
            for detalle in pedido.detalles:
                producto = self.uow.productos.get_by_id(detalle.producto_id)
                if producto:
                    producto.stock_cantidad += detalle.cantidad
                    if producto.stock_cantidad > 0:
                        producto.disponible = True
                    self.uow.productos.update(producto)

        self.uow.historial_pedidos.add(
            HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_desde=estado_desde,
                estado_hacia=estado_hacia,
                usuario_id=usuario_id,
                motivo=motivo,
            )
        )
        result = self._to_public(pedido.id)

        event_type = EVENTOS_WS.get(estado_hacia)
        if event_type:
            from app.core.websocket import manager

            data_ws = _pedido_to_ws_dict(result)
            await manager.broadcast_to_order(pedido_id, event_type, data_ws)
            roles_a_notificar = ROLES_POR_TRANSICION.get(estado_hacia, [])
            if roles_a_notificar:
                await manager.broadcast_to_roles(roles_a_notificar, event_type, data_ws)

        return result

    async def cancelar_cliente(
        self,
        pedido_id: int,
        usuario_id: int,
        motivo: str,
    ) -> PedidoPublic:
        pedido = self._get_pedido_or_404(pedido_id)

        if pedido.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso para cancelar este pedido",
            )

        if pedido.estado_codigo not in ESTADOS_CANCELABLES_POR_CLIENTE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(f"estado actual: {pedido.estado_codigo}"),
            )

        return await self.avanzar_estado(pedido_id, "CANCELADO", usuario_id, motivo)

    def get_pedido_para_usuario(
        self, pedido_id: int, usuario_id: int, roles: List[str]
    ) -> PedidoPublic:
        pedido = self._get_pedido_or_404(pedido_id)

        es_staff = bool({"ADMIN", "PEDIDOS"} & set(roles))
        if not es_staff and pedido.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este pedido",
            )
        return self._to_public(pedido_id)

    def listar_mis_pedidos(self, usuario_id: int) -> List[PedidoPublic]:
        pedidos = self.uow.pedidos.list_by_usuario(usuario_id)
        return [self._to_public(p.id) for p in pedidos]

    def listar_todos(
        self,
        estado_codigo: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[PedidoPublic], int]:
        """Devuelve (items, total) para paginación."""
        from sqlmodel import select, func
        from app.modules.pedidos.models import Pedido

        stmt = select(Pedido).where(Pedido.deleted_at == None)  # noqa: E711
        count_stmt = select(func.count(Pedido.id)).where(Pedido.deleted_at == None)  # noqa: E711

        if estado_codigo:
            stmt = stmt.where(Pedido.estado_codigo == estado_codigo)
            count_stmt = count_stmt.where(Pedido.estado_codigo == estado_codigo)

        total = self.uow.session.exec(count_stmt).one()
        skip = (page - 1) * size
        stmt = stmt.order_by(Pedido.created_at.desc()).offset(skip).limit(size)
        pedidos = list(self.uow.session.exec(stmt).all())
        return [self._to_public(p.id) for p in pedidos], total

    def _get_pedido_or_404(self, pedido_id: int) -> Pedido:
        pedido = self.uow.pedidos.get_by_id(pedido_id)
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        return pedido

    def _to_public(self, pedido_id: int) -> PedidoPublic:
        from app.modules.pagos.schemas import PagoRead

        pedido = self.uow.pedidos.get_by_id(pedido_id)
        detalles = self.uow.pedidos.get_detalles(pedido_id)
        historial = self.uow.pedidos.get_historial(pedido_id)

        pago_model = self.uow.pagos.get_ultimo_by_pedido(pedido_id)
        pago = PagoRead.model_validate(pago_model) if pago_model else None

        return PedidoPublic(
            id=pedido.id,
            usuario_id=pedido.usuario_id,
            direccion_id=pedido.direccion_id,
            estado_codigo=pedido.estado_codigo,
            forma_pago_codigo=pedido.forma_pago_codigo,
            subtotal=pedido.subtotal,
            descuento=pedido.descuento,
            costo_envio=pedido.costo_envio,
            total=pedido.total,
            notas=pedido.notas,
            created_at=pedido.created_at,
            updated_at=pedido.updated_at,
            detalles=[DetallePedidoPublic.model_validate(d) for d in detalles],
            historial=[HistorialPublic.model_validate(h) for h in historial],
            direccion=pedido.direccion,
            pago=pago,
        )


def _pedido_to_ws_dict(pedido: PedidoPublic) -> dict[str, Any]:

    return {
        "id": pedido.id,
        "usuario_id": pedido.usuario_id,
        "estado_codigo": pedido.estado_codigo,
        "forma_pago_codigo": pedido.forma_pago_codigo,
        "total": pedido.total,
        "notas": pedido.notas,
        "created_at": pedido.created_at.isoformat(),
        "updated_at": pedido.updated_at.isoformat(),
    }
