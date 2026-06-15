"""
tests/unit/test_websocket.py
===========================
Tests del comportamiento de WebSockets para notificaciones en tiempo real.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from app.modules.catalogos.models import EstadoPedido, FormaPago
from app.modules.categorias.model import Categoria
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria


def _seed_catalogo_ws(session: Session) -> tuple[int, str]:
    """Seed mínimo para crear un pedido. Retorna (producto_id, forma_pago_codigo)."""
    from app.modules.usuarios.model import Rol, UsuarioRol, Usuario
    from app.core.security import hash_password

    for codigo, nombre in [("CLIENT", "Cliente"), ("PEDIDOS", "Gestor de Pedidos")]:
        if not session.exec(select(Rol).where(Rol.codigo == codigo)).first():
            session.add(Rol(codigo=codigo, nombre=nombre))

    estados = [
        ("PENDIENTE", False), ("CONFIRMADO", False), ("EN_PREP", False),
        ("ENTREGADO", True), ("CANCELADO", True),
    ]
    for i, (codigo, es_terminal) in enumerate(estados):
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == codigo)).first():
            session.add(EstadoPedido(codigo=codigo, descripcion=codigo, orden=i+1, es_terminal=es_terminal))

    if not session.exec(select(FormaPago).where(FormaPago.codigo == "EFECTIVO")).first():
        session.add(FormaPago(codigo="EFECTIVO", descripcion="Efectivo", habilitado=True))

    cat = session.exec(select(Categoria).where(Categoria.nombre == "WsTest")).first()
    if not cat:
        cat = Categoria(nombre="WsTest", descripcion="Cat ws test")
        session.add(cat)
        session.flush()

    prod = Producto(nombre="Producto WS", precio_base=100.0, stock_cantidad=10, disponible=True)
    session.add(prod)
    session.flush()
    session.add(ProductoCategoria(producto_id=prod.id, categoria_id=cat.id, es_principal=True))

    usuario = session.exec(select(Usuario).where(Usuario.email == "cliente_ws@test.com")).first()
    if not usuario:
        usuario = Usuario(
            nombre="Cliente", apellido="WS",
            email="cliente_ws@test.com",
            password_hash=hash_password("password123"),
        )
        session.add(usuario)
        session.flush()
        session.add(UsuarioRol(usuario_id=usuario.id, rol_codigo="CLIENT"))

    session.commit()
    return prod.id, "EFECTIVO"


def _login_cliente_ws(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "cliente_ws@test.com", "password": "password123"},
    )
    assert response.status_code == 200, f"Login falló: {response.text}"
    cookie = response.cookies.get("access_token")
    return {"Cookie": f"access_token={cookie}"}


class TestWebSocket:
    """Pruebas del endpoint WebSocket /api/v1/pedidos/ws"""

    def test_websocket_rechaza_sin_token(self, client: TestClient):
        """Si no hay cookie access_token, el WebSocket se cierra con 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/pedidos/ws") as websocket:
                websocket.receive_text()

        assert exc_info.value.code == 1008

    def test_websocket_acepta_con_token(self, client: TestClient, admin_auth_headers: dict, engine_test):
        """Si el usuario está autenticado, la conexión se mantiene abierta."""
        cookie_val = admin_auth_headers["Cookie"].split("=")[1]

        import app.modules.pedidos.router
        app.modules.pedidos.router.engine = engine_test

        with client.websocket_connect("/api/v1/pedidos/ws", cookies={"access_token": cookie_val}) as websocket:
            websocket.send_text('{"action": "ping"}')
            assert True  # conexión abierta sin excepción

    def test_websocket_subscribe_order(self, client: TestClient, admin_auth_headers: dict, engine_test):
        """Un admin puede suscribirse a una orden y recibir confirmación SUBSCRIBED."""
        cookie_val = admin_auth_headers["Cookie"].split("=")[1]

        import app.modules.pedidos.router
        app.modules.pedidos.router.engine = engine_test

        with client.websocket_connect("/api/v1/pedidos/ws", cookies={"access_token": cookie_val}) as websocket:
            websocket.send_json({"action": "subscribe-order", "order_id": 999})
            data = websocket.receive_json()
            assert data["event"] == "SUBSCRIBED"
            assert data["data"]["order_id"] == 999

    def test_avanzar_estado_emite_evento_ws(
        self, client: TestClient, session: Session, admin_auth_headers: dict, engine_test
    ):
        """
        Test de integración: crear pedido → suscribirse via WS → avanzar estado via REST
        → verificar que el evento PEDIDO_CONFIRMADO llega al socket suscrito.
        """
        import app.modules.pedidos.router
        import app.core.uow
        app.modules.pedidos.router.engine = engine_test
        app.core.uow.engine = engine_test

        prod_id, forma_pago = _seed_catalogo_ws(session)
        headers_cliente = _login_cliente_ws(client)

        # 1. Crear pedido como cliente
        res = client.post(
            "/api/v1/pedidos/",
            json={
                "detalles": [{"producto_id": prod_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago,
                "costo_envio": 0.0,
            },
            headers=headers_cliente,
        )
        assert res.status_code == 201, f"No se pudo crear el pedido: {res.text}"
        pedido_id = res.json()["id"]

        cookie_admin = admin_auth_headers["Cookie"].split("=")[1]

        # 2. Abrir conexión WS y suscribirse al pedido
        with client.websocket_connect(
            "/api/v1/pedidos/ws", cookies={"access_token": cookie_admin}
        ) as ws:
            # Suscribirse a la room del pedido creado
            ws.send_json({"action": "subscribe-order", "order_id": pedido_id})
            sub_ack = ws.receive_json()
            assert sub_ack["event"] == "SUBSCRIBED", f"No se recibió SUBSCRIBED: {sub_ack}"

            # 3. Avanzar estado via REST (PENDIENTE → CONFIRMADO)
            patch_res = client.patch(
                f"/api/v1/pedidos/{pedido_id}/estado",
                json={"estado_hacia": "CONFIRMADO"},
                headers=admin_auth_headers,
            )
            assert patch_res.status_code == 200, f"No se pudo avanzar estado: {patch_res.text}"

            # 4. Verificar que el evento WS llegó al suscriptor
            evento = ws.receive_json()
            assert evento["event"] == "PEDIDO_CONFIRMADO", (
                f"Se esperaba PEDIDO_CONFIRMADO, llegó: {evento['event']}"
            )
            assert evento["data"]["id"] == pedido_id
            assert evento["data"]["estado_codigo"] == "CONFIRMADO"
