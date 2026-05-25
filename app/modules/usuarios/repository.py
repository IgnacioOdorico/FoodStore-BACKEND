from typing import List, Optional
from sqlmodel import Session, select, delete

from app.core.base_repository import BaseRepository
from app.modules.usuarios.model import Usuario, Rol, UsuarioRol


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: Session):
        super().__init__(Usuario, session)

    def get_all_active(self, rol: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Usuario]:
        """Obtiene usuarios activos. Si se pasa rol, hace un JOIN filtrando por rol en SQL."""
        stmt = select(Usuario).where(Usuario.deleted_at == None)
        if rol:
            stmt = stmt.join(UsuarioRol, Usuario.id == UsuarioRol.usuario_id).where(UsuarioRol.rol_codigo == rol)
        stmt = stmt.offset(skip).limit(limit)
        return list(self.session.exec(stmt).all())

    def get_by_email(self, email: str) -> Optional[Usuario]:
        return self.session.exec(
            select(Usuario).where(
                Usuario.email == email,
                Usuario.deleted_at == None
            )
        ).first()

    def get_by_email_any(self, email: str) -> Optional[Usuario]:
        """Busca por email incluyendo usuarios eliminados (para validar unicidad)."""
        return self.session.exec(
            select(Usuario).where(Usuario.email == email)
        ).first()

    def get_roles_codes(self, usuario_id: int) -> List[str]:
        statement = (
            select(Rol.codigo)
            .join(UsuarioRol)
            .where(UsuarioRol.usuario_id == usuario_id)
        )
        return list(self.session.exec(statement).all())


class RolRepository(BaseRepository[Rol]):
    def __init__(self, session: Session):
        super().__init__(Rol, session)

    def get_by_codigo(self, codigo: str) -> Optional[Rol]:
        return self.session.get(Rol, codigo)


class UsuarioRolRepository(BaseRepository[UsuarioRol]):
    def __init__(self, session: Session):
        super().__init__(UsuarioRol, session)

    def delete_all_for_user(self, usuario_id: int) -> None:
        """Elimina todos los roles asignados a un usuario."""
        statement = delete(UsuarioRol).where(UsuarioRol.usuario_id == usuario_id)
        self.session.exec(statement)
        self.session.flush()
