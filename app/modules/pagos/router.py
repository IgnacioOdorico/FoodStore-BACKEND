import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.uow import UnitOfWork, get_uow
from app.core.deps import get_current_active_user
from app.modules.usuarios.schemas import UserPublic
from app.modules.pagos.schemas import (
    CrearPagoRequest,
    ConfirmarPagoRequest,
    PagoCrearResponse,
    PagoEstadoResponse,
    PagoRead,
)
from app.modules.pagos.service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pagos", tags=["pagos"])


@router.post(
    "/crear", response_model=PagoCrearResponse, status_code=status.HTTP_201_CREATED
)
def crear_pago(
    data: CrearPagoRequest,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return PaymentService(uow).crear_pago(current_user.id, data.pedido_id)


@router.post("/webhook")
async def webhook(
    request: Request,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):

    try:
        query_params = dict(request.query_params)
        ctype = request.headers.get("content-type", "")
        if ctype.startswith("application/json"):
            data = await request.json()
        else:
            try:
                data = dict(await request.form())
            except Exception:
                data = {}
        with uow:
            return await PaymentService(uow).procesar_webhook(
                data, query_params=query_params
            )
    except Exception as e:
        logger.exception("Error en webhook MP")
        return {"status": "error", "reason": str(e)}


@router.post("/confirm", response_model=PagoEstadoResponse)
async def confirm_pago(
    data: ConfirmarPagoRequest,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):
    with uow:
        return await PaymentService(uow).confirmar_pago(data.pedido_id, data.payment_id)


@router.get("/redirect/{pedido_id}/{estado}")
def redirect_post_pago(pedido_id: int, estado: str, request: Request):
    frontend = settings.VITE_FRONTEND_URL or "http://localhost:5173"
    qs = request.url.query
    url = f"{frontend}/orders/{pedido_id}/{estado}"
    if qs:
        url += f"?{qs}"
    return RedirectResponse(url=url)


@router.get("/{pedido_id}", response_model=PagoRead)
def get_pago(
    pedido_id: int,
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
):

    with uow:
        return PaymentService(uow).get_pago_de_pedido(
            pedido_id, current_user.id, current_user.roles
        )
