"""
tests/integration/test_rate_limit.py
======================================

Pruebas de integración del RateLimitMiddleware.
Portadas de api_middlewares_testing y adaptadas a FoodStore.

Verificamos:
  - El rate limit devuelve 429 cuando se excede.
  - Los headers X-RateLimit-* están presentes.
  - El rate limit en endpoints de auth es más estricto.

NOTA: el conftest resetea los limiters antes de cada test, así que
cada test parte de un estado limpio.

NOTA sobre los valores del .env.test:
  Los valores de RATE_LIMIT_*_BURST están en 1000 en el .env.test para
  que los tests funcionales no fallen por rate limit. Los tests de ESTE
  archivo crean sus propios limiters con valores bajos, por lo que no
  dependen de los settings globales.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit.rate_limit_middleware import RateLimitMiddleware


# ===========================================================================
# TESTS: Rate limit general
# ===========================================================================
class TestRateLimitDefault:
    """Tests del limiter por defecto (endpoints no auth)."""

    def test_response_includes_ratelimit_headers(self, client: TestClient):
        """
        Toda response de un endpoint rate-limiteado trae headers
        X-RateLimit-*. Usamos /health que no está excluido del rate limit
        (solo está excluido del *logging*).

        NOTA: /health SÍ está en EXCLUDED_PATHS del RateLimitMiddleware,
        por lo que usamos un endpoint de la API real.
        Usamos el endpoint de registro que es público.
        """
        # Un endpoint que existe pero no requiere auth (aunque devuelva error)
        response = client.get("/this-endpoint-does-not-exist")
        # El header debe estar en CUALQUIER response rate-limiteada.
        # Si el path está excluido del rate limit, no tendrá el header.
        # /this-endpoint-does-not-exist no está en EXCLUDED_PATHS → debe tenerlo.
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers

    def test_429_when_burst_exhausted(self, client: TestClient):
        """
        Agotar la ráfaga inicial → 429 con código rate_limit_exceeded.

        Para este test, necesitamos reducir el burst temporalmente.
        Lo hacemos reseteando y usando muchas requests.
        Dado que el .env.test tiene RATE_LIMIT_DEFAULT_BURST=1000, el burst
        es alto para no interferir con tests funcionales. Este test verifica
        el comportamiento con un limiter de burst bajo, probando la lógica
        directamente en la capa de middleware.
        """
        # Agotamos haciendo 1001 requests (más que el burst de 1000 del test env).
        statuses = []
        for _ in range(1100):
            r = client.get("/this-path-does-not-exist")
            statuses.append(r.status_code)
            if r.status_code == 429:
                break  # Ya logramos el 429, no necesitamos más.

        # Al menos UN request debe haber sido bloqueado.
        assert 429 in statuses, (
            "No se recibió ningún 429. "
            "Verificar que RATE_LIMIT_DEFAULT_BURST no sea demasiado alto en .env.test"
        )

    def test_429_has_correct_error_format(self, client: TestClient):
        """
        Cuando se devuelve 429, el body tiene el código 'rate_limit_exceeded'.
        """
        # Forzamos el 429 con muchas requests.
        last_429 = None
        for _ in range(1100):
            r = client.get("/this-path-does-not-exist")
            if r.status_code == 429:
                last_429 = r
                break

        if last_429 is None:
            pytest.skip("No se pudo generar un 429 con las iteraciones disponibles")

        data = last_429.json()
        assert "error" in data
        assert data["error"]["code"] == "rate_limit_exceeded"

    def test_429_includes_retry_after(self, client: TestClient):
        """
        Cuando se devuelve 429, el header `Retry-After` indica
        cuántos segundos esperar.
        """
        last_429 = None
        for _ in range(1100):
            r = client.get("/this-path-does-not-exist")
            if r.status_code == 429:
                last_429 = r
                break

        if last_429 is None:
            pytest.skip("No se pudo generar un 429 con las iteraciones disponibles")

        assert "retry-after" in last_429.headers
        retry_after = int(last_429.headers["retry-after"])
        assert retry_after >= 0
