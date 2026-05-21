"""
Entry point de la aplicación FastAPI.

Responsabilidades:
  - Registrar routers (auth + categorías + productos + ingredientes).
  - Configurar CORS para consumo desde frontend (React, etc.).
  - Crear tablas al arrancar (lifespan).
  - Health check en /health.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import create_all_tables
from app.modules.usuarios.router import router as auth_router
from app.modules.categorias.router import router as categorias_router
from app.modules.producto.router import router as producto_router
from app.modules.ingrediente.router import router as ingrediente_router
from app.modules.pedidos.router import router as pedidos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Crea las tablas de BD al arrancar la aplicación."""
    try:
        create_all_tables()
    except Exception:
        # En tests, la BD de producción no está disponible.
        # conftest.py crea las tablas con SQLite en memoria.
        pass
    yield


app = FastAPI(
    title="FoodStore API",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS MIDDLEWARE (DEBE SER EL ÚLTIMO AGREGADO PARA SER EL PRIMERO EN EJECUTARSE) ────
# En FastAPI, los middlewares se aplican en orden INVERSO (LIFO)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Vite frontend
        "http://localhost:3000",       # CRA frontend
        "http://127.0.0.1:5173",       # Vite (127.0.0.1)
        "http://127.0.0.1:3000",       # CRA (127.0.0.1)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(categorias_router)
app.include_router(producto_router)
app.include_router(ingrediente_router)
app.include_router(pedidos_router)


# ─── Health check ────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/test", tags=["test"])
def test():
    """Test endpoint - simple response"""
    return {"message": "Backend is working"}
