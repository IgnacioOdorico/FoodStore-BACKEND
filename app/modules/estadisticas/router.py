from fastapi import APIRouter, Depends, Query
from datetime import date
from app.core.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.modules.estadisticas.service import EstadisticasService
from app.modules.estadisticas.schemas import (
    ResumenResponse, VentasPeriodoResponse,
    ProductosTopResponse, PedidosEstadoResponse, IngresosResponse
)

router = APIRouter(prefix="/api/v1/estadisticas", tags=["estadisticas"])

@router.get("/resumen", response_model=ResumenResponse,
            dependencies=[Depends(require_role(["ADMIN"]))])
def get_resumen(uow: UnitOfWork = Depends(get_uow)):
    with uow:
        return EstadisticasService(uow).get_resumen()

@router.get("/ventas", response_model=VentasPeriodoResponse,
            dependencies=[Depends(require_role(["ADMIN"]))])
def get_ventas(
    desde: date = Query(...),
    hasta: date = Query(...),
    agrupacion: str = Query(default="dia", pattern="^(dia|semana|mes)$"),
    uow: UnitOfWork = Depends(get_uow),
):
    with uow:
        return EstadisticasService(uow).get_ventas_por_periodo(desde, hasta, agrupacion)

@router.get("/productos-top", response_model=ProductosTopResponse,
            dependencies=[Depends(require_role(["ADMIN"]))])
def get_productos_top(
    limit: int = Query(default=10, ge=1, le=50),
    uow: UnitOfWork = Depends(get_uow),
):
    with uow:
        return EstadisticasService(uow).get_productos_top(limit)

@router.get("/pedidos-por-estado", response_model=PedidosEstadoResponse,
            dependencies=[Depends(require_role(["ADMIN"]))])
def get_pedidos_por_estado(uow: UnitOfWork = Depends(get_uow)):
    with uow:
        return EstadisticasService(uow).get_pedidos_por_estado()

@router.get("/ingresos", response_model=IngresosResponse,
            dependencies=[Depends(require_role(["ADMIN"]))])
def get_ingresos(
    desde: date = Query(...),
    hasta: date = Query(...),
    uow: UnitOfWork = Depends(get_uow),
):
    with uow:
        return EstadisticasService(uow).get_ingresos_por_forma_pago(desde, hasta)
