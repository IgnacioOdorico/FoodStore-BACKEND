from typing import List, Optional
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.pedidos.models import Pedido, DetallePedido, HistorialEstadoPedido


class PedidoRepository(BaseRepository[Pedido]):
    def __init__(self, session: Session):
        super().__init__(Pedido, session)

    def list_all_active(self, estado_codigo: Optional[str] = None) -> List[Pedido]:
        statement = select(Pedido).where(Pedido.deleted_at == None)  # noqa: E711
        if estado_codigo:
            statement = statement.where(Pedido.estado_codigo == estado_codigo)
        statement = statement.order_by(Pedido.created_at.desc())
        return list(self.session.exec(statement).all())

    def list_by_usuario(self, usuario_id: int) -> List[Pedido]:
        statement = (
            select(Pedido)
            .where(
                Pedido.usuario_id == usuario_id,
                Pedido.deleted_at == None,  # noqa: E711
            )
            .order_by(Pedido.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def get_detalles(self, pedido_id: int) -> List[DetallePedido]:
        return list(self.session.exec(
            select(DetallePedido).where(DetallePedido.pedido_id == pedido_id)
        ).all())

    def get_historial(self, pedido_id: int) -> List[HistorialEstadoPedido]:
        return list(self.session.exec(
            select(HistorialEstadoPedido)
            .where(HistorialEstadoPedido.pedido_id == pedido_id)
            .order_by(HistorialEstadoPedido.created_at.asc())
        ).all())


class DetallePedidoRepository(BaseRepository[DetallePedido]):
    def __init__(self, session: Session):
        super().__init__(DetallePedido, session)


class HistorialEstadoPedidoRepository(BaseRepository[HistorialEstadoPedido]):
    def __init__(self, session: Session):
        super().__init__(HistorialEstadoPedido, session)
