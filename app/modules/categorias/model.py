"""
Modelo de Categoría — tabla 'categoria' en PostgreSQL.

Adaptado al ERD v5:
  - Soporte para categorías jerárquicas (parent_id).
"""

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from pydantic import ConfigDict

if TYPE_CHECKING:
    from app.modules.producto.models import Producto

from app.modules.producto.associations import ProductoCategoria


class Categoria(SQLModel, table=True):
    id:          Optional[int] = Field(default=None, primary_key=True)
    nombre:      str           = Field(index=True, unique=True, max_length=50, nullable=False)
    descripcion: Optional[str] = Field(default=None)
    
    # Jerarquía (Self-reference)
    parent_id:   Optional[int] = Field(default=None, foreign_key="categoria.id")
    
    # Auditoría
    created_at:  datetime      = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:  datetime      = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    padre:       Optional["Categoria"] = Relationship(
        back_populates="subcategorias", 
        sa_relationship_kwargs={"remote_side": "Categoria.id", "foreign_keys": "[Categoria.parent_id]"}
    )
    subcategorias: List["Categoria"] = Relationship(back_populates="padre")
    
    # Relación N:N con Producto
    productos: List["Producto"] = Relationship(
        back_populates="categorias",
        link_model=ProductoCategoria
    )


# ─── Esquemas Pydantic ───────────────────────────────────────────────────────

class CategoriaCreate(SQLModel):
    nombre:      str = Field(min_length=1, max_length=50)
    descripcion: Optional[str] = None
    parent_id:   Optional[int] = None


class CategoriaUpdate(SQLModel):
    """Schema para PATCH: todos los campos son opcionales."""
    nombre:      Optional[str] = Field(default=None, min_length=1, max_length=50)
    descripcion: Optional[str] = None
    parent_id:   Optional[int] = None


class CategoriaPublic(SQLModel):
    id:          int
    nombre:      str
    descripcion: Optional[str]
    parent_id:   Optional[int]
    created_at:  datetime
    updated_at:  datetime

    model_config = ConfigDict(from_attributes=True)
