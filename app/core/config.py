"""
Configuración centralizada leída desde variables de entorno.

Adopta el patrón de u_05_v2: variables individuales de PostgreSQL
con @computed_field para construir DATABASE_URL automáticamente.
Los valores sensibles (SECRET_KEY, POSTGRES_PASSWORD) viven en .env.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings
import cloudinary


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Base de datos
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_db: str = "parcial2"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # URL para tests (SQLite in-memory por defecto).
    # conftest.py puede sobreescribir el engine directamente, pero
    # esta variable la consume el fixture de engine de tests.
    TEST_DATABASE_URL: str = "sqlite:///:memory:"

    # @computed_field:
    # Decorador de Pydantic v2 que indica que este atributo calculado
    # debe incluirse en la serialización del modelo (model_dump / JSON),
    # aunque no sea un campo persistido.

    # @property:
    # Convierte el método en una propiedad de solo lectura.
    # Permite acceder como atributo (obj.algo) en lugar de método (obj.algo()).
    # El valor se calcula dinámicamente en cada acceso.

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """
        Construye la URL de conexión a PostgreSQL.
        Para tests se sobreescribe con SQLite en memoria desde conftest.py.
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # JWT
    SECRET_KEY: str
    ALGORITHM:  str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── MercadoPago ─────────────────────────────────────────────────────────
    MP_ACCESS_TOKEN: Optional[str] = None
    MP_PUBLIC_KEY: Optional[str] = None
    MP_WEBHOOK_URL: Optional[str] = None
    MP_WEBHOOK_SECRET: Optional[str] = None
    NGROK_URL: Optional[str] = None

    # Frontend / API (usadas para back_urls y redirects post-pago)
    VITE_API_URL: str = "http://localhost:8000"
    VITE_FRONTEND_URL: str = "http://localhost:5174"

    # ─── Cloudinary ──────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # ─── Debug / Entorno ─────────────────────────────────────────────────────
    # True: desarrollo (secure=False en cookies, etc.). False: producción.
    DEBUG: bool = True

    # ─── Logging ─────────────────────────────────────────────────────────────
    # Nivel de log. Literal evita typos (typo en el .env → falla validación).
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # ─── Rate Limiting ───────────────────────────────────────────────────────
    # Límite por defecto: peticiones por minuto por cliente identificado.
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60
    RATE_LIMIT_DEFAULT_BURST: int = 100
    # Límite estricto para endpoints de autenticación (mitiga fuerza bruta).
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_AUTH_BURST: int = 20

    # ─── CORS ────────────────────────────────────────────────────────────────
    # Orígenes permitidos para el frontend. Lista separada por comas en .env.
    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:3000"
    )

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """
        Convierte el string separado por comas del .env en una lista.

        .env → "http://a.com,http://b.com"  →  ["http://a.com", "http://b.com"]
        """
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Alias para `CORS_ALLOWED_ORIGINS` parseado (lista)."""
        v = self.CORS_ALLOWED_ORIGINS
        if isinstance(v, list):
            return v
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    # Aliases lowercase para uso en RateLimitMiddleware
    @computed_field  # type: ignore[prop-decorator]
    @property
    def rate_limit_default_burst(self) -> int:
        return self.RATE_LIMIT_DEFAULT_BURST

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rate_limit_default_per_minute(self) -> int:
        return self.RATE_LIMIT_DEFAULT_PER_MINUTE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rate_limit_auth_burst(self) -> int:
        return self.RATE_LIMIT_AUTH_BURST

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rate_limit_auth_per_minute(self) -> int:
        return self.RATE_LIMIT_AUTH_PER_MINUTE

    model_config = {
        "env_file": BASE_DIR / ".env",
        "env_file_encoding": "utf-8",
        "extra":             "ignore",
        "case_sensitive":    False,
    }


# Instancia global
settings = Settings()

# Inicializar Cloudinary
if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
