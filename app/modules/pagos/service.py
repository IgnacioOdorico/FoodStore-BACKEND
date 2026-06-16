import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.uow import UnitOfWork
from app.modules.pagos.models import Pago
from app.modules.pagos.schemas import (
    PagoCrearResponse,
    PagoEstadoResponse,
    PagoRead,
)

logger = logging.getLogger(__name__)


def _map_estado_mp(estado_mp: Optional[str]) -> Optional[str]:
    if estado_mp == "approved":
        return "aprobado"
    if estado_mp in ("rejected", "cancelled", "refunded", "charged_back"):
        return "rechazado"
    if estado_mp in ("pending", "in_process", "authorized"):
        return "pendiente"
    return None


class PaymentService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def _access_token(self) -> Optional[str]:
        return settings.MP_ACCESS_TOKEN

    def _public_key(self) -> Optional[str]:
        return settings.MP_PUBLIC_KEY

    def _crear_preferencia_mp(
        self,
        monto: float,
        titulo: str,
        external_reference: str,
        pedido_id: int,
        idempotency_key: str,
    ) -> dict:
        """Crea una preferencia en MP. Devuelve {preference_id, init_point}."""
        access_token = self._access_token()
        if not access_token:
            raise RuntimeError(
                "MercadoPago no está configurado. Defina MP_ACCESS_TOKEN en .env"
            )

        try:
            import mercadopago

            sdk = mercadopago.SDK(access_token)
            public_base = settings.NGROK_URL or None
            base = public_base or settings.VITE_API_URL or "http://localhost:8000"
            back_urls = {
                "success": f"{base}/api/v1/pagos/redirect/{pedido_id}/success",
                "failure": f"{base}/api/v1/pagos/redirect/{pedido_id}/failure",
                "pending": f"{base}/api/v1/pagos/redirect/{pedido_id}/pending",
            }

            preference_data = {
                "items": [
                    {
                        "title": titulo,
                        "quantity": 1,
                        "unit_price": float(monto),
                        "currency_id": "ARS",
                    }
                ],
                "external_reference": external_reference,
                "back_urls": back_urls,
            }

            if public_base:
                preference_data["auto_return"] = "approved"

            notif_url = settings.MP_WEBHOOK_URL or (
                f"{public_base}/api/v1/pagos/webhook" if public_base else None
            )
            if notif_url:
                preference_data["notification_url"] = notif_url

            request_options = mercadopago.config.RequestOptions()
            request_options.custom_headers = {"x-idempotency-key": idempotency_key}

            result = sdk.preference().create(preference_data, request_options)
            if result.get("status") not in (200, 201):
                logger.error("Error creando preferencia MP: %s", result)
                msg = result.get("response", {}).get("message", "desconocido")
                raise RuntimeError(f"Error al crear preferencia: {msg}")

            resp = result.get("response", {})
            return {
                "preference_id": resp.get("id"),
                "init_point": resp.get("init_point"),
            }

        except ImportError:
            raise RuntimeError("Falta el SDK: pip install mercadopago")
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Error inesperado al crear preferencia MP")
            raise RuntimeError(f"Error de conexión con MP: {e}")

    def _consultar_pago_mp(self, payment_id: int) -> dict:
        access_token = self._access_token()
        if not access_token:
            raise RuntimeError("MercadoPago no configurado")

        try:
            import mercadopago

            sdk = mercadopago.SDK(access_token)
            result = sdk.payment().get(payment_id)
            if result.get("status") != 200:
                logger.error("Error consultando pago MP %s: %s", payment_id, result)
                raise RuntimeError(f"Error al consultar pago {payment_id}")

            resp = result.get("response", {})
            return {
                "mp_payment_id": resp.get("id"),
                "mp_status": resp.get("status"),
                "mp_status_detail": resp.get("status_detail"),
                "mp_merchant_order_id": resp.get("merchant_order_id"),
                "payment_method_id": resp.get("payment_method_id"),
                "external_reference": resp.get("external_reference"),
            }
        except ImportError:
            raise RuntimeError("Falta el SDK: pip install mercadopago")
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Error consultando pago MP %s", payment_id)
            raise RuntimeError(f"Error de conexión con MP: {e}")

    def crear_pago(self, usuario_id: int, pedido_id: int) -> PagoCrearResponse:

        pedido = self.uow.pedidos.get_by_id(pedido_id)
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
            )
        if pedido.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El pedido no pertenece al usuario",
            )
        if pedido.estado_codigo != "PENDIENTE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El pedido no admite pago (estado actual: {pedido.estado_codigo})",
            )
        if not self._access_token():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MercadoPago no configurado. Defina MP_ACCESS_TOKEN",
            )

        external_reference = str(uuid.uuid4())
        idempotency_key = str(uuid.uuid4())

        try:
            mp_data = self._crear_preferencia_mp(
                monto=pedido.total,
                titulo=f"Pedido #{pedido_id} - FoodStore",
                external_reference=external_reference,
                pedido_id=pedido_id,
                idempotency_key=idempotency_key,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        pago = Pago(
            pedido_id=pedido_id,
            transaction_amount=pedido.total,
            estado="pendiente",
            mp_status="pending",
            mp_preference_id=mp_data["preference_id"],
            mp_init_point=mp_data.get("init_point"),
            external_reference=external_reference,
            idempotency_key=idempotency_key,
        )
        self.uow.pagos.add(pago)

        if pedido.forma_pago_codigo != "MERCADOPAGO":
            pedido.forma_pago_codigo = "MERCADOPAGO"
            self.uow.pedidos.update(pedido)

        return PagoCrearResponse(
            pago_id=pago.id,
            preference_id=mp_data["preference_id"],
            init_point=mp_data.get("init_point"),
            public_key=self._public_key(),
        )

    async def procesar_webhook(
        self, data: dict, query_params: Optional[dict] = None
    ) -> dict:

        logger.info("Webhook MP: data=%s qs=%s", data, query_params or {})
        query_params = query_params or {}
        if not data:
            data = query_params

        topic = data.get("type") or data.get("topic") or query_params.get("topic")
        data_id = (
            data.get("data_id")
            or (data.get("data") or {}).get("id")
            or query_params.get("data.id")
            or query_params.get("id")
        )
        pago_mp_id = data_id or data.get("id")

        if not pago_mp_id:
            return {"status": "ignored", "reason": "sin payment id"}
        if topic not in (None, "payment", "merchant_order"):
            return {"status": "ignored", "reason": f"topic {topic}"}

        # merchant_order webhooks entregan un merchant_order_id, no un payment_id.
        # Las notificaciones de topic "payment" son más confiables y llegan por separado,
        # así que procesamos solo payment y omitimos merchant_order.
        if topic == "merchant_order":
            logger.info(
                "Ignorando merchant_order (se procesará vía payment): id=%s", pago_mp_id
            )
            return {"status": "ignored", "reason": "merchant_order skipped (payment topic is more reliable)"}

        try:
            mp_info = self._consultar_pago_mp(int(pago_mp_id))
        except RuntimeError as e:
            logger.warning("No se pudo consultar el pago MP: %s", e)
            return {"status": "error", "reason": str(e)}

        nuevo_estado = _map_estado_mp(mp_info.get("mp_status"))
        if nuevo_estado is None:
            return {"status": "ignored", "reason": f"status {mp_info.get('mp_status')}"}

        pago = self.uow.pagos.get_by_mp_payment_id(int(pago_mp_id))
        if not pago and mp_info.get("external_reference"):
            pago = self.uow.pagos.get_by_external_reference(
                mp_info["external_reference"]
            )
        if not pago and mp_info.get("mp_merchant_order_id"):
            pago = self.uow.pagos.get_by_mp_merchant_order_id(
                mp_info["mp_merchant_order_id"]
            )
        if not pago:
            return {"status": "ignored", "reason": "pago no encontrado"}

        es_mismo_pago = pago.mp_payment_id == int(pago_mp_id)
        
        if pago.estado == "aprobado" and nuevo_estado != "aprobado" and not es_mismo_pago:
            return {"status": "ok", "detail": "ya existe un intento aprobado", "estado": pago.estado}
            
        if pago.estado == nuevo_estado and es_mismo_pago:
            return {"status": "ok", "detail": "ya procesado", "estado": pago.estado}

        pago.mp_payment_id = int(pago_mp_id)
        pago.mp_status = mp_info.get("mp_status")
        pago.mp_status_detail = mp_info.get("mp_status_detail")
        pago.mp_merchant_order_id = mp_info.get("mp_merchant_order_id")
        pago.payment_method_id = mp_info.get("payment_method_id")
        pago.estado = nuevo_estado
        pago.updated_at = datetime.now(timezone.utc)
        self.uow.pagos.update(pago)

        sincronizado = self._sincronizar_pedido(pago, nuevo_estado)
        return {"status": "ok", "estado": nuevo_estado, "pedido_id": pago.pedido_id, "sincronizado": sincronizado}

    async def confirmar_pago(
        self, pedido_id: int, payment_id: Optional[int] = None
    ) -> PagoEstadoResponse:

        pedido = self.uow.pedidos.get_by_id(pedido_id)
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
            )

        resolved = payment_id
        if not resolved:
            ultimo = self.uow.pagos.get_ultimo_by_pedido(pedido_id)
            if ultimo and ultimo.mp_payment_id:
                resolved = ultimo.mp_payment_id

        if not resolved:
            ultimo = self.uow.pagos.get_ultimo_by_pedido(pedido_id)
            return PagoEstadoResponse(
                pedido_id=pedido_id,
                estado=ultimo.estado if ultimo else None,
            )

        try:
            mp_info = self._consultar_pago_mp(int(resolved))
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        nuevo_estado = _map_estado_mp(mp_info.get("mp_status")) or "pendiente"

        pago = self.uow.pagos.get_by_mp_payment_id(int(resolved))
        if not pago:
            pago = self.uow.pagos.get_ultimo_by_pedido(pedido_id)
            
        if pago:
            es_mismo_pago = (pago.mp_payment_id == int(resolved))
            actualizar = True
            
            if pago.estado == "aprobado" and nuevo_estado != "aprobado" and not es_mismo_pago:
                actualizar = False
            elif pago.estado == nuevo_estado and es_mismo_pago:
                actualizar = False
                
            if actualizar:
                pago.mp_payment_id = int(resolved)
                pago.mp_status = mp_info.get("mp_status")
                pago.mp_status_detail = mp_info.get("mp_status_detail")
                pago.mp_merchant_order_id = mp_info.get("mp_merchant_order_id")
                pago.payment_method_id = mp_info.get("payment_method_id")
                pago.estado = nuevo_estado
                pago.updated_at = datetime.now(timezone.utc)
                self.uow.pagos.update(pago)
                self._sincronizar_pedido(pago, nuevo_estado)

        return PagoEstadoResponse(pedido_id=pedido_id, estado=nuevo_estado)

    def get_pago_de_pedido(
        self, pedido_id: int, usuario_id: int, roles: list[str]
    ) -> PagoRead:

        pedido = self.uow.pedidos.get_by_id(pedido_id)
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
            )

        es_staff = bool({"ADMIN", "PEDIDOS"} & set(roles))
        if not es_staff and pedido.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este pago",
            )

        pago = self.uow.pagos.get_ultimo_by_pedido(pedido_id)
        if not pago:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El pedido no tiene pagos registrados",
            )
        return PagoRead.model_validate(pago)

    def _sincronizar_pedido(self, pago: Pago, nuevo_estado: str) -> bool:

        if nuevo_estado not in ("aprobado",):
            return False

        pedido = self.uow.pedidos.get_by_id(pago.pedido_id)
        if not pedido or pedido.estado_codigo != "PENDIENTE":
            return False

        estado_hacia = "CONFIRMADO"
        motivo = "Pago aprobado por MercadoPago"

        from app.modules.pedidos.service import PedidoService

        PedidoService(self.uow).avanzar_estado(
            pedido_id=pago.pedido_id,
            estado_hacia=estado_hacia,
            usuario_id=None,
            motivo=motivo,
        )
        return True
