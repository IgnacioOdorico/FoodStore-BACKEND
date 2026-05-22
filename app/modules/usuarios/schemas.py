from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr
from sqlmodel import SQLModel


class UserCreate(SQLModel):
    nombre: str
    apellido: str
    email: EmailStr
    celular: Optional[str] = None
    password: str


class UserPublic(SQLModel):
    id: int
    nombre: str
    apellido: str
    email: str
    celular: Optional[str]
    roles: List[str] = []
    created_at: datetime


class Token(SQLModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(SQLModel):
    email: str
    password: str


class RolPublic(SQLModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None


class UsuarioRolPublic(SQLModel):
    usuario_id: int
    rol_codigo: str
    created_at: datetime
