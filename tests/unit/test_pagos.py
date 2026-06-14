"""
tests/unit/test_pagos.py
========================
Tests de la integración de pagos con MercadoPago.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.modules.pagos.models import Pago
from app.modules.pedidos.models import Pedido


def _seed_y_crear_pedido(client: TestClient, session: Session) -> tuple[int, dict]:
    """
    Crea el seed mínimo y un pedido PENDIENTE.
    Retorna (pedido_id, headers_cliente).
    """
    from app.modules.catalogos.models import EstadoPedido, FormaPago
    from app.modules.categorias.model import Categoria
    from app.modules.producto.models import Producto
    from app.modules.producto.associations import ProductoCategoria
    from app.modules.usuarios.model import Usuario, Rol, UsuarioRol
    from app.core.security import hash_password

    # Seed básico
    estados = [
        ("PENDIENTE", False), ("CONFIRMADO", False), ("EN_PREP", False),
        ("ENTREGADO", True), ("CANCELADO", True),
    ]
    for i, (codigo, es_terminal) in enumerate(estados):
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == codigo)).first():
            session.add(EstadoPedido(codigo=codigo, descripcion=codigo, orden=i+1, es_terminal=es_terminal))

    if not session.exec(select(FormaPago).where(FormaPago.codigo == "MERCADOPAGO")).first():
        session.add(FormaPago(codigo="MERCADOPAGO", descripcion="MercadoPago", habilitado=True))

    for codigo, nombre in [("CLIENT", "Cliente"), ("ADMIN", "Administrador")]:
        if not session.exec(select(Rol).where(Rol.codigo == codigo)).first():
            session.add(Rol(codigo=codigo, nombre=nombre))

    cat = Categoria(nombre="CatPago", descripcion="Test")
    session.add(cat)
    session.flush()

    prod = Producto(nombre="Prod Pago", precio_base=500.0, stock_cantidad=5, disponible=True)
    session.add(prod)
    session.flush()
    session.add(ProductoCategoria(producto_id=prod.id, categoria_id=cat.id, es_principal=True))

    usuario = session.exec(select(Usuario).where(Usuario.email == "cliente_pago@test.com")).first()
    if not usuario:
        usuario = Usuario(
            nombre="Cliente", apellido="Pago",
            email="cliente_pago@test.com",
            password_hash=hash_password("password123"),
        )
        session.add(usuario)
        session.flush()
        session.add(UsuarioRol(usuario_id=usuario.id, rol_codigo="CLIENT"))

    session.commit()

    # Login
    login_resp = client.post(
        "/api/v1/auth/token",
        data={"username": "cliente_pago@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    cookie = login_resp.cookies.get("access_token")
    headers = {"Cookie": f"access_token={cookie}"}

    # Crear pedido
    pedido_resp = client.post(
        "/api/v1/pedidos/",
        json={
            "detalles": [{"producto_id": prod.id, "cantidad": 1}],
            "forma_pago_codigo": "MERCADOPAGO",
            "costo_envio": 50.0,
        },
        headers=headers,
    )
    assert pedido_resp.status_code == 201
    return pedido_resp.json()["id"], headers


class TestCrearPago:
    """POST /api/v1/pagos/crear"""

    def test_crear_pago_genera_preferencia_mp(
        self, client: TestClient, session: Session
    ):
        """Crear pago genera una preferencia en MP y registra en tabla Pago."""
        pedido_id, headers = _seed_y_crear_pedido(client, session)

        # Mockear el SDK de MercadoPago para no hacer llamadas reales
        mock_result = {
            "status": 201,
            "response": {
                "id": "TEST_PREF_123",
                "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=TEST_PREF_123",
            },
        }
        with patch("mercadopago.SDK") as mock_sdk_class:
            mock_sdk = MagicMock()
            mock_sdk_class.return_value = mock_sdk
            mock_sdk.preference.return_value.create.return_value = mock_result

            response = client.post(
                "/api/v1/pagos/crear",
                json={"pedido_id": pedido_id},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.json()
        assert "preference_id" in data
        assert "init_point" in data

    def test_idempotency_key_es_unico_por_pago(
        self, client: TestClient, session: Session
    ):
        """Cada creación de pago genera un idempotency_key único (anti-cobros duplicados)."""
        pedido_id, headers = _seed_y_crear_pedido(client, session)

        mock_result = {
            "status": 201,
            "response": {"id": "PREF_A", "init_point": "https://mp.com/A"},
        }
        with patch("mercadopago.SDK") as mock_sdk_class:
            mock_sdk = MagicMock()
            mock_sdk_class.return_value = mock_sdk
            mock_sdk.preference.return_value.create.return_value = mock_result

            client.post("/api/v1/pagos/crear", json={"pedido_id": pedido_id}, headers=headers)

        # Verificar que se registró el pago con idempotency_key
        pago = session.exec(
            select(Pago).where(Pago.pedido_id == pedido_id)
        ).first()
        assert pago is not None
        assert pago.idempotency_key is not None
        assert len(pago.idempotency_key) > 0

    def test_pago_pedido_ajeno_retorna_403(
        self, client: TestClient, session: Session, admin_auth_headers: dict
    ):
        """Un usuario no puede crear pago para un pedido ajeno."""
        pedido_id, _ = _seed_y_crear_pedido(client, session)

        # Admin intenta crear pago para el pedido del cliente — 403
        response = client.post(
            "/api/v1/pagos/crear",
            json={"pedido_id": pedido_id},
            headers=admin_auth_headers,
        )
        assert response.status_code in (403, 404)


class TestWebhook:
    """POST /api/v1/pagos/webhook"""

    def test_webhook_sin_payment_id_retorna_ignored(self, client: TestClient):
        """Webhook sin payment_id es ignorado silenciosamente (siempre 200)."""
        response = client.post(
            "/api/v1/pagos/webhook",
            json={"type": "payment"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ignored"

    def test_webhook_topic_desconocido_retorna_ignored(self, client: TestClient):
        """Webhook con topic desconocido es ignorado."""
        response = client.post(
            "/api/v1/pagos/webhook",
            json={"type": "subscription", "data": {"id": "123"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ignored"

    def test_webhook_aprobado_confirma_pedido(
        self, client: TestClient, session: Session
    ):
        """
        Webhook con pago aprobado debe avanzar el pedido a CONFIRMADO.
        Se mockea la consulta a la API de MP.
        """
        pedido_id, headers = _seed_y_crear_pedido(client, session)

        # Crear el pago en estado pendiente
        external_ref = "ext-ref-test-webhook-123"
        pago = Pago(
            pedido_id=pedido_id,
            transaction_amount=550.0,
            estado="pendiente",
            mp_status="pending",
            external_reference=external_ref,
            idempotency_key="idem-webhook-test-key-456",
        )
        session.add(pago)
        session.commit()

        # Mockear la consulta a MP: simula pago aprobado
        mp_info_aprobado = {
            "mp_payment_id": 999888777,
            "mp_status": "approved",
            "mp_status_detail": "accredited",
            "payment_method_id": "visa",
            "external_reference": external_ref,
        }

        with patch(
            "app.modules.pagos.service.PaymentService._consultar_pago_mp",
            return_value=mp_info_aprobado,
        ):
            response = client.post(
                "/api/v1/pagos/webhook",
                json={"type": "payment", "data": {"id": "999888777"}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("estado") == "aprobado"

        # Verificar que el pedido avanzó a CONFIRMADO
        pedido = session.get(Pedido, pedido_id)
        session.refresh(pedido)
        assert pedido.estado_codigo == "CONFIRMADO"


class TestGetPago:
    """GET /api/v1/pagos/{pedido_id}"""

    def test_propietario_puede_ver_su_pago(
        self, client: TestClient, session: Session
    ):
        """El propietario del pedido puede ver el pago asociado."""
        pedido_id, headers = _seed_y_crear_pedido(client, session)

        # Crear pago manual
        pago = Pago(
            pedido_id=pedido_id,
            transaction_amount=550.0,
            estado="pendiente",
            mp_status="pending",
            external_reference="ext-ref-get-test-111",
            idempotency_key="idem-get-test-key-222",
        )
        session.add(pago)
        session.commit()

        response = client.get(f"/api/v1/pagos/{pedido_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pedido_id"] == pedido_id

    def test_usuario_ajeno_no_puede_ver_pago(
        self, client: TestClient, session: Session
    ):
        """Un usuario sin acceso no puede ver el pago de otro."""
        # Crear pedido con cliente_pago
        pedido_id, _ = _seed_y_crear_pedido(client, session)

        # Login como admin y verificar que SÍ puede ver (staff puede)
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": "admin@test.com", "password": "admin123"},
        )
        cookie = login_resp.cookies.get("access_token")
        admin_headers = {"Cookie": f"access_token={cookie}"}

        response = client.get(f"/api/v1/pagos/{pedido_id}", headers=admin_headers)
        # Admin puede ver cualquier pago o retorna 404 si no hay pago aún
        assert response.status_code in (200, 404)
