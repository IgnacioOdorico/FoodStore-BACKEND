from decimal import Decimal
from typing import List, Dict
from pydantic import BaseModel

class ResumenResponse(BaseModel):
    ventas_hoy: Decimal
    ticket_promedio: Decimal
    pedidos_activos: int
    mes_actual: Decimal

class VentasPeriodoItem(BaseModel):
    fecha: str
    ingresos: Decimal
    cantidad: int

class VentasPeriodoResponse(BaseModel):
    items: List[VentasPeriodoItem]

class ProductoTopItem(BaseModel):
    nombre: str
    cantidad: int
    ingresos: Decimal

class ProductosTopResponse(BaseModel):
    items: List[ProductoTopItem]

class PedidosEstadoResponse(BaseModel):
    items: Dict[str, int]

class IngresosItem(BaseModel):
    forma_pago_codigo: str
    ingresos: Decimal

class IngresosResponse(BaseModel):
    items: List[IngresosItem]
    total: Decimal
