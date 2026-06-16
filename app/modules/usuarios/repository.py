from datetime import datetime, timezone
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

    def get_all(self, rol: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Usuario]:
        """Obtiene TODOS los usuarios (activos e inactivos). Si se pasa rol, filtra por rol."""
        stmt = select(Usuario)
        if rol:
            stmt = stmt.join(UsuarioRol, Usuario.id == UsuarioRol.usuario_id).where(UsuarioRol.rol_codigo == rol)
        stmt = stmt.offset(skip).limit(limit)
        return list(self.session.exec(stmt).all())

    def get_admin(self) -> Optional[Usuario]:
        """Obtiene el usuario administrador (si existe)."""
        stmt = (
            select(Usuario)
            .join(UsuarioRol, Usuario.id == UsuarioRol.usuario_id)
            .where(
                UsuarioRol.rol_codigo == "ADMIN",
                Usuario.deleted_at == None
            )
        )
        return self.session.exec(stmt).first()

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


class RefreshTokenRepository(BaseRepository["RefreshToken"]):
    def __init__(self, session: Session):
        from app.modules.usuarios.model import RefreshToken
        super().__init__(RefreshToken, session)

    def get_by_hash(self, token_hash: str) -> Optional["RefreshToken"]:
        from app.modules.usuarios.model import RefreshToken
        return self.session.exec(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).first()

    def revoke_all_for_user(self, usuario_id: int) -> None:
        from app.modules.usuarios.model import RefreshToken
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.usuario_id == usuario_id,
                RefreshToken.revoked_at == None,
            )
        )
        now = datetime.now(timezone.utc)
        for token in self.session.exec(stmt).all():
            token.revoked_at = now
        self.session.flush()


class UsuarioRolRepository(BaseRepository[UsuarioRol]):
    def __init__(self, session: Session):
        super().__init__(UsuarioRol, session)

    def delete_all_for_user(self, usuario_id: int) -> None:
        """Elimina todos los roles asignados a un usuario."""
        statement = delete(UsuarioRol).where(UsuarioRol.usuario_id == usuario_id)
        self.session.exec(statement)
        self.session.flush()
