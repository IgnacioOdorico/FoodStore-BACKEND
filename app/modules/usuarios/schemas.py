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
    deleted_at: Optional[datetime] = None


class Token(SQLModel):
    access_token: str
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


class UserUpdate(SQLModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    celular: Optional[str] = None


class AdminUserCreate(SQLModel):
    """Creación de empleado por un administrador — asigna los roles indicados (no CLIENT)."""
    nombre: str
    apellido: str
    email: EmailStr
    password: str
    celular: Optional[str] = None
    roles: List[str] = ["STOCK"]


class AdminUserUpdate(SQLModel):
    """Actualización de usuario por un administrador — permite cambiar email y roles."""
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    celular: Optional[str] = None
    email: Optional[EmailStr] = None
    roles: Optional[List[str]] = None

class PasswordChange(SQLModel):
    password_actual: str
    password_nuevo: str
