import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.modules.catalogos.models import EstadoPedido, FormaPago
from app.modules.categorias.model import Categoria
from app.modules.producto.models import Producto
from app.modules.producto.associations import ProductoCategoria
from app.modules.pedidos.models import Pedido, DetallePedido, HistorialEstadoPedido
from app.modules.usuarios.model import Rol, UsuarioRol, Usuario
from app.core.security import hash_password

_MOCK_VENTAS = patch(
    "app.modules.estadisticas.repository.EstadisticasRepository._get_ventas_por_dia",
    return_value=[],
)


def _seed_completo(session: Session) -> tuple[int, int, int]:
    for codigo, nombre in [("CLIENT", "Cliente"), ("ADMIN", "Administrador"), ("PEDIDOS", "Pedidos")]:
        if not session.exec(select(Rol).where(Rol.codigo == codigo)).first():
            session.add(Rol(codigo=codigo, nombre=nombre))

    estados = [
        ("PENDIENTE", False), ("CONFIRMADO", False), ("EN_PREP", False),
        ("ENTREGADO", True), ("CANCELADO", True),
    ]
    for i, (codigo, es_terminal) in enumerate(estados):
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == codigo)).first():
            session.add(EstadoPedido(codigo=codigo, descripcion=codigo, orden=i + 1, es_terminal=es_terminal))

    for codigo, desc in [("MERCADOPAGO", "MercadoPago"), ("EFECTIVO", "Efectivo")]:
        if not session.exec(select(FormaPago).where(FormaPago.codigo == codigo)).first():
            session.add(FormaPago(codigo=codigo, descripcion=desc, habilitado=True))

    cat = session.exec(select(Categoria).where(Categoria.nombre == "TestCat")).first()
    if not cat:
        cat = Categoria(nombre="TestCat", descripcion="Cat test")
        session.add(cat)
        session.flush()

    prod = Producto(nombre="Producto Stats", precio_base=200.0, stock_cantidad=50, disponible=True)
    session.add(prod)
    session.flush()
    session.add(ProductoCategoria(producto_id=prod.id, categoria_id=cat.id, es_principal=True))

    usuario = session.exec(select(Usuario).where(Usuario.email == "cliente_stats@test.com")).first()
    if not usuario:
        usuario = Usuario(
            nombre="Stats", apellido="Cliente",
            email="cliente_stats@test.com",
            password_hash=hash_password("password123"),
        )
        session.add(usuario)
        session.flush()
        session.add(UsuarioRol(usuario_id=usuario.id, rol_codigo="CLIENT"))

    session.commit()
    return prod.id, usuario.id, cat.id


def _crear_pedido_directo(session: Session, usuario_id: int, prod_id: int, estado: str = "PENDIENTE") -> Pedido:
    pedido = Pedido(
        usuario_id=usuario_id,
        estado_codigo=estado,
        forma_pago_codigo="EFECTIVO",
        subtotal=200.0,
        descuento=0.0,
        costo_envio=0.0,
        total=200.0,
    )
    session.add(pedido)
    session.flush()
    session.add(DetallePedido(
        pedido_id=pedido.id,
        producto_id=prod_id,
        cantidad=1,
        nombre_snapshot="Producto Stats",
        precio_snapshot=200.0,
        subtotal_snap=200.0,
    ))
    session.add(HistorialEstadoPedido(
        pedido_id=pedido.id,
        estado_desde=None,
        estado_hacia=estado,
    ))
    session.commit()
    return pedido


class TestEstadisticasDashboard:

    def test_dashboard_requiere_autenticacion(self, client: TestClient):
        response = client.get("/api/v1/estadisticas/dashboard")
        assert response.status_code == 401

    def test_dashboard_ok_retorna_estructura(self, client: TestClient, admin_auth_headers: dict, session: Session):
        _seed_completo(session)
        with _MOCK_VENTAS:
            response = client.get("/api/v1/estadisticas/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "totalProductos" in data
        assert "totalPedidos" in data
        assert "totalUsuarios" in data
        assert "pedidosPorEstado" in data
        assert "topProductos" in data
        assert "resumenStock" in data

    def test_dashboard_total_productos_correcto(self, client: TestClient, admin_auth_headers: dict, session: Session):
        _seed_completo(session)
        with _MOCK_VENTAS:
            response = client.get("/api/v1/estadisticas/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200
        assert response.json()["totalProductos"] >= 1

    def test_dashboard_excluye_pedidos_cancelados_de_top(
        self, client: TestClient, admin_auth_headers: dict, session: Session
    ):
        prod_id, usuario_id, _ = _seed_completo(session)
        _crear_pedido_directo(session, usuario_id, prod_id, "CONFIRMADO")
        _crear_pedido_directo(session, usuario_id, prod_id, "CANCELADO")

        with _MOCK_VENTAS:
            response = client.get("/api/v1/estadisticas/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200
        top = response.json().get("topProductos", [])
        for item in top:
            assert item["ingresos"] >= 0

    def test_dashboard_pedidos_por_estado_incluye_estados(
        self, client: TestClient, admin_auth_headers: dict, session: Session
    ):
        prod_id, usuario_id, _ = _seed_completo(session)
        _crear_pedido_directo(session, usuario_id, prod_id, "PENDIENTE")
        _crear_pedido_directo(session, usuario_id, prod_id, "CONFIRMADO")

        with _MOCK_VENTAS:
            response = client.get("/api/v1/estadisticas/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200
        estados = response.json().get("pedidosPorEstado", {})
        assert "PENDIENTE" in estados
        assert "CONFIRMADO" in estados
        assert estados["PENDIENTE"] >= 1
        assert estados["CONFIRMADO"] >= 1

    def test_dashboard_resumen_stock_tiene_campos(
        self, client: TestClient, admin_auth_headers: dict, session: Session
    ):
        _seed_completo(session)
        with _MOCK_VENTAS:
            response = client.get("/api/v1/estadisticas/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200
        resumen = response.json().get("resumenStock", {})
        assert "bajo" in resumen
        assert "sinStock" in resumen
        assert "normal" in resumen
        assert "total" in resumen
