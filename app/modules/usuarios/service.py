from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.core.uow import UnitOfWork
from app.modules.usuarios.model import Usuario, UsuarioRol
from app.modules.usuarios.schemas import UserCreate, Token, UserPublic, UserUpdate, AdminUserCreate, AdminUserUpdate, PasswordChange


class UsuarioService:

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def register(self, user_in: UserCreate) -> UserPublic:
        """Registra un nuevo usuario con el rol 'CLIENT' por defecto."""
        
        if self.uow.usuarios.get_by_email(user_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya está registrado",
            )

        # 1. Crear el usuario
        usuario = Usuario(
            nombre=user_in.nombre,
            apellido=user_in.apellido,
            email=user_in.email,
            celular=user_in.celular,
            password_hash=hash_password(user_in.password),
        )

        user_db = self.uow.usuarios.add(usuario)
        self.uow.commit() 

        # 2. Asignar rol CLIENT por defecto 
        rol_client = self.uow.roles.get_by_codigo("CLIENT")
        if not rol_client:
            from app.modules.usuarios.model import Rol
            rol_client = self.uow.roles.add(Rol(codigo="CLIENT", nombre="Cliente"))
            self.uow.commit()

        self.uow.usuarios_roles.add(UsuarioRol(
            usuario_id=user_db.id,
            rol_codigo="CLIENT"
        ))

        # 3. Retornar vista pública con roles
        return self._to_public(user_db)

    def create_employee(self, data: AdminUserCreate) -> UserPublic:
        """Crea un nuevo empleado con los roles especificados (sin rol CLIENT)."""
        if self.uow.usuarios.get_by_email_any(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya está registrado",
            )

        if not data.roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe especificarse al menos un rol",
            )

        # Validar que los roles existan y sean de staff
        STAFF_ROLES = {"ADMIN", "STOCK", "PEDIDOS"}
        for rol_codigo in data.roles:
            if rol_codigo not in STAFF_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Rol no permitido para empleados: {rol_codigo}",
                )

        usuario = Usuario(
            nombre=data.nombre,
            apellido=data.apellido,
            email=data.email,
            celular=data.celular,
            password_hash=hash_password(data.password),
        )
        user_db = self.uow.usuarios.add(usuario)
        self.uow.commit()

        for rol_codigo in data.roles:
            self.uow.usuarios_roles.add(UsuarioRol(
                usuario_id=user_db.id,
                rol_codigo=rol_codigo,
            ))

        return self._to_public(user_db)

    def authenticate(self, email: str, password: str) -> Token:
        """Verifica credenciales y genera un access token."""
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

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def list_all(self) -> List[UserPublic]:
        usuarios = self.uow.usuarios.get_all()
        return [self._to_public(u) for u in usuarios]

    def delete_user(self, user_id: int) -> UserPublic:
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        user.deleted_at = datetime.now(timezone.utc)
        updated = self.uow.usuarios.update(user)
        return self._to_public(updated)

    def update_user(self, user_id: int, data: AdminUserUpdate) -> UserPublic:
        """Actualiza datos de cualquier usuario (admin). Permite cambiar email y roles."""
        user = self.uow.usuarios.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        # Campos básicos
        if data.nombre is not None:
            user.nombre = data.nombre
        if data.apellido is not None:
            user.apellido = data.apellido
        if data.celular is not None:
            user.celular = data.celular

        # Cambio de email — verificar unicidad
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

        # Cambio de roles — reemplazar todos los roles actuales
        if data.roles is not None:
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
