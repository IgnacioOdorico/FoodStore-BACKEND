from decimal import Decimal
from typing import List, Dict, Annotated
from pydantic import BaseModel, PlainSerializer

# Serializa Decimal como float en respuestas JSON (JSON no tiene tipo Decimal)
DecimalJSON = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used='json')]


class ResumenResponse(BaseModel):
    ventas_hoy: DecimalJSON
    ticket_promedio: DecimalJSON
    pedidos_activos: int
    mes_actual: DecimalJSON

class VentasPeriodoItem(BaseModel):
    fecha: str
    ingresos: DecimalJSON
    cantidad: int

class VentasPeriodoResponse(BaseModel):
    items: List[VentasPeriodoItem]

class ProductoTopItem(BaseModel):
    nombre: str
    cantidad: int
    ingresos: DecimalJSON

class ProductosTopResponse(BaseModel):
    items: List[ProductoTopItem]

class PedidosEstadoResponse(BaseModel):
    items: Dict[str, int]

class IngresosItem(BaseModel):
    forma_pago_codigo: str
    ingresos: DecimalJSON

class IngresosResponse(BaseModel):
    items: List[IngresosItem]
    total: DecimalJSON


class ResumenStockResponse(BaseModel):
    bajo: int
    sinStock: int
    normal: int
    total: int


class DashboardResponse(BaseModel):
    totalProductos: int
    totalPedidos: int
    totalUsuarios: int
    pedidosPorEstado: Dict[str, int]
    topProductos: List[ProductoTopItem]
    resumenStock: ResumenStockResponse
