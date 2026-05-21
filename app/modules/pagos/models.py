import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from pydantic import ConfigDict
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.pedidos.models import Pedido


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Pago(SQLModel, table=True):
    __tablename__ = "pago"

    id:                Optional[int] = Field(default=None, primary_key=True)
    pedido_id:         int = Field(foreign_key="pedido.id", nullable=False)

    mp_payment_id:     Optional[int] = Field(default=None, unique=True)
    mp_status:         str = Field(default="pending", max_length=30, nullable=False)
    mp_status_detail:  Optional[str] = Field(default=None, max_length=100)

    external_reference: str = Field(
        default_factory=_new_uuid, unique=True, nullable=False, max_length=100
    )
    idempotency_key:    str = Field(
        default_factory=_new_uuid, unique=True, nullable=False, max_length=100
    )

    transaction_amount: float = Field(nullable=False)
    payment_method_id:  Optional[str] = Field(default=None, max_length=50)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    pedido: "Pedido" = Relationship(back_populates="pagos")


class PagoCreate(SQLModel):
    """Body para POST /pagos."""
    pedido_id:          int
    transaction_amount: float = Field(gt=0)
    payment_method_id:  Optional[str] = None


class PagoWebhookUpdate(SQLModel):
    """Body para POST /pagos/webhook (simulado)."""
    external_reference: str
    mp_payment_id:      Optional[int] = None
    mp_status:          str
    mp_status_detail:   Optional[str] = None


class PagoPublic(SQLModel):
    id:                 int
    pedido_id:          int
    mp_payment_id:      Optional[int]
    mp_status:          str
    mp_status_detail:   Optional[str]
    external_reference: str
    transaction_amount: float
    payment_method_id:  Optional[str]
    created_at:         datetime
    updated_at:         datetime

    model_config = ConfigDict(from_attributes=True)
