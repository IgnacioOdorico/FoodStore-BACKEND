from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from sqlmodel import SQLModel, Field


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
