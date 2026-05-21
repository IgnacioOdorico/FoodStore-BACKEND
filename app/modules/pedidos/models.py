from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from pydantic import ConfigDict
from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.usuarios.model import Usuario
    from app.modules.direcciones.models import DireccionEntrega
    from app.modules.catalogos.models import EstadoPedido, FormaPago
    from app.modules.pagos.models import Pago


class Pedido(SQLModel, table=True):
    __tablename__ = "pedido"

    id:                Optional[int] = Field(default=None, primary_key=True)

    usuario_id:        int = Field(foreign_key="usuario.id", nullable=False)
    direccion_id:      Optional[int] = Field(default=None, foreign_key="direccion_entrega.id")
    estado_codigo:     str = Field(foreign_key="estado_pedido.codigo", nullable=False, max_length=20)
    forma_pago_codigo: str = Field(foreign_key="forma_pago.codigo", nullable=False, max_length=20)

    subtotal:    float = Field(nullable=False)
    descuento:   float = Field(default=0.0, nullable=False)
    costo_envio: float = Field(default=0.0, nullable=False)
    total:       float = Field(nullable=False)

    notas:       Optional[str] = Field(default=None)

    created_at:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at:  Optional[datetime] = Field(default=None)

    usuario:    "Usuario"                   = Relationship(
        back_populates="pedidos",
        sa_relationship_kwargs={"foreign_keys": "[Pedido.usuario_id]"},
    )
    direccion:  Optional["DireccionEntrega"] = Relationship(back_populates="pedidos")
    estado:     "EstadoPedido"               = Relationship(back_populates="pedidos")
    forma_pago: "FormaPago"                  = Relationship(back_populates="pedidos")

    detalles:   List["DetallePedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    historial:  List["HistorialEstadoPedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    pagos:      List["Pago"] = Relationship(back_populates="pedido")


class DetallePedido(SQLModel, table=True):
    __tablename__ = "detalle_pedido"

    pedido_id:        int = Field(foreign_key="pedido.id", primary_key=True)
    producto_id:      int = Field(foreign_key="producto.id", primary_key=True)

    cantidad:         int = Field(nullable=False)

    nombre_snapshot:  str = Field(nullable=False, max_length=200)
    precio_snapshot:  float = Field(nullable=False)
    subtotal_snap:    float = Field(nullable=False)

    personalizacion:  Optional[List[int]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    created_at:       datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    pedido: "Pedido" = Relationship(back_populates="detalles")


class HistorialEstadoPedido(SQLModel, table=True):
    __tablename__ = "historial_estado_pedido"

    id:            Optional[int] = Field(default=None, primary_key=True)

    pedido_id:     int = Field(foreign_key="pedido.id", nullable=False)
    estado_desde:  Optional[str] = Field(default=None, foreign_key="estado_pedido.codigo", max_length=20)
    estado_hacia:  str = Field(foreign_key="estado_pedido.codigo", nullable=False, max_length=20)
    usuario_id:    Optional[int] = Field(default=None, foreign_key="usuario.id")
    motivo:        Optional[str] = Field(default=None)

    created_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    pedido:        "Pedido"  = Relationship(back_populates="historial")
    usuario:       Optional["Usuario"] = Relationship(back_populates="historial_pedidos")


class ItemPedidoRequest(SQLModel):
    producto_id:     int
    cantidad:        int = Field(ge=1)
    personalizacion: Optional[List[int]] = None  


class PedidoCreate(SQLModel):
    detalles:           List[ItemPedidoRequest] = Field(..., min_length=1)
    forma_pago_codigo:  str = Field(min_length=1, max_length=20)
    direccion_id:       Optional[int] = None
    notas:              Optional[str] = None
    descuento:          float = Field(default=0.0, ge=0)
    costo_envio:        float = Field(default=0.0, ge=0)


class AvanzarEstadoRequest(SQLModel):
    estado_hacia: str
    motivo:       Optional[str] = None


class CancelarRequest(SQLModel):
    motivo: str = Field(min_length=1)


class DetallePedidoPublic(SQLModel):
    pedido_id:        int
    producto_id:      int
    cantidad:         int
    nombre_snapshot:  str
    precio_snapshot:  float
    subtotal_snap:    float
    personalizacion:  Optional[List[int]] = None
    created_at:       datetime

    model_config = ConfigDict(from_attributes=True)


class HistorialPublic(SQLModel):
    id:           int
    estado_desde: Optional[str]
    estado_hacia: str
    usuario_id:   Optional[int]
    motivo:       Optional[str]
    created_at:   datetime

    model_config = ConfigDict(from_attributes=True)


class PedidoPublic(SQLModel):
    id:                int
    usuario_id:        int
    direccion_id:      Optional[int]
    estado_codigo:     str
    forma_pago_codigo: str
    subtotal:          float
    descuento:         float
    costo_envio:       float
    total:             float
    notas:             Optional[str]
    created_at:        datetime
    updated_at:        datetime

    detalles:  List[DetallePedidoPublic] = []
    historial: List[HistorialPublic] = []

    model_config = ConfigDict(from_attributes=True)
