from typing import List

from app.core.uow import UnitOfWork
from app.modules.catalogos.schemas import (
    UnidadMedidaPublic,
    EstadoPedidoPublic,
    FormaPagoPublic,
)


class CatalogoService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def list_unidades(self) -> List[UnidadMedidaPublic]:
        return [UnidadMedidaPublic.model_validate(u) for u in self.uow.unidades_medida.get_all()]

    def list_estados_pedido(self) -> List[EstadoPedidoPublic]:
        return [
            EstadoPedidoPublic.model_validate(e)
            for e in sorted(self.uow.estados_pedido.get_all(), key=lambda e: e.orden)
        ]

    def list_formas_pago(self, solo_habilitadas: bool = False) -> List[FormaPagoPublic]:
        items = self.uow.formas_pago.get_all()
        if solo_habilitadas:
            items = [f for f in items if f.habilitado]
        return [FormaPagoPublic.model_validate(f) for f in items]
