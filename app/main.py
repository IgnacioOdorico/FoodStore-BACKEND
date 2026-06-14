"""
app/main.py — Punto de entrada de la aplicación FoodStore.

Acá se conectan TODAS las piezas:
  - Lifespan (startup/shutdown).
  - Logger (setup UNA vez al iniciar).
  - Middlewares (RateLimit, Logging, Timing, CORS).
  - Exception handlers (formato JSON unificado).
  - Routers de cada módulo.

Es el ÚNICO archivo donde se "ensambla" todo. Mantenerlo limpio facilita
entender la app de un vistazo.
"""

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Logger (portado de api_middlewares_testing)
from app.core.logger import get_logger, setup_logging

# Middlewares (portados de api_middlewares_testing)
from app.core.middleware.logging_middleware import LoggingMiddleware
from app.core.middleware.timing_middleware import TimingMiddleware
from app.core.rate_limit.rate_limit_middleware import RateLimitMiddleware

# Exception handlers (portados de api_middlewares_testing)
from app.core.exceptions.exception_handlers import register_exception_handlers

# Routers — todos los módulos de FoodStore
from app.modules.usuarios.router import router as auth_router, admin_router as admin_usuarios_router
from app.modules.catalogos.router import router as catalogos_router
from app.modules.direcciones.router import router as direcciones_router
from app.modules.categorias.router import router as categorias_router
from app.modules.producto.router import router as producto_router
from app.modules.ingrediente.router import router as ingrediente_router
from app.modules.pedidos.router import router as pedidos_router
from app.modules.pagos.router import router as pagos_router
from app.modules.uploads.router import router as uploads_router
from app.modules.estadisticas.router import router as estadisticas_router


# ---------------------------------------------------------------------------
# LOGGER (a nivel módulo)
# ---------------------------------------------------------------------------
# Configuramos el logger UNA vez al importar el módulo.
setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LIFESPAN: startup + shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager de vida de la app.

    - Startup: código que se ejecuta ANTES de que la app acepte requests.
      Acá creamos las tablas y logueamos el evento.
    - Shutdown: código que se ejecuta cuando la app se cierra (Ctrl+C,
      deploy nuevo, etc.). Logueamos el evento.

    ¿Por qué `asynccontextmanager` y no `@app.on_event`?
    ----------------------------------------------------
    `@app.on_event` está deprecado. El patrón moderno es un async context
    manager con `yield`. Lo que va ANTES del yield es startup; lo que va
    DESPUÉS es shutdown.
    """
    # ============== STARTUP ==============
    logger.info(
        "app.startup — FoodStore API v%s [env: production]",
        "2.0.0",
    )

    yield  # ← La app queda escuchando requests acá.

    # ============== SHUTDOWN ==============
    logger.info("app.shutdown")


# ---------------------------------------------------------------------------
# CREACIÓN DE LA APP
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FoodStore API",
    version="2.0.0",
    description="FoodStore — Backend (FastAPI + SQLModel).",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# MIDDLEWARES
# ---------------------------------------------------------------------------
# ⚠️ El ORDEN de los middlewares importa: se ejecutan en orden de
# declaración para la request, y en orden INVERSO para la response.

# 1) Rate limit: lo ponemos PRIMERO para cortar requests abusivas antes
#    de gastar trabajo en logging/auth/etc.
app.add_middleware(RateLimitMiddleware)

# 2) Logging: registramos cada request con su duración total. Va DESPUÉS
#    del rate limit (si rate limit cortó, el log lo refleja como 429).
app.add_middleware(LoggingMiddleware)

# 3) Timing: mide el tiempo de procesamiento interno. Es un middleware
#    "transparente" que solo agrega headers, no loguea.
app.add_middleware(TimingMiddleware)

# 4) CORS: maneja los headers de Cross-Origin. DEBE ir último para que
#    su respuesta (Access-Control-Allow-Origin) se agregue a TODAS las
#    responses, incluso las 4xx/5xx de los middlewares anteriores.
#    Se mantienen los mismos orígenes que tenía FoodStore originalmente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ---------------------------------------------------------------------------
# EXCEPTION HANDLERS (formato JSON unificado)
# ---------------------------------------------------------------------------
# Registra los 5 handlers definidos en `app/core/exceptions/exception_handlers.py`:
#   - app_error_handler (errores de dominio)
#   - http_exception_handler (HTTPException de FastAPI)
#   - validation_exception_handler (RequestValidationError de Pydantic)
#   - sqlalchemy_exception_handler (IntegrityError, etc.)
#   - unhandled_exception_handler (catch-all)
register_exception_handlers(app)


# ---------------------------------------------------------------------------
# ROUTERS — todos los módulos de FoodStore
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(admin_usuarios_router)
app.include_router(catalogos_router)
app.include_router(direcciones_router)
app.include_router(categorias_router)
app.include_router(producto_router)
app.include_router(ingrediente_router)
app.include_router(pedidos_router)
app.include_router(pagos_router)
app.include_router(uploads_router)
app.include_router(estadisticas_router)


# ---------------------------------------------------------------------------
# ENDPOINT RAÍZ: health check simple
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health():
    """Health check minimalista."""
    return {"status": "ok", "version": "2.0.0"}
