from typing import Optional
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.catalogos.models import UnidadMedida, EstadoPedido, FormaPago


class UnidadMedidaRepository(BaseRepository[UnidadMedida]):
    def __init__(self, session: Session):
        super().__init__(UnidadMedida, session)

    def get_by_simbolo(self, simbolo: str) -> Optional[UnidadMedida]:
        return self.session.exec(
            select(UnidadMedida).where(UnidadMedida.simbolo == simbolo)
        ).first()


class EstadoPedidoRepository(BaseRepository[EstadoPedido]):
    def __init__(self, session: Session):
        super().__init__(EstadoPedido, session)

    def get_by_codigo(self, codigo: str) -> Optional[EstadoPedido]:
        return self.session.get(EstadoPedido, codigo)


class FormaPagoRepository(BaseRepository[FormaPago]):
    def __init__(self, session: Session):
        super().__init__(FormaPago, session)

    def get_by_codigo(self, codigo: str) -> Optional[FormaPago]:
        return self.session.get(FormaPago, codigo)
