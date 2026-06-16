import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from sqlmodel import SQLModel
from app.core.config import settings

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.modules.usuarios.model import Usuario, Rol
from app.modules.categorias.model import Categoria
from app.modules.ingrediente.models import Ingrediente
from app.modules.catalogos.models import UnidadMedida, EstadoPedido, FormaPago
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria, ProductoIngrediente
from app.modules.pedidos.models import Pedido, DetallePedido, HistorialEstadoPedido
from app.modules.direcciones.models import DireccionEntrega
from app.modules.pagos.models import Pago

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
