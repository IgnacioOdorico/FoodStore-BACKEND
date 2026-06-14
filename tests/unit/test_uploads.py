import io
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


class TestUploadImagen:

    def test_upload_requiere_autenticacion(self, client: TestClient):
        data = {"file": ("test.jpg", io.BytesIO(b"fake_image_data"), "image/jpeg")}
        response = client.post("/api/v1/uploads/imagen", files=data)
        assert response.status_code == 401

    def test_upload_formato_no_soportado_retorna_400(self, client: TestClient, admin_auth_headers: dict):
        data = {"file": ("test.gif", io.BytesIO(b"GIF89a"), "image/gif")}
        response = client.post("/api/v1/uploads/imagen", files=data, headers=admin_auth_headers)
        assert response.status_code == 400

    def test_upload_archivo_muy_grande_retorna_400(self, client: TestClient, admin_auth_headers: dict):
        large_bytes = b"x" * (5 * 1024 * 1024 + 1)
        data = {"file": ("big.jpg", io.BytesIO(large_bytes), "image/jpeg")}
        response = client.post("/api/v1/uploads/imagen", files=data, headers=admin_auth_headers)
        assert response.status_code == 400

    def test_upload_imagen_ok_retorna_url(self, client: TestClient, admin_auth_headers: dict):
        mock_response = {
            "secure_url": "https://res.cloudinary.com/test/image/upload/test.jpg",
            "public_id": "foodstore/test",
            "width": 800,
            "height": 600,
            "format": "jpg",
            "resource_type": "image",
        }

        with patch(
            "app.modules.uploads.service.UploadService.upload_image",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            data = {"file": ("photo.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"x" * 100), "image/jpeg")}
            response = client.post("/api/v1/uploads/imagen", files=data, headers=admin_auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert "secure_url" in body
        assert "public_id" in body

    def test_upload_webp_es_formato_valido(self, client: TestClient, admin_auth_headers: dict):
        mock_response = {
            "secure_url": "https://res.cloudinary.com/test/image/upload/test.webp",
            "public_id": "foodstore/test_webp",
            "width": 400,
            "height": 400,
            "format": "webp",
            "resource_type": "image",
        }

        with patch(
            "app.modules.uploads.service.UploadService.upload_image",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            data = {"file": ("photo.webp", io.BytesIO(b"RIFF" + b"x" * 100), "image/webp")}
            response = client.post("/api/v1/uploads/imagen", files=data, headers=admin_auth_headers)

        assert response.status_code == 201


class TestDeleteImagen:

    def test_delete_requiere_autenticacion(self, client: TestClient):
        response = client.delete("/api/v1/uploads/imagen/foodstore/test")
        assert response.status_code == 401

    def test_delete_imagen_ok(self, client: TestClient, admin_auth_headers: dict):
        with patch(
            "app.modules.uploads.service.UploadService.delete_image",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.delete(
                "/api/v1/uploads/imagen/foodstore%2Ftest",
                headers=admin_auth_headers,
            )

        assert response.status_code == 204
