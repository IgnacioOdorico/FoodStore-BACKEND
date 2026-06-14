from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ResumenKpis(BaseModel):
    total_ingresos: float
    total_pedidos: int
    ticket_promedio: float

class VentasPeriodoItem(BaseModel):
    fecha: str
    fechaLabel: str
    ingresos: float
    cantidad: int

class ProductoTopItem(BaseModel):
    nombre: str
    cantidad: int
    ingresos: float

class ResumenStock(BaseModel):
    bajo: int
    sinStock: int
    normal: int
    total: int

class DashboardResponse(BaseModel):
    totalCategorias: int
    totalProductos: int
    totalIngredientes: int
    totalPedidos: int
    totalUsuarios: Optional[int] = None
    pedidosPorEstado: Dict[str, int]
    pedidosPorFormaPago: Dict[str, int]
    ordenesRecientes: List[Any]
    productosStockBajo: List[Any]
    ingredientesStockBajo: List[Any]
    pedidosPorDia: List[VentasPeriodoItem]
    topProductos: List[ProductoTopItem]
    productosConCategoria: List[Any]
    resumenStock: ResumenStock
