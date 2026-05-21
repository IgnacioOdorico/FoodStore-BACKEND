from typing import List, Optional
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.pagos.models import Pago


class PagoRepository(BaseRepository[Pago]):
    def __init__(self, session: Session):
        super().__init__(Pago, session)

    def list_by_pedido(self, pedido_id: int) -> List[Pago]:
        return list(self.session.exec(
            select(Pago).where(Pago.pedido_id == pedido_id).order_by(Pago.created_at.desc())
        ).all())

    def get_by_external_reference(self, external_reference: str) -> Optional[Pago]:
        return self.session.exec(
            select(Pago).where(Pago.external_reference == external_reference)
        ).first()
