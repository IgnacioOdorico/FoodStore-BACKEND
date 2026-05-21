from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.modules.producto.models import Producto

from app.modules.producto.associations import ProductoIngrediente


class Ingrediente(SQLModel, table=True):
    __tablename__ = "ingrediente"

    id:          Optional[int] = Field(default=None, primary_key=True)
    nombre:      str           = Field(index=True, unique=True, max_length=100, nullable=False)
    descripcion: Optional[str] = Field(default=None)
    es_alergeno: bool          = Field(default=False, nullable=False)

    created_at:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    productos: List["Producto"] = Relationship(
        back_populates="ingredientes",
        link_model=ProductoIngrediente,
    )
