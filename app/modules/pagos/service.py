from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status

from app.core.uow import UnitOfWork
from app.modules.pagos.models import Pago
from app.modules.pagos.schemas import (
    PagoCreate,
    PagoPublic,
    PagoWebhookUpdate,
)


class PagoService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def crear_pago(self, data: PagoCreate, usuario_id: int) -> PagoPublic:
        pedido = self.uow.pedidos.get_by_id(data.pedido_id)
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        if pedido.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso sobre este pedido",
            )

        pago = Pago(
            pedido_id=pedido.id,
            transaction_amount=data.transaction_amount,
            payment_method_id=data.payment_method_id,
            mp_status="pending",
        )
        created = self.uow.pagos.add(pago)
        return PagoPublic.model_validate(created)

    def listar_por_pedido(self, pedido_id: int, usuario_id: int, roles: List[str]) -> List[PagoPublic]:
        pedido = self.uow.pedidos.get_by_id(pedido_id)
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        es_staff = bool({"ADMIN", "PEDIDOS"} & set(roles))
        if not es_staff and pedido.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este pedido",
            )
        return [PagoPublic.model_validate(p) for p in self.uow.pagos.list_by_pedido(pedido_id)]

    def webhook(self, data: PagoWebhookUpdate) -> PagoPublic:
        pago = self.uow.pagos.get_by_external_reference(data.external_reference)
        if not pago:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pago no encontrado",
            )

        pago.mp_status = data.mp_status
        pago.mp_status_detail = data.mp_status_detail
        pago.mp_payment_id = data.mp_payment_id
        pago.updated_at = datetime.now(timezone.utc)
        self.uow.pagos.update(pago)

        if data.mp_status == "approved":
            from app.modules.pedidos.service import PedidoService, FSM
            pedido = self.uow.pedidos.get_by_id(pago.pedido_id)
            if pedido and "CONFIRMADO" in FSM.get(pedido.estado_codigo, set()):
                PedidoService(self.uow).avanzar_estado(
                    pedido_id=pago.pedido_id,
                    estado_hacia="CONFIRMADO",
                    usuario_id=None,  # actor sistema
                    motivo=f"Pago MP aprobado ({data.mp_payment_id})",
                )

        return PagoPublic.model_validate(pago)
