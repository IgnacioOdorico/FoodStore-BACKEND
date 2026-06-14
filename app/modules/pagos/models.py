from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.pedidos.models import Pedido


class Pago(SQLModel, table=True):
    __tablename__ = "pago"

    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", index=True, nullable=False)
    transaction_amount: float = Field(nullable=False)
    estado: str = Field(default="pendiente", max_length=20, nullable=False)
    mp_preference_id: Optional[str] = Field(default=None, max_length=100)
    mp_init_point: Optional[str] = Field(default=None, max_length=255)
    mp_payment_id: Optional[int] = Field(default=None, sa_type=BigInteger, unique=True)
    mp_status: str = Field(default="pending", max_length=30, nullable=False)
    mp_status_detail: Optional[str] = Field(default=None, max_length=100)
    mp_merchant_order_id: Optional[int] = Field(default=None, sa_type=BigInteger)
    payment_method_id: Optional[str] = Field(default=None, max_length=50)
    external_reference: str = Field(max_length=100, unique=True, nullable=False)
    idempotency_key: str = Field(max_length=100, unique=True, nullable=False)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)

    pedido: "Pedido" = Relationship(back_populates="pagos")
