from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.modules.pedidos.models import Pedido, HistorialEstadoPedido
    from app.modules.direcciones.models import DireccionEntrega

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


class UsuarioRol(SQLModel, table=True):
    __tablename__ = "usuario_rol"

    usuario_id:      int       = Field(foreign_key="usuario.id", primary_key=True)
    rol_codigo:      str       = Field(foreign_key="rol.codigo", primary_key=True, max_length=20)
    
    asignado_por_id: Optional[int] = Field(default=None, foreign_key="usuario.id")
    expires_at:      Optional[datetime] = Field(default=None)
    created_at:      datetime  = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relaciones
    usuario: "Usuario" = Relationship(
        back_populates="roles_link",
        sa_relationship_kwargs={"foreign_keys": "[UsuarioRol.usuario_id]"}
    )
    rol:     "Rol"     = Relationship(back_populates="usuarios_link")


class Rol(SQLModel, table=True):

    __tablename__ = "rol"

    codigo:      str  = Field(primary_key=True, max_length=20)
    nombre:      str  = Field(unique=True, index=True, nullable=False, max_length=50)
    descripcion: Optional[str] = Field(default=None)

    # Relación N:N vía UsuarioRol
    usuarios_link: List[UsuarioRol] = Relationship(back_populates="rol")



class Usuario(SQLModel, table=True):

    __tablename__ = "usuario"

    id:            Optional[int] = Field(default=None, primary_key=True)
    nombre:        str           = Field(max_length=80, nullable=False)
    apellido:      str           = Field(max_length=80, nullable=False)
    email:         str           = Field(unique=True, index=True, nullable=False, max_length=254)
    celular:       Optional[str] = Field(default=None, max_length=20)
    password_hash: str           = Field(max_length=60, nullable=False) # Bcrypt hash
    
    # Audit
    created_at:    datetime      = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:    datetime      = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at:    Optional[datetime] = Field(default=None)

    roles_link:     List[UsuarioRol] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "[UsuarioRol.usuario_id]"}
    )
    pedidos:        List["Pedido"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "[Pedido.usuario_id]"},
    )
    direcciones:    List["DireccionEntrega"] = Relationship(back_populates="usuario")
    historial_pedidos: List["HistorialEstadoPedido"] = Relationship(back_populates="usuario")
