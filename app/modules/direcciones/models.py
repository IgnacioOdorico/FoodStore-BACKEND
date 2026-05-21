from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from pydantic import ConfigDict
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.usuarios.model import Usuario
    from app.modules.pedidos.models import Pedido


class DireccionEntrega(SQLModel, table=True):
    __tablename__ = "direccion_entrega"

    id:             Optional[int] = Field(default=None, primary_key=True)
    usuario_id:     int           = Field(foreign_key="usuario.id", nullable=False)

    alias:          Optional[str] = Field(default=None, max_length=50)
    linea1:         str           = Field(nullable=False)
    linea2:         Optional[str] = Field(default=None)
    ciudad:         str           = Field(max_length=100, nullable=False)
    provincia:      Optional[str] = Field(default=None, max_length=100)
    codigo_postal:  Optional[str] = Field(default=None, max_length=10)
    latitud:        Optional[float] = Field(default=None)
    longitud:       Optional[float] = Field(default=None)

    es_principal:   bool          = Field(default=False, nullable=False)

    created_at:     datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:     datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at:     Optional[datetime] = Field(default=None)

    usuario: "Usuario" = Relationship(back_populates="direcciones")
    pedidos: List["Pedido"] = Relationship(back_populates="direccion")


class DireccionCreate(SQLModel):
    alias:         Optional[str] = Field(default=None, max_length=50)
    linea1:        str = Field(min_length=1)
    linea2:        Optional[str] = None
    ciudad:        str = Field(min_length=1, max_length=100)
    provincia:     Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    latitud:       Optional[float] = None
    longitud:      Optional[float] = None
    es_principal:  bool = False


class DireccionUpdate(SQLModel):
    alias:         Optional[str] = Field(default=None, max_length=50)
    linea1:        Optional[str] = None
    linea2:        Optional[str] = None
    ciudad:        Optional[str] = Field(default=None, max_length=100)
    provincia:     Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    latitud:       Optional[float] = None
    longitud:      Optional[float] = None


class DireccionPublic(SQLModel):
    id:            int
    usuario_id:    int
    alias:         Optional[str]
    linea1:        str
    linea2:        Optional[str]
    ciudad:        str
    provincia:     Optional[str]
    codigo_postal: Optional[str]
    latitud:       Optional[float]
    longitud:      Optional[float]
    es_principal:  bool
    created_at:    datetime
    updated_at:    datetime

    model_config = ConfigDict(from_attributes=True)
