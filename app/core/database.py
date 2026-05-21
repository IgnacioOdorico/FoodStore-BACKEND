"""
Engine SQLModel y factory de sesión.

Usa PostgreSQL configurado vía variables de entorno.
Los tests sobreescriben get_session con SQLite en memoria — sin tocar este módulo.
"""

from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)


def get_session():
    """Dependencia FastAPI: provee una sesión de BD por request."""
    with Session(engine) as session:
        yield session


def create_all_tables() -> None:
    """Crea las tablas registradas en SQLModel.metadata al arrancar la app."""
    import app.modules.usuarios.model           # Usuario, Rol, UsuarioRol, RefreshToken
    import app.modules.direcciones.models       # DireccionEntrega
    import app.modules.catalogos.models         # UnidadMedida, EstadoPedido, FormaPago
    import app.modules.categorias.model         # Categoria
    import app.modules.ingrediente.models       # Ingrediente
    import app.modules.producto.associations    # ProductoCategoria, ProductoIngrediente
    import app.modules.producto.models          # Producto
    import app.modules.pedidos.models           # Pedido, DetallePedido, HistorialEstadoPedido
    import app.modules.pagos.models             # Pago

    SQLModel.metadata.create_all(engine)
