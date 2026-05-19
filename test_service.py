# Test directo del servicio
import sys
from datetime import datetime, timezone

# Importar modelos
from app.modules.categorias.model import Categoria, CategoriaPublic
from app.modules.categorias.service import CategoriaService
from app.core.uow import UnitOfWork

# Test
try:
    with UnitOfWork() as uow:
        service = CategoriaService(uow)
        
        # Intentar listar categorías
        result = service.list_all()
        print(f"Service.list_all() successful: {len(result)} categorias")
        if result:
            print(f"  First: {result[0]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
