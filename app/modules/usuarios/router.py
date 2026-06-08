import logging
import traceback
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, status, Response, Query
from fastapi.security import OAuth2PasswordRequestForm

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user, require_role
from app.core.config import settings
from app.modules.usuarios.schemas import (
    UserCreate, UserPublic, Token, UserUpdate,
    AdminUserCreate, AdminUserUpdate, PasswordChange,
)
from app.modules.usuarios.service import UsuarioService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/v1/admin/usuarios", tags=["admin-usuarios"])

logger = logging.getLogger(__name__)

_ACCESS_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


# Auth pública

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Registra un nuevo usuario con rol CLIENT."""
    with uow:
        service = UsuarioService(uow)
        return service.register(user_in)


@router.post("/token")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    response: Response,
):
    """Login: emite access_token como cookie httpOnly."""
    try:
        logger.info(f"[LOGIN] Attempting login for: {form_data.username}")
        with uow:
            service = UsuarioService(uow)
            token = service.authenticate(form_data.username, form_data.password)
            response.set_cookie(
                key="access_token",
                value=token.access_token,
                httponly=True,
                max_age=_ACCESS_MAX_AGE,
                samesite="lax",
                secure=False,
            )
            logger.info(f"[LOGIN] OK for: {form_data.username}")
            return {"mensaje": "Login exitoso", "user_email": form_data.username}
    except Exception as e:
        logger.error(f"[LOGIN ERROR] {e}\n{traceback.format_exc()}")
        raise


@router.post("/logout")
def logout(response: Response):
    """Cierra la sesión eliminando la cookie de acceso."""
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    return {"mensaje": "Sesión cerrada"}


# Perfil del usuario autenticado

@router.get("/me", response_model=UserPublic)
def read_me(
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
):
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_me(
    data: UserUpdate,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Actualiza nombre, apellido y celular del usuario autenticado."""
    with uow:
        service = UsuarioService(uow)
        return service.update_me(current_user.id, data)


@router.patch("/me/password", status_code=204)
def change_password(
    data: PasswordChange,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Cambia la contraseña del usuario autenticado."""
    with uow:
        service = UsuarioService(uow)
        service.change_password(current_user.id, data)


# Administración de usuarios (solo ADMIN)

@admin_router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_employee(
    data: AdminUserCreate,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Crea un empleado con los roles indicados. Solo ADMIN."""
    with uow:
        service = UsuarioService(uow)
        return service.create_employee(data)


@admin_router.get("", response_model=List[UserPublic])
def list_users(
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    rol: Annotated[Optional[str], Query(description="Filtrar por rol")] = None,
    skip: Annotated[int, Query(ge=0, description="Offset de paginación")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Límite de resultados")] = 100,
):
    with uow:
        service = UsuarioService(uow)
        return service.list_all(rol=rol, skip=skip, limit=limit)


@admin_router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        service = UsuarioService(uow)
        return service.update_user(user_id, data)


@admin_router.post("/{user_id}/reactivar", response_model=UserPublic)
def reactivate_user(
    user_id: int,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        service = UsuarioService(uow)
        return service.reactivate_user(user_id)


@admin_router.delete("/{user_id}", response_model=UserPublic)
def delete_user(
    user_id: int,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        service = UsuarioService(uow)
        return service.delete_user(user_id)
