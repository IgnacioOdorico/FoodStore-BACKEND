from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status

from app.core.uow import UnitOfWork
from app.modules.direcciones.models import DireccionEntrega
from app.modules.direcciones.schemas import (
    DireccionCreate,
    DireccionUpdate,
    DireccionPublic,
)


class DireccionService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def list_mine(self, usuario_id: int) -> List[DireccionPublic]:
        items = self.uow.direcciones.list_by_usuario(usuario_id)
        return [DireccionPublic.model_validate(d) for d in items]

    def get_mine(self, usuario_id: int, direccion_id: int) -> DireccionPublic:
        direccion = self._get_owned(usuario_id, direccion_id)
        return DireccionPublic.model_validate(direccion)

    def create(self, usuario_id: int, data: DireccionCreate) -> DireccionPublic:
        # Si es la primera dirección del usuario, marcamos como principal
        existing = self.uow.direcciones.list_by_usuario(usuario_id)
        es_principal = data.es_principal or len(existing) == 0

        if es_principal:
            self.uow.direcciones.unset_principal(usuario_id)

        direccion = DireccionEntrega(
            usuario_id=usuario_id,
            **{k: v for k, v in data.model_dump().items() if k != "es_principal"},
            es_principal=es_principal,
        )
        created = self.uow.direcciones.add(direccion)
        return DireccionPublic.model_validate(created)

    def update(self, usuario_id: int, direccion_id: int, data: DireccionUpdate) -> DireccionPublic:
        direccion = self._get_owned(usuario_id, direccion_id)

        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(direccion, k, v)
        direccion.updated_at = datetime.now(timezone.utc)

        updated = self.uow.direcciones.update(direccion)
        return DireccionPublic.model_validate(updated)

    def set_principal(self, usuario_id: int, direccion_id: int) -> DireccionPublic:
        direccion = self._get_owned(usuario_id, direccion_id)

        self.uow.direcciones.unset_principal(usuario_id)
        direccion.es_principal = True
        direccion.updated_at = datetime.now(timezone.utc)
        updated = self.uow.direcciones.update(direccion)
        return DireccionPublic.model_validate(updated)

    def delete(self, usuario_id: int, direccion_id: int) -> None:
        direccion = self._get_owned(usuario_id, direccion_id)
        direccion.deleted_at = datetime.now(timezone.utc)
        direccion.es_principal = False
        self.uow.direcciones.update(direccion)

    def _get_owned(self, usuario_id: int, direccion_id: int) -> DireccionEntrega:
        direccion = self.uow.direcciones.get_by_id(direccion_id)
        if not direccion or direccion.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dirección no encontrada",
            )
        if direccion.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso sobre esta dirección",
            )
        return direccion
