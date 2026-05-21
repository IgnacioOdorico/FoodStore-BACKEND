from typing import Annotated, List

from fastapi import APIRouter, Depends, Query

from app.core.uow import UnitOfWork, get_uow
from app.modules.catalogos.models import (
    UnidadMedidaPublic,
    EstadoPedidoPublic,
    FormaPagoPublic,
)
from app.modules.catalogos.service import CatalogoService

router = APIRouter(prefix="/api/v1/catalogos", tags=["catalogos"])


@router.get("/unidades-medida", response_model=List[UnidadMedidaPublic])
def listar_unidades_medida(uow: Annotated[UnitOfWork, Depends(get_uow)]):
    with uow:
        return CatalogoService(uow).list_unidades()


@router.get("/estados-pedido", response_model=List[EstadoPedidoPublic])
def listar_estados_pedido(uow: Annotated[UnitOfWork, Depends(get_uow)]):
    with uow:
        return CatalogoService(uow).list_estados_pedido()


@router.get("/formas-pago", response_model=List[FormaPagoPublic])
def listar_formas_pago(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    solo_habilitadas: Annotated[bool, Query(description="Devolver solo las habilitadas")] = False,
):
    with uow:
        return CatalogoService(uow).list_formas_pago(solo_habilitadas=solo_habilitadas)
