from typing import Annotated, List
from fastapi import APIRouter, Depends, status, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user, require_role
from app.modules.usuarios.schemas import UserCreate, UserPublic, Token, UserUpdate, PasswordChange
from app.modules.usuarios.service import UsuarioService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    """Registra un nuevo usuario."""
    with uow:
        service = UsuarioService(uow)
        return service.register(user_in)


@router.post("/token")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    response: Response,
):

    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[LOGIN] Attempting login for: {form_data.username}")
        
        with uow:
            service = UsuarioService(uow)
            # El formulario de FastAPI usa el campo 'username' para el identificador
            token = service.authenticate(form_data.username, form_data.password)
            logger.info(f"[LOGIN] Authentication successful for: {form_data.username}")

            response.set_cookie(
                key="access_token",
                value=token.access_token,
                httponly=True,
                max_age=token.expires_in,
                samesite="lax",
                secure=False,
            )
            return {"mensaje": "Login exitoso", "user_email": form_data.username}
    except Exception as e:
        import traceback
        logger.error(f"[LOGIN ERROR] {str(e)}")
        logger.error(traceback.format_exc())
        raise


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    return {"mensaje": "Sesión cerrada"}


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

@router.get("/admin/usuarios", response_model=List[UserPublic])
def list_users(
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        service = UsuarioService(uow)
        return service.list_all()


@router.delete("/admin/usuarios/{user_id}", response_model=UserPublic)
def delete_user(
    user_id: int,
    _admin: Annotated[UserPublic, Depends(require_role(["ADMIN"]))],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        service = UsuarioService(uow)
        return service.delete_user(user_id)
