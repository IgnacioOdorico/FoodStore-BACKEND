from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.uow import UnitOfWork
from app.modules.categorias.model import Categoria
from app.modules.categorias.schemas import (
    CategoriaCreate,
    CategoriaUpdate,
    CategoriaPublic,
    PaginatedCategorias,
)


class CategoriaService:

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def list_all(self, parent_id: Optional[int] = None, *, skip: int = 0, limit: int = 100) -> PaginatedCategorias:
        categorias = self.uow.categorias.list_active(parent_id=parent_id, offset=skip, limit=limit)
        total = self.uow.categorias.count_active(parent_id=parent_id)
        return PaginatedCategorias(
            items=[CategoriaPublic.model_validate(c) for c in categorias],
            total=total,
            skip=skip,
            limit=limit,
        )

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

        # Bloquear si la categoría padre tiene productos activos
        if self.uow.categorias.count_productos_activos(categoria_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar: la categoría tiene productos activos asociados",
            )

        # Obtener subcategorías activas
        subcategorias = self.uow.categorias.list_active_children(categoria_id)

        # Bloquear si alguna subcategoría tiene productos activos
        subcategorias_con_productos = [
            s for s in subcategorias
            if self.uow.categorias.count_productos_activos(s.id) > 0
        ]
        if subcategorias_con_productos:
            nombres = ", ".join(s.nombre for s in subcategorias_con_productos)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"No se puede eliminar: las siguientes subcategorías tienen "
                    f"productos activos asociados: {nombres}"
                ),
            )

        # Cascade soft-delete: eliminar subcategorías activas primero
        now = datetime.now(timezone.utc)
        for sub in subcategorias:
            sub.deleted_at = now
            self.uow.categorias.update(sub)

        # Soft-delete de la categoría padre
        categoria.deleted_at = now
        self.uow.categorias.update(categoria)
