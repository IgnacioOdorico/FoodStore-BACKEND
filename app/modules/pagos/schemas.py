from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from sqlmodel import SQLModel


class CrearPagoRequest(SQLModel):
    pedido_id: int


class ConfirmarPagoRequest(SQLModel):
    pedido_id: int
    payment_id: Optional[int] = None


class PagoCrearResponse(SQLModel):
    pago_id: int
    preference_id: str
    init_point: Optional[str] = None
    public_key: Optional[str] = None


class PagoEstadoResponse(SQLModel):
    pedido_id: int
    estado: Optional[str] = None  # "pendiente" | "aprobado" | "rechazado" | None


class PagoRead(SQLModel):
    id: int
    pedido_id: int
    transaction_amount: float
    estado: str
    mp_preference_id: Optional[str] = None
    mp_init_point: Optional[str] = None
    mp_payment_id: Optional[int] = None
    mp_status: str
    mp_status_detail: Optional[str] = None
    payment_method_id: Optional[str] = None
    external_reference: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
