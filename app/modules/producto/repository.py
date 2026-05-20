"""Repositorio de Producto."""

from sqlmodel import Session

from app.core.base_repository import BaseRepository
from app.modules.producto.models import Producto


class ProductoRepository(BaseRepository[Producto]):

    def __init__(self, session: Session):
        super().__init__(Producto, session)
