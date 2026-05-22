from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.modules.producto.models import Producto

from app.modules.producto.associations import ProductoCategoria


class Categoria(SQLModel, table=True):
    __tablename__ = "categoria"

    id:          Optional[int] = Field(default=None, primary_key=True)
    nombre:      str           = Field(index=True, unique=True, max_length=100, nullable=False)
    descripcion: Optional[str] = Field(default=None)
    imagen_url:  Optional[str] = Field(default=None, max_length=2000)
    parent_id:   Optional[int] = Field(default=None, foreign_key="categoria.id")

    created_at:  datetime      = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:  datetime      = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at:  Optional[datetime] = Field(default=None)

    padre:       Optional["Categoria"] = Relationship(
        back_populates="subcategorias",
        sa_relationship_kwargs={"remote_side": "Categoria.id", "foreign_keys": "[Categoria.parent_id]"}
    )
    subcategorias: List["Categoria"] = Relationship(back_populates="padre")

    productos: List["Producto"] = Relationship(
        back_populates="categorias",
        link_model=ProductoCategoria
    )
