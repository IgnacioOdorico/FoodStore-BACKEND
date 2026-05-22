from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from sqlmodel import SQLModel, Field


class CategoriaCreate(SQLModel):
    nombre:      str = Field(min_length=1, max_length=100)
    descripcion: Optional[str] = None
    imagen_url:  Optional[str] = None
    parent_id:   Optional[int] = None


class CategoriaUpdate(SQLModel):
    nombre:      Optional[str] = Field(default=None, min_length=1, max_length=100)
    descripcion: Optional[str] = None
    imagen_url:  Optional[str] = None
    parent_id:   Optional[int] = None


class CategoriaPublic(SQLModel):
    id:          int
    nombre:      str
    descripcion: Optional[str]
    imagen_url:  Optional[str]
    parent_id:   Optional[int]
    created_at:  datetime
    updated_at:  datetime

    model_config = ConfigDict(from_attributes=True)
