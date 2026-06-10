"""
Configuración centralizada leída desde variables de entorno.

Adopta el patrón de u_05_v2: variables individuales de PostgreSQL
con @computed_field para construir DATABASE_URL automáticamente.
Los valores sensibles (SECRET_KEY, POSTGRES_PASSWORD) viven en .env.
"""

from pathlib import Path
from typing import Optional

from pydantic import computed_field
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Base de datos
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_db: str = "parcial2"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

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
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    MP_ACCESS_TOKEN: Optional[str] = None
    MP_PUBLIC_KEY: Optional[str] = None
    MP_WEBHOOK_URL: Optional[str] = None
    MP_WEBHOOK_SECRET: Optional[str] = None
    NGROK_URL: Optional[str] = None

    # Frontend / API (usadas para back_urls y redirects post-pago)
    VITE_API_URL: str = "http://localhost:8000"
    VITE_FRONTEND_URL: str = "http://localhost:5173"

    model_config = {
        "env_file": BASE_DIR / ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Instancia global
settings = Settings()
