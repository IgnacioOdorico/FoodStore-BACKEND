"""Engine SQLModel y factory de sesión."""

from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)


def get_session():
    """Dependencia FastAPI: provee una sesión de BD por request."""
    with Session(engine) as session:
        yield session


def create_all_tables() -> None:
    """Crea las tablas registradas en SQLModel.metadata al arrancar la app."""
    import app.modules.usuarios.model     
    import app.modules.categorias.model   
    import app.modules.producto.models    
    import app.modules.ingrediente.models  
    import app.modules.pedidos.models  
    SQLModel.metadata.create_all(engine)
