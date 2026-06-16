"""
tests/unit/test_pedidos.py
===========================
Tests de la lógica de pedidos: FSM, audit trail, reglas de negocio.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.modules.catalogos.models import EstadoPedido, FormaPago, UnidadMedida
from app.modules.categorias.model import Categoria
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria
from app.modules.pedidos.models import Pedido, HistorialEstadoPedido


def _seed_catalogo(session: Session) -> tuple[int, int]:
    """Crea datos mínimos para poder crear un pedido. Retorna (producto_id, forma_pago_codigo)."""
    from app.modules.usuarios.model import Rol, UsuarioRol
    from app.modules.usuarios.model import Usuario
    from app.core.security import hash_password

    # Roles básicos
    for codigo, nombre in [("CLIENT", "Cliente"), ("PEDIDOS", "Gestor de Pedidos")]:
        if not session.exec(select(Rol).where(Rol.codigo == codigo)).first():
            session.add(Rol(codigo=codigo, nombre=nombre))

    # Estados de pedido
    estados = [
        ("PENDIENTE", False), ("CONFIRMADO", False), ("EN_PREP", False),
        ("ENTREGADO", True), ("CANCELADO", True),
    ]
    for i, (codigo, es_terminal) in enumerate(estados):
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == codigo)).first():
            session.add(EstadoPedido(codigo=codigo, descripcion=codigo, orden=i+1, es_terminal=es_terminal))

    # Forma de pago
    if not session.exec(select(FormaPago).where(FormaPago.codigo == "MERCADOPAGO")).first():
        session.add(FormaPago(codigo="MERCADOPAGO", descripcion="MercadoPago", habilitado=True))
    if not session.exec(select(FormaPago).where(FormaPago.codigo == "EFECTIVO")).first():
        session.add(FormaPago(codigo="EFECTIVO", descripcion="Efectivo", habilitado=True))

    # Categoría
    cat = session.exec(select(Categoria).where(Categoria.nombre == "Test")).first()
    if not cat:
        cat = Categoria(nombre="Test", descripcion="Cat test")
        session.add(cat)
        session.flush()

    # Producto con stock
    prod = Producto(
        nombre="Producto Test",
        precio_base=100.0,
        stock_cantidad=10,
        disponible=True,
    )
    session.add(prod)
    session.flush()

    session.add(ProductoCategoria(producto_id=prod.id, categoria_id=cat.id, es_principal=True))

    # Usuario CLIENT
    usuario = session.exec(select(Usuario).where(Usuario.email == "cliente@test.com")).first()
    if not usuario:
        from app.core.security import hash_password
        usuario = Usuario(
            nombre="Cliente",
            apellido="Test",
            email="cliente@test.com",
            password_hash=hash_password("password123"),
        )
        session.add(usuario)
        session.flush()
        session.add(UsuarioRol(usuario_id=usuario.id, rol_codigo="CLIENT"))

    session.commit()
    return prod.id, "EFECTIVO"


def _login_cliente(client: TestClient) -> dict:
    """Login como cliente, retorna headers con cookie."""
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "cliente@test.com", "password": "password123"},
    )
    assert response.status_code == 200, f"Login falló: {response.text}"
    cookie = response.cookies.get("access_token")
    return {"Cookie": f"access_token={cookie}"}


class TestCrearPedido:
    """POST /api/v1/pedidos"""

    def test_crear_pedido_ok(self, client: TestClient, session: Session):
        """Un cliente puede crear un pedido con un item válido."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers = _login_cliente(client)

        response = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 50.0,
            },
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["estado_codigo"] == "PENDIENTE"
        assert data["total"] > 0

    def test_crear_pedido_primer_historial_estado_desde_null(
        self, client: TestClient, session: Session
    ):
        """El primer registro de historial siempre tiene estado_desde=NULL."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers = _login_cliente(client)

        response = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers,
        )
        assert response.status_code == 201
        pedido_id = response.json()["id"]

        historial = session.exec(
            select(HistorialEstadoPedido).where(HistorialEstadoPedido.pedido_id == pedido_id)
        ).all()
        assert len(historial) >= 1
        # El primer registro debe tener estado_desde=NULL
        primer = min(historial, key=lambda h: h.created_at)
        assert primer.estado_desde is None
        assert primer.estado_hacia == "PENDIENTE"

    def test_crear_pedido_producto_sin_stock_retorna_400(
        self, client: TestClient, session: Session
    ):
        """No se puede crear un pedido si el producto no tiene stock."""
        prod_id, forma_pago = _seed_catalogo(session)

        # Agotar el stock manualmente
        prod = session.get(Producto, prod_id)
        prod.stock_cantidad = 0
        session.add(prod)
        session.commit()

        headers = _login_cliente(client)
        response = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers,
        )
        assert response.status_code == 400


class TestAvanzarEstado:
    """PATCH /api/v1/pedidos/{id}/avanzar"""

    def test_avanzar_estado_ok(
        self, client: TestClient, session: Session, admin_auth_headers: dict
    ):
        """Admin puede avanzar el estado de un pedido (PENDIENTE → CONFIRMADO)."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers_cliente = _login_cliente(client)

        # Crear pedido
        res = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers_cliente,
        )
        assert res.status_code == 201
        pedido_id = res.json()["id"]

        # Avanzar a CONFIRMADO
        response = client.patch(
            f"/api/v1/pedidos/{pedido_id}/estado",
            json={"estado_hacia": "CONFIRMADO"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["estado_codigo"] == "CONFIRMADO"

    def test_avanzar_estado_invalido_retorna_409(
        self, client: TestClient, session: Session, admin_auth_headers: dict
    ):
        """Una transición inválida según la FSM retorna 409."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers_cliente = _login_cliente(client)

        res = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers_cliente,
        )
        pedido_id = res.json()["id"]

        # PENDIENTE → ENTREGADO no es válido según FSM
        response = client.patch(
            f"/api/v1/pedidos/{pedido_id}/estado",
            json={"estado_hacia": "ENTREGADO"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 409

    def test_cancelar_sin_motivo_retorna_400(
        self, client: TestClient, session: Session, admin_auth_headers: dict
    ):
        """Cancelar sin motivo retorna 400."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers_cliente = _login_cliente(client)

        res = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers_cliente,
        )
        pedido_id = res.json()["id"]

        response = client.patch(
            f"/api/v1/pedidos/{pedido_id}/estado",
            json={"estado_hacia": "CANCELADO", "motivo": None},
            headers=admin_auth_headers,
        )
        assert response.status_code in (400, 422)

    def test_cancelar_con_motivo_ok(
        self, client: TestClient, session: Session, admin_auth_headers: dict
    ):
        """Cancelar con motivo funciona correctamente."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers_cliente = _login_cliente(client)

        res = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers_cliente,
        )
        pedido_id = res.json()["id"]

        response = client.patch(
            f"/api/v1/pedidos/{pedido_id}/estado",
            json={"estado_hacia": "CANCELADO", "motivo": "El cliente cambió de opinión"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["estado_codigo"] == "CANCELADO"


class TestHistorial:
    """GET /api/v1/pedidos/{id}/historial"""

    def test_historial_retorna_lista_ordenada(
        self, client: TestClient, session: Session, admin_auth_headers: dict
    ):
        """El historial del pedido se retorna ordenado por created_at ASC."""
        prod_id, forma_pago = _seed_catalogo(session)
        headers_cliente = _login_cliente(client)

        res = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers_cliente,
        )
        pedido_id = res.json()["id"]

        # Avanzar estado para agregar entrada al historial
        client.patch(
            f"/api/v1/pedidos/{pedido_id}/estado",
            json={"estado_hacia": "CONFIRMADO"},
            headers=admin_auth_headers,
        )

        response = client.get(
            f"/api/v1/pedidos/{pedido_id}/historial",
            headers=headers_cliente,
        )
        assert response.status_code == 200
        historial = response.json()
        assert len(historial) >= 2  # PENDIENTE + CONFIRMADO
        # El primero debe tener estado_hacia=PENDIENTE
        assert historial[0]["estado_hacia"] == "PENDIENTE"
        assert historial[0]["estado_desde"] is None


class TestPaginacion:
    """Verifica la paginación en GET /api/v1/pedidos/admin/listado"""

    def test_listado_paginado_retorna_estructura_correcta(
        self, client: TestClient, admin_auth_headers: dict
    ):
        """El endpoint de listado paginado retorna {items, total, page, size, pages}."""
        response = client.get(
            "/api/v1/pedidos/admin/listado?page=1&size=5",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        assert data["page"] == 1
        assert data["size"] == 5
