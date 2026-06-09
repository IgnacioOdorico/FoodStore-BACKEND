"""
tests/integration/test_exception_handlers.py
=============================================

Pruebas de los exception handlers globales.
Portadas de api_middlewares_testing y adaptadas a FoodStore.

Verificamos que TODOS los errores de la API se devuelvan con el formato
JSON unificado:
    {
        "error": {
            "code": "...",
            "message": "...",
            "request_id": "...",
            "timestamp": "..."
        }
    }
"""

import pytest
from fastapi.testclient import TestClient


# ===========================================================================
# TESTS: Formato unificado
# ===========================================================================
class TestUnifiedErrorFormat:
    """El response de TODA excepción tiene la misma forma JSON."""

    def test_404_has_unified_format(self, client: TestClient):
        """
        Un GET a un endpoint inexistente devuelve 404 con nuestro
        formato (no el default de FastAPI {"detail": "..."}).
        """
        response = client.get("/this-path-does-not-exist")
        assert response.status_code == 404
        data = response.json()
        # El formato tiene la clave "error" envolviendo todo.
        assert "error" in data
        err = data["error"]
        assert "code" in err
        assert "message" in err
        assert "request_id" in err
        assert "timestamp" in err

    def test_422_validation_error_format(self, client: TestClient):
        """
        Body inválido → 422 con formato unificado.
        Pydantic detecta el error y nuestro handler lo formatea.
        FoodStore: /api/v1/auth/register espera campos específicos.
        """
        response = client.post(
            "/api/v1/auth/register",
            json={"nombre": 123},  # faltan apellido, email, password
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        err = data["error"]
        assert err["code"] == "validation_error"

    def test_401_unauthenticated(self, client: TestClient):
        """
        Un endpoint protegido sin token → 401 con formato unificado.
        """
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]

    def test_error_has_request_id_field(self, client: TestClient):
        """
        Todos los errores incluyen el campo request_id que permite
        correlacionar la respuesta con los logs del servidor.
        """
        response = client.get("/endpoint-que-no-existe")
        data = response.json()
        assert "error" in data
        assert "request_id" in data["error"]
        # request_id puede ser None (si el middleware no corrió) o un UUID.
        # En tests con TestClient corriendo los middlewares, debería ser un UUID.

    def test_error_has_timestamp_field(self, client: TestClient):
        """
        Todos los errores incluyen el campo timestamp en formato ISO 8601.
        """
        response = client.get("/endpoint-que-no-existe")
        data = response.json()
        assert "error" in data
        timestamp = data["error"].get("timestamp")
        assert timestamp is not None
        # Verificamos formato ISO 8601 básico.
        assert "T" in timestamp  # ej: "2024-01-15T10:30:00.000Z"
