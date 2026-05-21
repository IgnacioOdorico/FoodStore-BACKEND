from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import select

from app.core.uow import UnitOfWork
from app.modules.ingrediente.models import Ingrediente
from app.modules.ingrediente.schemas import IngredienteCreate, IngredienteUpdate, IngredienteRead


class IngredienteService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def list_ingredientes(
        self,
        nombre: Optional[str] = None,
        es_alergeno: Optional[bool] = None,
    ) -> List[IngredienteRead]:
        statement = select(Ingrediente)
        if nombre:
            statement = statement.where(Ingrediente.nombre.contains(nombre))
        if es_alergeno is not None:
            statement = statement.where(Ingrediente.es_alergeno == es_alergeno)
        items = self.uow.session.exec(statement).all()
        return [IngredienteRead.model_validate(i) for i in items]

    def create_ingrediente(self, data: IngredienteCreate) -> IngredienteRead:
        existing = self.uow.session.exec(
            select(Ingrediente).where(Ingrediente.nombre == data.nombre)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un ingrediente con ese nombre",
            )

        ingrediente = Ingrediente(**data.model_dump())
        self.uow.ingredientes.add(ingrediente)
        return IngredienteRead.model_validate(ingrediente)

    def get_ingrediente(self, id: int) -> Optional[IngredienteRead]:
        ingrediente = self.uow.ingredientes.get_by_id(id)
        return IngredienteRead.model_validate(ingrediente) if ingrediente else None

    def update_ingrediente(self, id: int, data: IngredienteUpdate) -> Optional[IngredienteRead]:
        ingrediente = self.uow.ingredientes.get_by_id(id)
        if not ingrediente:
            return None

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(ingrediente, key, value)
        ingrediente.updated_at = datetime.now(timezone.utc)

        self.uow.ingredientes.update(ingrediente)
        return IngredienteRead.model_validate(ingrediente)

    ## Hard delete
    def delete_ingrediente(self, id: int) -> bool:
        ingrediente = self.uow.ingredientes.get_by_id(id)
        if not ingrediente:
            return False
        self.uow.session.delete(ingrediente)
        return True
