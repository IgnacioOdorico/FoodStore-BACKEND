"""
tests/conftest.py
=================

Fixtures compartidos por toda la suite de tests de FoodStore.

Adaptaciones respecto a api_middlewares_testing:
  - El modelo de Usuario de FoodStore tiene (nombre, apellido, email,
    password_hash) en vez de (username, email, hashed_password, rol).
  - El login usa el endpoint /api/v1/auth/token con `username` = email.
  - Los modelos se crean directamente en la session de test (SQLite in-memory).
  - Se importan TODOS los modelos de FoodStore para que SQLModel.metadata
    los conozca antes de hacer create_all.
  - Como tenemos JWT en cookies + auth, agregamos fixtures para
    obtener headers de autenticación.
  - Como tenemos un RateLimitMiddleware en memoria, agregamos un
    fixture para resetearlo entre tests.
"""

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------
import os
import pytest

# FastAPI TestClient: simula requests HTTP sin abrir un socket TCP.
from fastapi.testclient import TestClient

# SQLModel/SQLAlchemy para manejo de DB en tests.
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_session
from app.core.rate_limit.rate_limit_middleware import RateLimitMiddleware
from app.core.security import hash_password
from app.main import app as fastapi_app

# ⚠️ Importar TODOS los modelos ANTES de create_all para que
# SQLModel.metadata los registre. Si falta alguno, la tabla no se crea.
import app.modules.usuarios.model           # Usuario, Rol, UsuarioRol
import app.modules.direcciones.models       # DireccionEntrega
import app.modules.catalogos.models         # UnidadMedida, EstadoPedido, FormaPago
import app.modules.categorias.model         # Categoria
import app.modules.ingrediente.models       # Ingrediente
import app.modules.producto.associations    # ProductoCategoria, ProductoIngrediente
import app.modules.producto.models          # Producto
import app.modules.pedidos.models           # Pedido, DetallePedido, HistorialEstadoPedido

from app.modules.usuarios.model import Usuario, Rol, UsuarioRol


# ===========================================================================
# CONFIGURACIÓN DE ENTORNO PARA TESTS
# ===========================================================================
# Forzamos el environment "test" ANTES de cualquier import que lea settings.
os.environ.setdefault("ENVIRONMENT", "test")


# ===========================================================================
# 1. ENGINE DE TEST
# ===========================================================================
@pytest.fixture(name="engine_test", scope="session")
def engine_test_fixture():
    """
    Engine de SQLAlchemy para los tests.

    ¿Por qué SQLite en vez de PostgreSQL?
    --------------------------------------
    Para CI/CD rápido y para que cualquiera pueda correr los tests sin
    levantar un Postgres. StaticPool garantiza que todos los threads
    usen la misma conexión (requerido por SQLite in-memory).

    `scope="session"`: el engine se crea UNA vez por toda la ejecución
    de pytest, no por test. Mucho más rápido.
    """
    url = settings.TEST_DATABASE_URL
    connect_args = {}
    poolclass = StaticPool

    # SQLite necesita `check_same_thread=False` cuando se usa desde
    # múltiples threads (TestClient puede usar threads).
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(
        url,
        connect_args=connect_args,
        poolclass=poolclass,
        echo=False,  # True para ver SQL en consola (debug).
    )
    yield engine
    # Al final de TODA la suite, cerramos el engine.
    engine.dispose()


# ===========================================================================
# 2. SESSION DE BASE DE DATOS
# ===========================================================================
@pytest.fixture(name="session", scope="function")
def session_fixture(engine_test):
    """
    Session de DB para un test.

    `scope="function"`: nueva session por test. Antes del yield creamos
    las tablas; después las dropeamos. Esto garantiza aislamiento total.
    """
    # DDL: CREATE TABLE.
    SQLModel.metadata.create_all(engine_test)

    with Session(engine_test) as session:
        yield session  # ← el test corre acá.

    # DDL: DROP TABLE. Limpieza total.
    SQLModel.metadata.drop_all(engine_test)


# ===========================================================================
# 3. CLIENTE HTTP DE TEST
# ===========================================================================
@pytest.fixture(name="client", scope="function")
def client_fixture(session: Session):
    """
    TestClient de FastAPI con la DB de test inyectada.

    `dependency_overrides[get_session]` reemplaza la dependency de
    producción por una que devuelve NUESTRA session de test. El endpoint
    no se entera: cree que está usando la DB real.

    `with TestClient(fastapi_app) as client` activa el lifespan (startup/shutdown).
    """
    def get_session_override():
        return session

    fastapi_app.dependency_overrides[get_session] = get_session_override

    # Limpiamos el rate limiter para que un test no contamine al siguiente.
    _reset_rate_limit_state()

    # ⚠️ Como la session está overrideada, el lifespan no puede
    # insertar datos en la session de test. Creamos el admin DIRECTO.
    _create_test_admin(session)

    with TestClient(fastapi_app) as client:
        yield client

    # Restauramos el estado original de la app.
    fastapi_app.dependency_overrides.clear()


def _create_test_admin(session: Session) -> None:
    """
    Crea el usuario admin y el rol ADMIN en la session de TEST.

    FoodStore usa un modelo con nombre+apellido y password_hash.
    El campo de login es `email` (mapeado al campo `username` del
    OAuth2PasswordRequestForm en el service).
    """
    from sqlmodel import select

    # Crear rol ADMIN si no existe
    existing_rol = session.exec(
        select(Rol).where(Rol.codigo == "ADMIN")
    ).first()
    if not existing_rol:
        rol_admin = Rol(codigo="ADMIN", nombre="Administrador")
        session.add(rol_admin)
        session.flush()

    # Crear usuario admin si no existe
    existing_user = session.exec(
        select(Usuario).where(Usuario.email == "admin@test.com")
    ).first()
    if existing_user is None:
        admin = Usuario(
            nombre="Admin",
            apellido="Test",
            email="admin@test.com",
            password_hash=hash_password("admin123"),
        )
        session.add(admin)
        session.flush()

        # Asignar rol ADMIN
        session.add(UsuarioRol(
            usuario_id=admin.id,
            rol_codigo="ADMIN",
        ))

    session.commit()


def _reset_rate_limit_state() -> None:
    """
    Resetea el estado en memoria del RateLimitMiddleware.

    Como el limiter vive en el atributo de clase (compartido entre
    requests), un test que agote el bucket dejaría al siguiente test
    "sin budget". Reseteamos antes de cada test que use el client.

    Usa el classmethod `reset_all_limiters()` que expusimos en el
    middleware para que los tests no tengan que hackear internals.
    """
    try:
        RateLimitMiddleware.reset_all_limiters()
    except Exception:
        # Si falla el reset, no bloqueamos el test.
        pass


# ===========================================================================
# 4. HELPERS DE AUTENTICACIÓN
# ===========================================================================
def _get_admin_auth_headers(client: TestClient) -> dict:
    """
    Helper: hace login con el admin y devuelve headers con la cookie.

    El admin existe porque `client_fixture` lo crea en la session de test.
    FoodStore usa OAuth2PasswordRequestForm con `username` = email.
    El endpoint de login es /api/v1/auth/token.
    """
    response = client.post(
        "/api/v1/auth/token",
        data={  # ⚠️ form, no JSON.
            "username": "admin@test.com",
            "password": "admin123",
        },
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"No se pudo loguear al admin. Status: {response.status_code}, "
            f"Body: {response.text}"
        )
    # El JWT viaja en la cookie HttpOnly `access_token` (no en el body).
    cookie = response.cookies.get("access_token")
    if not cookie:
        raise RuntimeError(
            f"Login del admin OK pero sin cookie access_token. "
            f"Body: {response.text}"
        )
    return {"Cookie": f"access_token={cookie}"}


@pytest.fixture(name="admin_auth_headers")
def admin_auth_headers_fixture(client: TestClient) -> dict:
    """Headers de autenticación del admin (con cookie)."""
    return _get_admin_auth_headers(client)
