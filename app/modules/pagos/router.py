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


import hmac
import hashlib

def _verify_hmac(request: Request, data_id: str) -> bool:
    """Valida la firma HMAC de MercadoPago."""
    if not settings.MP_WEBHOOK_SECRET:
        logger.warning("MP_WEBHOOK_SECRET no configurado, omitiendo validación HMAC")
        return True
        
    x_signature = request.headers.get("x-signature")
    x_request_id = request.headers.get("x-request-id")
    
    if not x_signature or not x_request_id:
        logger.warning("Faltan headers x-signature o x-request-id en webhook de MP")
        return False
        
    try:
        parts = dict(p.split("=") for p in x_signature.split(","))
        ts = parts.get("ts")
        v1 = parts.get("v1")
        
        if not ts or not v1:
            return False
            
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        hmac_calc = hmac.new(
            settings.MP_WEBHOOK_SECRET.encode(),
            manifest.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(hmac_calc, v1)
    except Exception:
        return False

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
                
        # Extraer el ID para validación HMAC
        data_id = str(data.get("data", {}).get("id", ""))
        if not data_id:
            data_id = str(query_params.get("data.id", ""))
            
        if data_id and not _verify_hmac(request, data_id):
            logger.error("Validación HMAC fallida en webhook de MP")
            # Devolvemos 200 para que MP no reintente un payload modificado,
            # o podríamos devolver 403. MP recomienda 200 o 400.
            return {"status": "error", "reason": "invalid_signature"}

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
    frontend = settings.VITE_FRONTEND_URL or "http://localhost:5174"
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
