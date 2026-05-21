from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.modules.categorias.model import Categoria
    from app.modules.ingrediente.models import Ingrediente
    from app.modules.catalogos.models import UnidadMedida

from app.modules.producto.associations import ProductoCategoria, ProductoIngrediente


class Producto(SQLModel, table=True):
    __tablename__ = "producto"

    id:              Optional[int] = Field(default=None, primary_key=True)
    unidad_venta_id: Optional[int] = Field(default=None, foreign_key="unidad_medida.id")

    nombre:          str  = Field(index=True, max_length=150, nullable=False)
    descripcion:     Optional[str] = Field(default=None)
    precio_base:     float = Field(nullable=False)  # DECIMAL(10,2) CHECK >= 0

    imagenes_url:    Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    stock_cantidad:  int  = Field(default=0, nullable=False)   # CHECK >= 0
    disponible:      bool = Field(default=True, nullable=False)

    created_at:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at:      Optional[datetime] = Field(default=None)

    unidad_venta:    Optional["UnidadMedida"] = Relationship(back_populates="productos")

    categorias:      List["Categoria"] = Relationship(
        back_populates="productos",
        link_model=ProductoCategoria,
    )
    ingredientes:    List["Ingrediente"] = Relationship(
        back_populates="productos",
        link_model=ProductoIngrediente,
    )
