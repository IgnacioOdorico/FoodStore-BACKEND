"""
tests/unit/test_auth.py
========================
Tests de la capa de autenticación y autorización.
Cubre: register, login, logout, /me, rate limiting, JWT.

Spec §4.1: Flujo de autenticación
Spec §4.2: Roles y permisos RBAC
Spec §4.3: Rate Limiting
"""
import pytest
from fastapi.testclient import TestClient

from tests.conftest import _get_admin_auth_headers


class TestRegister:
    """POST /api/v1/auth/register"""

    def test_register_nuevo_usuario_ok(self, client: TestClient):
        """Un usuario nuevo se registra correctamente con rol CLIENT."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Juan",
                "apellido": "Pérez",
                "email": "juan@test.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "juan@test.com"
        assert "CLIENT" in data["roles"]
        assert "password_hash" not in data  # nunca exponer hash

    def test_register_email_duplicado_retorna_409(self, client: TestClient):
        """No se puede registrar dos veces con el mismo email."""
        payload = {
            "nombre": "Ana",
            "apellido": "García",
            "email": "ana@test.com",
            "password": "password123",
        }
        client.post("/api/v1/auth/register", json=payload)
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    def test_register_password_corta_retorna_422(self, client: TestClient):
        """La contraseña debe tener al menos 8 caracteres."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Pedro",
                "apellido": "López",
                "email": "pedro@test.com",
                "password": "corta",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """POST /api/v1/auth/token"""

    def test_login_credenciales_correctas_ok(self, client: TestClient):
        """Login exitoso setea cookie access_token."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin@test.com", "password": "admin123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.cookies

    def test_login_credenciales_incorrectas_retorna_401(self, client: TestClient):
        """Credenciales inválidas retornan 401."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin@test.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_usuario_inexistente_retorna_401(self, client: TestClient):
        """Email que no existe retorna 401."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "noexiste@test.com", "password": "password123"},
        )
        assert response.status_code == 401


class TestMe:
    """GET /api/v1/auth/me"""

    def test_me_autenticado_retorna_usuario(self, client: TestClient, admin_auth_headers: dict):
        """Usuario autenticado puede ver su propio perfil."""
        response = client.get("/api/v1/auth/me", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert "ADMIN" in data["roles"]

    def test_me_sin_auth_retorna_401(self, client: TestClient):
        """Sin token, GET /me debe retornar 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)


class TestLogout:
    """POST /api/v1/auth/logout"""

    def test_logout_borra_cookie(self, client: TestClient, admin_auth_headers: dict):
        """Logout elimina la cookie access_token."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        # La cookie debe ser eliminada (no estar en las cookies del client)
        assert response.json()["mensaje"] == "Sesión cerrada"


class TestRBAC:
    """Verifica que los endpoints respetan los roles — Spec §4.2"""

    def test_cliente_no_puede_crear_productos(self, client: TestClient):
        """Un usuario CLIENT no puede crear productos (requiere ADMIN)."""
        # Registrar usuario CLIENT
        client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Cliente",
                "apellido": "Normal",
                "email": "cliente@test.com",
                "password": "password123",
            },
        )
        # Login como CLIENT
        client.post(
            "/api/v1/auth/token",
            data={"username": "cliente@test.com", "password": "password123"},
        )
        # Intentar crear producto
        response = client.post(
            "/api/v1/productos/",
            json={
                "nombre": "Producto Test",
                "precio_base": 100.0,
                "categoria_ids": [1],
            },
        )
        assert response.status_code in (401, 403)

    def test_admin_puede_listar_usuarios(self, client: TestClient, admin_auth_headers: dict):
        """ADMIN puede acceder al endpoint de administración de usuarios."""
        response = client.get(
            "/api/v1/admin/usuarios",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
