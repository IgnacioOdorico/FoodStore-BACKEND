from datetime import datetime
from typing import List, Optional

from pydantic import ConfigDict
from sqlmodel import SQLModel

from app.modules.direcciones.schemas import DireccionPublic
from app.modules.pagos.schemas import PagoRead


class ItemPedidoRequest(SQLModel):
    producto_id: int
    cantidad: int
    personalizacion: Optional[List[int]] = None


class PedidoCreate(SQLModel):
    detalles: List[ItemPedidoRequest]
    forma_pago_codigo: str
    direccion_id: Optional[int] = None
    notas: Optional[str] = None
    descuento: float = 0.0
    costo_envio: float = 0.0


class AvanzarEstadoRequest(SQLModel):
    estado_hacia: str
    motivo: Optional[str] = None


class CancelarRequest(SQLModel):
    motivo: str


class DetallePedidoPublic(SQLModel):
    pedido_id: int
    producto_id: int
    cantidad: int
    nombre_snapshot: str
    precio_snapshot: float
    subtotal_snap: float
    personalizacion: Optional[List[int]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HistorialPublic(SQLModel):
    id: int
    estado_desde: Optional[str]
    estado_hacia: str
    usuario_id: Optional[int]
    motivo: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PedidoPublic(SQLModel):
    id: int
    usuario_id: int
    direccion_id: Optional[int]
    estado_codigo: str
    forma_pago_codigo: str
    subtotal: float
    descuento: float
    costo_envio: float
    total: float
    notas: Optional[str]
    created_at: datetime
    updated_at: datetime

    detalles: List[DetallePedidoPublic] = []
    historial: List[HistorialPublic] = []
    direccion: Optional[DireccionPublic] = None
    pago: Optional[PagoRead] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPedidos(SQLModel):
    """Respuesta paginada."""
    items: List[PedidoPublic]
    total: int
    page: int
    size: int
    pages: int

