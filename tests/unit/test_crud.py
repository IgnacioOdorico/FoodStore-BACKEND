"""
tests/unit/test_crud.py
=======================
Tests de integración para CRUD de categorías, ingredientes, direcciones y productos.
Cubre: creación, listado, obtención, actualización, soft-delete y autorización.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.modules.categorias.model import Categoria


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login_cliente(client: TestClient) -> None:
    """Registra y loguea un CLIENT, la cookie queda almacenada en el client."""
    client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Cliente",
            "apellido": "Test",
            "email": "cliente@test.com",
            "password": "password123",
        },
    )
    client.post(
        "/api/v1/auth/token",
        data={"username": "cliente@test.com", "password": "password123"},
    )


def _seed_categoria(session: Session) -> int:
    """Crea una categoría de prueba y retorna su ID."""
    cat = Categoria(nombre="Test Cat", descripcion="Categoría de prueba")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat.id


# ===========================================================================
# CATEGORÍAS
# ===========================================================================

class TestCategorias:
    """CRUD /api/v1/categorias"""

    def test_crear_categoria(self, client: TestClient, admin_auth_headers: dict):
        """ADMIN puede crear una categoría."""
        response = client.post(
            "/api/v1/categorias/",
            json={"nombre": "Bebidas", "descripcion": "Bebidas frías y calientes"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nombre"] == "Bebidas"
        assert data["descripcion"] == "Bebidas frías y calientes"
        assert "id" in data

    def test_listar_categorias(self, client: TestClient):
        """Público puede listar categorías."""
        response = client.get("/api/v1/categorias/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert "total" in data

    def test_get_categoria(self, client: TestClient, session: Session):
        """Público puede obtener una categoría por ID."""
        cat_id = _seed_categoria(session)
        response = client.get(f"/api/v1/categorias/{cat_id}")
        assert response.status_code == 200
        assert response.json()["id"] == cat_id

    def test_cliente_no_puede_crear_categoria(self, client: TestClient):
        """CLIENT no puede crear categorías (requiere ADMIN)."""
        _login_cliente(client)
        response = client.post(
            "/api/v1/categorias/",
            json={"nombre": "Bebidas"},
        )
        assert response.status_code in (401, 403)


# ===========================================================================
# INGREDIENTES
# ===========================================================================

class TestIngredientes:
    """CRUD /api/v1/ingredientes"""

    def test_crear_ingrediente(self, client: TestClient, admin_auth_headers: dict):
        """ADMIN puede crear un ingrediente."""
        response = client.post(
            "/api/v1/ingredientes/",
            json={
                "nombre": "Queso",
                "es_alergeno": True,
                "stock_cantidad": 100,
                "descripcion": "Queso mozzarella",
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Queso"
        assert data["es_alergeno"] is True
        assert data["stock_cantidad"] == 100
        assert "id" in data

    def test_listar_ingredientes(self, client: TestClient, admin_auth_headers: dict):
        """Usuario autenticado puede listar ingredientes."""
        response = client.get("/api/v1/ingredientes/", headers=admin_auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_ingrediente(self, client: TestClient, admin_auth_headers: dict):
        """Usuario autenticado puede obtener un ingrediente por ID."""
        res = client.post(
            "/api/v1/ingredientes/",
            json={"nombre": "Tomate", "stock_cantidad": 50},
            headers=admin_auth_headers,
        )
        ing_id = res.json()["id"]
        response = client.get(f"/api/v1/ingredientes/{ing_id}", headers=admin_auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == ing_id

    def test_crear_ingrediente_sin_auth_retorna_401(self, client: TestClient):
        """Sin autenticación no se puede crear un ingrediente."""
        response = client.post(
            "/api/v1/ingredientes/",
            json={"nombre": "Lechuga", "stock_cantidad": 30},
        )
        assert response.status_code in (401, 403)


# ===========================================================================
# DIRECCIONES
# ===========================================================================

class TestDirecciones:
    """CRUD /api/v1/direcciones"""

    def test_crear_direccion(self, client: TestClient):
        """CLIENT puede crear una dirección."""
        _login_cliente(client)
        response = client.post(
            "/api/v1/direcciones/",
            json={
                "linea1": "Av. Siempre Viva 123",
                "ciudad": "Springfield",
                "es_principal": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["linea1"] == "Av. Siempre Viva 123"
        assert data["ciudad"] == "Springfield"
        assert data["es_principal"] is True
        assert "id" in data

    def test_listar_mis_direcciones(self, client: TestClient):
        """CLIENT puede listar sus direcciones."""
        _login_cliente(client)
        response = client.get("/api/v1/direcciones/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_crear_direccion_sin_auth_retorna_401(self, client: TestClient):
        """Sin autenticación no se puede crear una dirección."""
        response = client.post(
            "/api/v1/direcciones/",
            json={"linea1": "Test 123", "ciudad": "Test City"},
        )
        assert response.status_code in (401, 403)

    def test_eliminar_direccion(self, client: TestClient):
        """CLIENT puede eliminar su propia dirección."""
        _login_cliente(client)
        res = client.post(
            "/api/v1/direcciones/",
            json={"linea1": "Calle Falsa 456", "ciudad": "Buenos Aires", "es_principal": True},
        )
        dir_id = res.json()["id"]
        response = client.delete(f"/api/v1/direcciones/{dir_id}")
        assert response.status_code == 204


# ===========================================================================
# PRODUCTOS
# ===========================================================================

class TestProductos:
    """CRUD /api/v1/productos"""

    def test_crear_producto(self, client: TestClient, admin_auth_headers: dict, session: Session):
        """ADMIN puede crear un producto (requiere categoría existente)."""
        cat_id = _seed_categoria(session)
        response = client.post(
            "/api/v1/productos/",
            json={
                "nombre": "Hamburguesa Clásica",
                "precio_base": 1500.00,
                "stock_cantidad": 50,
                "disponible": True,
                "categoria_ids": [cat_id],
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nombre"] == "Hamburguesa Clásica"
        assert data["precio_base"] == 1500.00
        assert "id" in data

    def test_listar_productos(self, client: TestClient):
        """Público puede listar productos (respuesta paginada)."""
        response = client.get("/api/v1/productos/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        assert isinstance(data["items"], list)

    def test_get_producto(self, client: TestClient, admin_auth_headers: dict, session: Session):
        """Público puede obtener un producto por ID."""
        cat_id = _seed_categoria(session)
        res = client.post(
            "/api/v1/productos/",
            json={
                "nombre": "Producto Test",
                "precio_base": 500.00,
                "stock_cantidad": 10,
                "categoria_ids": [cat_id],
            },
            headers=admin_auth_headers,
        )
        prod_id = res.json()["id"]
        response = client.get(f"/api/v1/productos/{prod_id}")
        assert response.status_code == 200
        assert response.json()["nombre"] == "Producto Test"

    def test_actualizar_producto(self, client: TestClient, admin_auth_headers: dict, session: Session):
        """ADMIN puede actualizar un producto."""
        cat_id = _seed_categoria(session)
        res = client.post(
            "/api/v1/productos/",
            json={
                "nombre": "Original",
                "precio_base": 1000.00,
                "stock_cantidad": 20,
                "categoria_ids": [cat_id],
            },
            headers=admin_auth_headers,
        )
        prod_id = res.json()["id"]
        response = client.patch(
            f"/api/v1/productos/{prod_id}",
            json={"nombre": "Actualizado", "precio_base": 1200.00},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Actualizado"
        assert data["precio_base"] == 1200.00

    def test_soft_delete_producto(self, client: TestClient, admin_auth_headers: dict, session: Session):
        """ADMIN puede soft-delete un producto."""
        cat_id = _seed_categoria(session)
        res = client.post(
            "/api/v1/productos/",
            json={
                "nombre": "Producto a eliminar",
                "precio_base": 500.00,
                "stock_cantidad": 10,
                "categoria_ids": [cat_id],
            },
            headers=admin_auth_headers,
        )
        prod_id = res.json()["id"]
        response = client.delete(f"/api/v1/productos/{prod_id}", headers=admin_auth_headers)
        assert response.status_code == 204

    def test_cliente_no_puede_crear_producto(self, client: TestClient):
        """CLIENT no puede crear productos (requiere ADMIN)."""
        _login_cliente(client)
        response = client.post(
            "/api/v1/productos/",
            json={
                "nombre": "Producto Cliente",
                "precio_base": 100.0,
                "categoria_ids": [1],
            },
        )
        assert response.status_code in (401, 403)
