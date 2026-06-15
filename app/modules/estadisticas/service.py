from datetime import date
from app.core.uow import UnitOfWork
from app.modules.estadisticas.repository import EstadisticasRepository
from app.modules.estadisticas.schemas import (
    ResumenResponse, VentasPeriodoResponse,
    ProductosTopResponse, PedidosEstadoResponse, IngresosResponse
)

class EstadisticasService:
    def __init__(self, uow: UnitOfWork):
        self.repository = EstadisticasRepository(uow.session)

    def get_resumen(self) -> ResumenResponse:
        data = self.repository.get_resumen_kpis()
        return ResumenResponse(**data)

    def get_ventas_por_periodo(self, desde: date, hasta: date, agrupacion: str) -> VentasPeriodoResponse:
        items = self.repository.get_ventas_periodo(desde, hasta, agrupacion)
        return VentasPeriodoResponse(items=items)

    def get_productos_top(self, limit: int) -> ProductosTopResponse:
        items = self.repository.get_productos_top(limit)
        return ProductosTopResponse(items=items)

    def get_pedidos_por_estado(self) -> PedidosEstadoResponse:
        items = self.repository.get_pedidos_por_estado()
        return PedidosEstadoResponse(items=items)

    def get_ingresos_por_forma_pago(self, desde: date, hasta: date) -> IngresosResponse:
        items = self.repository.get_ingresos_por_forma_pago(desde, hasta)
        total = sum([item["ingresos"] for item in items])
        return IngresosResponse(items=items, total=total)
