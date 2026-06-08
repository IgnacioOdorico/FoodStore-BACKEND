from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.producto.models import Producto
    from app.modules.producto.associations import ProductoIngrediente
    from app.modules.pedidos.models import Pedido, HistorialEstadoPedido


class UnidadMedida(SQLModel, table=True):
    __tablename__ = "unidad_medida"

    id:        Optional[int] = Field(default=None, primary_key=True)
    nombre:    str           = Field(unique=True, index=True, nullable=False, max_length=50)
    simbolo:   str           = Field(unique=True, nullable=False, max_length=10)
    tipo:      str           = Field(nullable=False, max_length=20)  # masa | volumen | unidad | area

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    productos: List["Producto"] = Relationship(back_populates="unidad_venta")


class EstadoPedido(SQLModel, table=True):
    """
    Catálogo de estados del FSM de Pedidos.

    Seed obligatorio (ver app/db/seed.py):
      PENDIENTE  (orden 1, terminal=False)
      CONFIRMADO (orden 2, terminal=False)
      EN_PREP    (orden 3, terminal=False)
      ENTREGADO  (orden 4, terminal=True)
      CANCELADO  (orden 5, terminal=True)
    """
    __tablename__ = "estado_pedido"

    codigo:       str  = Field(primary_key=True, max_length=20)
    descripcion:  str  = Field(nullable=False, max_length=80)
    orden:        int  = Field(nullable=False)
    es_terminal:  bool = Field(default=False, nullable=False)

    pedidos: List["Pedido"] = Relationship(back_populates="estado")


class FormaPago(SQLModel, table=True):
    """
    Catálogo de formas de pago.

    Seed obligatorio (ver app/db/seed.py):
      MERCADOPAGO  — Checkout API
      EFECTIVO     — retiro en local
      TRANSFERENCIA — bancaria
    """
    __tablename__ = "forma_pago"

    codigo:      str  = Field(primary_key=True, max_length=20)
    descripcion: str  = Field(nullable=False, max_length=80)
    habilitado:  bool = Field(default=True, nullable=False)

    pedidos: List["Pedido"] = Relationship(back_populates="forma_pago")
