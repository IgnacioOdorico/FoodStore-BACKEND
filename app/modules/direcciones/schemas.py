from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


class DireccionCreate(SQLModel):
    alias: Optional[str] = Field(default=None, max_length=50)
    linea1: str = Field(min_length=1)
    linea2: Optional[str] = None
    ciudad: str = Field(min_length=1, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    es_principal: bool = False


class DireccionUpdate(SQLModel):
    alias: Optional[str] = Field(default=None, max_length=50)
    linea1: Optional[str] = None
    linea2: Optional[str] = None
    ciudad: Optional[str] = Field(default=None, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    latitud: Optional[float] = None
    longitud: Optional[float] = None


class DireccionPublic(SQLModel):
    id: int
    usuario_id: int
    alias: Optional[str]
    linea1: str
    linea2: Optional[str]
    ciudad: str
    provincia: Optional[str]
    codigo_postal: Optional[str]
    latitud: Optional[float]
    longitud: Optional[float]
    es_principal: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
