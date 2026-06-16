import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import HTTPException, status

from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_refresh_token,
)
from app.core.uow import UnitOfWork
from app.core.config import settings
from app.modules.usuarios.model import Usuario, UsuarioRol, RefreshToken
from app.modules.usuarios.schemas import UserCreate, Token, TokenConRefresh, UserPublic, UserUpdate, AdminUserCreate, AdminUserUpdate, PasswordChange


class UsuarioService:

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def register(self, user_in: UserCreate) -> UserPublic:
        """Registra un nuevo usuario con el rol 'CLIENT' por defecto."""
        
        existing_user = self.uow.usuarios.get_by_email_any(user_in.email)
        
        if existing_user:
            if existing_user.deleted_at is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El email ya está registrado",
                )
            else:
                existing_user.deleted_at = None
                existing_user.nombre = user_in.nombre
                existing_user.apellido = user_in.apellido
                existing_user.celular = user_in.celular
                existing_user.password_hash = hash_password(user_in.password)
                
                user_db = self.uow.usuarios.update(existing_user)
                self.uow.usuarios_roles.delete_all_for_user(user_db.id)
                self.uow.session.flush()
        else:
            usuario = Usuario(
                nombre=user_in.nombre,
                apellido=user_in.apellido,
                email=user_in.email,
                celular=user_in.celular,
                password_hash=hash_password(user_in.password),
            )
            user_db = self.uow.usuarios.add(usuario)
            self.uow.session.flush() 

        rol_client = self.uow.roles.get_by_codigo("CLIENT")
        if not rol_client:
            from app.modules.usuarios.model import Rol
            rol_client = self.uow.roles.add(Rol(codigo="CLIENT", nombre="Cliente"))
            self.uow.session.flush()

        self.uow.usuarios_roles.add(UsuarioRol(
            usuario_id=user_db.id,
            rol_codigo="CLIENT"
        ))

        return self._to_public(user_db)

    def create_employee(self, data: AdminUserCreate) -> UserPublic:
        """Crea un nuevo empleado con los roles especificados (sin rol CLIENT)."""
        if not data.roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe especificarse al menos un rol",
            )

        STAFF_ROLES = {"ADMIN", "STOCK", "PEDIDOS"}
        for rol_codigo in data.roles:
            if rol_codigo not in STAFF_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Rol no permitido para empleados: {rol_codigo}",
                )

        if "ADMIN" in data.roles:
            existing_admin = self.uow.usuarios.get_admin()
            if existing_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Ya existe un administrador en el sistema. Solo puede haber uno.",
                )

        existing_user = self.uow.usuarios.get_by_email_any(data.email)
        
        if existing_user:
            if existing_user.deleted_at is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El email ya está registrado",
                )
            else:
                existing_user.deleted_at = None
                existing_user.nombre = data.nombre
                existing_user.apellido = data.apellido
                existing_user.celular = data.celular
                existing_user.password_hash = hash_password(data.password)
                
                user_db = self.uow.usuarios.update(existing_user)
                self.uow.usuarios_roles.delete_all_for_user(user_db.id)
                self.uow.session.flush()
        else:
            usuario = Usuario(
                nombre=data.nombre,
                apellido=data.apellido,
                email=data.email,
                celular=data.celular,
                password_hash=hash_password(data.password),
            )
            user_db = self.uow.usuarios.add(usuario)
            self.uow.session.flush()

        for rol_codigo in data.roles:
            self.uow.usuarios_roles.add(UsuarioRol(
                usuario_id=user_db.id,
                rol_codigo=rol_codigo,
            ))

        return self._to_public(user_db)

    def authenticate(self, email: str, password: str) -> TokenConRefresh:
        """Verifica credenciales y genera access + refresh tokens."""
        user = self.uow.usuarios.get_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cuenta de usuario eliminada",
            )

        roles = self.uow.usuarios.get_roles_codes(user.id)

        access_token = create_access_token(
            data={"sub": user.email, "roles": roles, "name": f"{user.nombre} {user.apellido}"}
        )

        refresh_jwt = create_refresh_token(data={"sub": user.email, "usuario_id": user.id})

        token_hash = hashlib.sha256(refresh_jwt.encode()).hexdigest()
        refresh_record = RefreshToken(
            usuario_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.uow.session.add(refresh_record)
        self.uow.session.flush()

        return TokenConRefresh(
            access_token=access_token,
            token_type="bearer",
            expires_in=30 * 60,
            refresh_token=refresh_jwt,
        )

    def refresh_session(self, refresh_token_str: str) -> TokenConRefresh:
        """Rota un refresh token: revoca el viejo, emite nuevos pares."""
        payload = decode_refresh_token(refresh_token_str)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido o expirado",
            )

        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
        stored = self.uow.session.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if not stored:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco no encontrado",
            )

        if stored.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco ya fue revocado",
            )

        if stored.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco expirado",
            )

        stored.revoked_at = datetime.now(timezone.utc)

        user = self.uow.usuarios.get_by_id(stored.usuario_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
            )

        roles = self.uow.usuarios.get_roles_codes(user.id)

        new_access = create_access_token(
            data={"sub": user.email, "roles": roles, "name": f"{user.nombre} {user.apellido}"}
        )
        new_refresh = create_refresh_token(data={"sub": user.email, "usuario_id": user.id})

        new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
        new_record = RefreshToken(
            usuario_id=user.id,
            token_hash=new_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.uow.session.add(new_record)
        self.uow.session.flush()

        return TokenConRefresh(
            access_token=new_access,
            token_type="bearer",
            expires_in=30 * 60,
            refresh_token=new_refresh,
        )

    def revoke_refresh(self, refresh_token_str: str) -> None:
        """Revoca un refresh token en BD."""
        if not refresh_token_str:
            return
        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
        stored = self.uow.session.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
            self.uow.session.flush()

    def logout_user(self) -> None:
        """No-op: con solo access token en cookie, el logout se maneja borrando la cookie."""
        pass

    def list_all(self, rol: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[UserPublic]:
        usuarios = self.uow.usuarios.get_all(rol=rol, skip=skip, limit=limit)
        return [self._to_public(u) for u in usuarios]

    def delete_user(self, user_id: int, current_admin_id: int) -> UserPublic:
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if user.id == current_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes eliminarte a ti mismo",
            )
        user.deleted_at = datetime.now(timezone.utc)
        updated = self.uow.usuarios.update(user)
        return self._to_public(updated)

    def update_user(self, user_id: int, data: AdminUserUpdate, current_admin_id: int) -> UserPublic:
        """Actualiza datos de cualquier usuario (admin). Permite cambiar email y roles."""
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        if user.id == current_admin_id and data.roles is not None and "ADMIN" not in data.roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes quitarte tu propio rol de administrador",
            )

        if data.nombre is not None:
            user.nombre = data.nombre
        if data.apellido is not None:
            user.apellido = data.apellido
        if data.celular is not None:
            user.celular = data.celular

        if data.email is not None and data.email != user.email:
            existing = self.uow.usuarios.get_by_email_any(data.email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El email ya está en uso por otro usuario",
                )
            user.email = data.email

        user.updated_at = datetime.now(timezone.utc)
        updated = self.uow.usuarios.update(user)

        if data.roles is not None:
            if "ADMIN" in data.roles:
                current_roles = self.uow.usuarios.get_roles_codes(user_id)
                if "ADMIN" not in current_roles:
                    existing_admin = self.uow.usuarios.get_admin()
                    if existing_admin:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Ya existe un administrador en el sistema. Solo puede haber uno.",
                        )
            
            self.uow.usuarios_roles.delete_all_for_user(user_id)
            for rol_codigo in data.roles:
                rol = self.uow.roles.get_by_codigo(rol_codigo)
                if not rol:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Rol desconocido: {rol_codigo}",
                    )
                self.uow.usuarios_roles.add(UsuarioRol(
                    usuario_id=user_id,
                    rol_codigo=rol_codigo,
                ))

        return self._to_public(updated)

    def reactivate_user(self, user_id: int) -> UserPublic:
        """Reactiva un usuario eliminado por soft-delete."""
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if not user.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya está activo",
            )
        user.deleted_at = None
        updated = self.uow.usuarios.update(user)
        return self._to_public(updated)


    def update_me(self, user_id: int, data: UserUpdate) -> UserPublic:
        """Actualiza los datos del usuario autenticado."""
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if data.nombre is not None:
            user.nombre = data.nombre
        if data.apellido is not None:
            user.apellido = data.apellido
        if data.celular is not None:
            user.celular = data.celular
        updated = self.uow.usuarios.update(user)
        return self._to_public(updated)


    def change_password(self, user_id: int, data: PasswordChange) -> None:
        """Cambia la contraseña del usuario autenticado, verificando la actual."""
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if not verify_password(data.password_actual, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual es incorrecta",
            )
        if len(data.password_nuevo) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La nueva contraseña debe tener al menos 8 caracteres",
            )
        user.password_hash = hash_password(data.password_nuevo)
        self.uow.usuarios.update(user)

    def _to_public(self, user: Usuario) -> UserPublic:
        roles = self.uow.usuarios.get_roles_codes(user.id)
        return UserPublic(
            id=user.id,
            nombre=user.nombre,
            apellido=user.apellido,
            email=user.email,
            celular=user.celular,
            roles=roles,
            created_at=user.created_at,
            deleted_at=user.deleted_at,
        )
