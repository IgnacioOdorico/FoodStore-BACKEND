from typing import List, Optional

from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.categorias.model import Categoria


class CategoriaRepository(BaseRepository[Categoria]):

    def __init__(self, session: Session):
        super().__init__(Categoria, session)

    def list_active(self, parent_id: Optional[int] = None, *, offset: int = 0, limit: int = 100) -> List[Categoria]:
        statement = select(Categoria).where(Categoria.deleted_at == None)  # noqa: E711
        if parent_id is not None:
            statement = statement.where(Categoria.parent_id == parent_id)
        statement = statement.offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def count_active(self, parent_id: Optional[int] = None) -> int:
        from sqlmodel import func
        statement = select(func.count(Categoria.id)).where(Categoria.deleted_at == None)  # noqa: E711
        if parent_id is not None:
            statement = statement.where(Categoria.parent_id == parent_id)
        return self.session.exec(statement).one()

    def get_by_nombre(self, nombre: str) -> Categoria | None:
        return self.session.exec(
            select(Categoria).where(Categoria.nombre == nombre)
        ).first()

    def exists_nombre_excluding(self, nombre: str, exclude_id: int) -> bool:
        result = self.session.exec(
            select(Categoria).where(
                Categoria.nombre == nombre,
                Categoria.id != exclude_id,
            )
        ).first()
        return result is not None

    def list_active_children(self, parent_id: int) -> List[Categoria]:
        """Devuelve subcategorías activas de un padre."""
        return list(self.session.exec(
            select(Categoria).where(
                Categoria.parent_id == parent_id,
                Categoria.deleted_at == None,  # noqa: E711
            )
        ).all())

    def count_productos_activos(self, categoria_id: int) -> int:
        from app.modules.producto.models import Producto
        from app.modules.producto.associations import ProductoCategoria

        statement = (
            select(Producto)
            .join(ProductoCategoria, ProductoCategoria.producto_id == Producto.id)
            .where(
                ProductoCategoria.categoria_id == categoria_id,
                Producto.deleted_at == None,  # noqa: E711
            )
        )
        return len(list(self.session.exec(statement).all()))
