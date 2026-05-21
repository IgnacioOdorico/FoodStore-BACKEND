from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import create_all_tables

from app.modules.usuarios.router import router as auth_router
from app.modules.catalogos.router import router as catalogos_router
from app.modules.direcciones.router import router as direcciones_router
from app.modules.categorias.router import router as categorias_router
from app.modules.producto.router import router as producto_router
from app.modules.ingrediente.router import router as ingrediente_router
from app.modules.pedidos.router import router as pedidos_router
from app.modules.pagos.router import router as pagos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_all_tables()
    except Exception:
        # En tests, la BD de producción no está disponible.
        # conftest.py crea las tablas con SQLite en memoria.
        pass
    yield


app = FastAPI(
    title="FoodStore API",
    version="2.0.0",
    description="FoodStore — Backend Parcial 2 (FastAPI + SQLModel) alineado al ERD v6.",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


app.include_router(auth_router)
app.include_router(catalogos_router)
app.include_router(direcciones_router)
app.include_router(categorias_router)
app.include_router(producto_router)
app.include_router(ingrediente_router)
app.include_router(pedidos_router)
app.include_router(pagos_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": "2.0.0"}
