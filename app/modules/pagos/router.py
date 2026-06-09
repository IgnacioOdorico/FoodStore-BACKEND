from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/pagos", tags=["pagos"])

@router.post("/crear")
async def crear_pago():
    pass

@router.post("/webhook")
async def webhook_mercadopago():
    pass

@router.get("/{pedido_id}")
async def obtener_pago(pedido_id: int):
    pass
