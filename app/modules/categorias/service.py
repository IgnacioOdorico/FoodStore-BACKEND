from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.uow import UnitOfWork
from app.modules.categorias.model import Categoria
from app.modules.categorias.schemas import (
    CategoriaCreate,
    CategoriaUpdate,
    CategoriaPublic,
)


class CategoriaService:

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def list_all(self, parent_id: Optional[int] = None) -> List[CategoriaPublic]:
        """Lista todas las categorías activas. Filtra por parent_id si se pasa."""
        categorias = self.uow.categorias.list_active(parent_id=parent_id)
        return [CategoriaPublic.model_validate(c) for c in categorias]

    def get_by_id(self, categoria_id: int) -> CategoriaPublic:
        categoria = self.uow.categorias.get_by_id(categoria_id)
        if not categoria or categoria.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada",
            )
        return CategoriaPublic.model_validate(categoria)

    def create(self, cat_in: CategoriaCreate) -> CategoriaPublic:
        if self.uow.categorias.get_by_nombre(cat_in.nombre):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una categoría con ese nombre",
            )

        categoria = Categoria.model_validate(cat_in)
        created = self.uow.categorias.add(categoria)
        return CategoriaPublic.model_validate(created)

    def update(self, categoria_id: int, cat_in: CategoriaUpdate) -> CategoriaPublic:
        categoria = self.uow.categorias.get_by_id(categoria_id)
        if not categoria or categoria.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada",
            )

        update_data = cat_in.model_dump(exclude_unset=True)

        if "nombre" in update_data:
            if self.uow.categorias.exists_nombre_excluding(
                update_data["nombre"], categoria_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe una categoría con ese nombre",
                )

        for key, value in update_data.items():
            setattr(categoria, key, value)
        categoria.updated_at = datetime.now(timezone.utc)

        updated = self.uow.categorias.update(categoria)
        return CategoriaPublic.model_validate(updated)

    def delete(self, categoria_id: int) -> None:
        categoria = self.uow.categorias.get_by_id(categoria_id)
        if not categoria or categoria.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada",
            )

        if self.uow.categorias.count_productos_activos(categoria_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar: la categoría tiene productos activos asociados",
            )

        categoria.deleted_at = datetime.now(timezone.utc)
        self.uow.categorias.update(categoria)
