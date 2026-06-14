from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class ProductoCategoria(SQLModel, table=True):
    __tablename__ = "producto_categoria"

    producto_id:   int  = Field(foreign_key="producto.id", primary_key=True)
    categoria_id:  int  = Field(foreign_key="categoria.id", primary_key=True)
    es_principal:  bool = Field(default=False, nullable=False)
    created_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductoIngrediente(SQLModel, table=True):
    __tablename__ = "producto_ingrediente"

    producto_id:      int  = Field(foreign_key="producto.id", primary_key=True)
    ingrediente_id:   int  = Field(foreign_key="ingrediente.id", primary_key=True)

    cantidad:         float = Field(nullable=False)  # DECIMAL(10,3) en PG
    unidad_medida_id: int = Field(foreign_key="unidad_medida.id")
    es_removible:     bool  = Field(default=False, nullable=False)

    created_at:       datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
