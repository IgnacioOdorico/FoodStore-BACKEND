from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.pedidos.models import Pedido

class Pago(SQLModel, table=True):
    __tablename__ = "pago"

    id: Optional[int] = Field(default=None, primary_key=True)
    mp_payment_id: Optional[int] = Field(default=None, unique=True)
    mp_status: str = Field(max_length=30)
    mp_status_detail: Optional[str] = Field(default=None, max_length=100)
    transaction_amount: float
    payment_method_id: Optional[str] = Field(default=None, max_length=50)
    external_reference: str = Field(unique=True, max_length=100)
    idempotency_key: str = Field(unique=True, max_length=100)
    
    pedido_id: int = Field(foreign_key="pedido.id")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
