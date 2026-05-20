"""Unit of Work — gestión de transacción."""

from sqlmodel import Session

from app.core.database import engine
from app.modules.usuarios.repository import UsuarioRepository, RolRepository, UsuarioRolRepository
from app.modules.categorias.repository import CategoriaRepository
from app.modules.producto.repository import ProductoRepository
from app.modules.ingrediente.repository import IngredienteRepository
from app.modules.pedidos.repository import PedidoRepository, DetallePedidoRepository


class UnitOfWork:
    """
    Context manager que encapsula una transacción de BD.

    Atributos:
        usuarios:     UsuarioRepository
        categorias:   CategoriaRepository
        productos:    ProductoRepository
        ingredientes: IngredienteRepository
    """

    def __init__(self):
        self.session: Session | None = None

    def __enter__(self):
        self.session = Session(engine)
        self.usuarios = UsuarioRepository(self.session)
        self.roles = RolRepository(self.session)
        self.usuarios_roles = UsuarioRolRepository(self.session)
        self.categorias = CategoriaRepository(self.session)
        self.productos = ProductoRepository(self.session)
        self.ingredientes = IngredienteRepository(self.session)
        self.pedidos = PedidoRepository(self.session)
        self.detalles_pedidos = DetallePedidoRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()

    def commit(self):
        """Commit explícito (para casos donde se necesita antes de salir del with)."""
        self.session.commit()

    def rollback(self):
        """Rollback explícito."""
        self.session.rollback()


def get_uow() -> UnitOfWork:
    """Dependencia FastAPI: provee un UnitOfWork por request."""
    return UnitOfWork()
