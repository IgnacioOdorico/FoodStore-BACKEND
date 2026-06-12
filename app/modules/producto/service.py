from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlmodel import select, func

from app.core.uow import UnitOfWork
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria, ProductoIngrediente
from app.modules.producto.schemas import (
    ProductoCreate,
    ProductoUpdate,
    ProductoReadWithDetails,
)


class ProductoService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def list_productos(
        self,
        nombre: Optional[str] = None,
        disponible: Optional[bool] = None,
        categoria_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ProductoReadWithDetails], int]:
        """Devuelve (items, total) para paginación."""
        statement = select(Producto).where(Producto.deleted_at == None)  # noqa: E711
        count_stmt = select(func.count(Producto.id)).where(Producto.deleted_at == None)  # noqa: E711

        if nombre:
            statement = statement.where(Producto.nombre.contains(nombre))
            count_stmt = count_stmt.where(Producto.nombre.contains(nombre))
        if disponible is not None:
            statement = statement.where(Producto.disponible == disponible)
            count_stmt = count_stmt.where(Producto.disponible == disponible)

        if categoria_id is not None:
            statement = (
                statement.join(ProductoCategoria, ProductoCategoria.producto_id == Producto.id)
                .where(ProductoCategoria.categoria_id == categoria_id)
                .distinct()
            )
            count_stmt = (
                count_stmt.join(ProductoCategoria, ProductoCategoria.producto_id == Producto.id)
                .where(ProductoCategoria.categoria_id == categoria_id)
            )

        total = self.uow.session.exec(count_stmt).one()
        statement = statement.offset(skip).limit(limit)
        items = self.uow.session.exec(statement).all()
        return [self._get_with_details(i.id) for i in items], total

    def get_producto(self, id: int) -> Optional[ProductoReadWithDetails]:
        producto = self.uow.productos.get_by_id(id)
        if not producto or producto.deleted_at:
            return None
        return self._get_with_details(id)

    def create_producto(self, data: ProductoCreate) -> ProductoReadWithDetails:
        prod_data = data.model_dump(exclude={"categoria_ids", "ingredientes_receta"})
        producto = Producto(**prod_data)

        self.uow.productos.add(producto)
        self.uow.session.flush()

        for idx, cat_id in enumerate(data.categoria_ids):
            self.uow.session.add(ProductoCategoria(
                producto_id=producto.id,
                categoria_id=cat_id,
                es_principal=(idx == 0),
            ))

        for ing_item in data.ingredientes_receta:
            self.uow.session.add(ProductoIngrediente(
                producto_id=producto.id,
                ingrediente_id=ing_item.id,
                cantidad=ing_item.cantidad,
                unidad_medida_id=ing_item.unidad_medida_id,
                es_removible=ing_item.es_removible,
            ))

        return self._get_with_details(producto.id)

    def update_producto(self, id: int, data: ProductoUpdate) -> Optional[ProductoReadWithDetails]:
        producto = self.uow.productos.get_by_id(id)
        if not producto or producto.deleted_at:
            return None

        update_data = data.model_dump(
            exclude_unset=True,
            exclude={"categoria_ids", "ingredientes_receta"},
        )
        for key, value in update_data.items():
            setattr(producto, key, value)
        producto.updated_at = datetime.now(timezone.utc)

        if data.categoria_ids is not None:
            for old in self.uow.session.exec(
                select(ProductoCategoria).where(ProductoCategoria.producto_id == id)
            ).all():
                self.uow.session.delete(old)
            for idx, cat_id in enumerate(data.categoria_ids):
                self.uow.session.add(ProductoCategoria(
                    producto_id=id,
                    categoria_id=cat_id,
                    es_principal=(idx == 0),
                ))

        if data.ingredientes_receta is not None:
            for old in self.uow.session.exec(
                select(ProductoIngrediente).where(ProductoIngrediente.producto_id == id)
            ).all():
                self.uow.session.delete(old)
            for ing_item in data.ingredientes_receta:
                self.uow.session.add(ProductoIngrediente(
                    producto_id=id,
                    ingrediente_id=ing_item.id,
                    cantidad=ing_item.cantidad,
                    unidad_medida_id=ing_item.unidad_medida_id,
                    es_removible=ing_item.es_removible,
                ))

        self.uow.productos.update(producto)
        return self._get_with_details(id)

    def set_disponibilidad(self, id: int, disponible: bool) -> Optional[ProductoReadWithDetails]:
        """PATCH /disponibilidad — activa/desactiva un producto (ADMIN o STOCK)."""
        producto = self.uow.productos.get_by_id(id)
        if not producto or producto.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Producto no encontrado",
            )
        producto.disponible = disponible
        producto.updated_at = datetime.now(timezone.utc)
        self.uow.productos.update(producto)
        return self._get_with_details(id)

    def delete_producto(self, id: int) -> bool:
        """Soft delete."""
        producto = self.uow.productos.get_by_id(id)
        if not producto or producto.deleted_at:
            return False
        producto.deleted_at = datetime.now(timezone.utc)
        self.uow.productos.update(producto)
        return True


    def _get_with_details(self, id: int) -> ProductoReadWithDetails:
        producto = self.uow.session.get(Producto, id)
        dto = ProductoReadWithDetails.model_validate(producto)

        for cat_dto in dto.categorias:
            link = self.uow.session.exec(
                select(ProductoCategoria).where(
                    ProductoCategoria.producto_id == id,
                    ProductoCategoria.categoria_id == cat_dto.id,
                )
            ).first()
            if link:
                cat_dto.es_principal = link.es_principal

        for ing_dto in dto.ingredientes:
            link = self.uow.session.exec(
                select(ProductoIngrediente).where(
                    ProductoIngrediente.producto_id == id,
                    ProductoIngrediente.ingrediente_id == ing_dto.id,
                )
            ).first()
            if link:
                ing_dto.cantidad = link.cantidad
                ing_dto.unidad_medida_id = link.unidad_medida_id
                ing_dto.es_removible = link.es_removible

        return dto
