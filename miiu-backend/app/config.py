"""Configuracao lida de variaveis de ambiente (arquivo .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    ADMIN_SENHA: str = "123456"
    UPLOAD_DIR: str = "uploads"
    UPLOAD_MAX_MB: int = 10
    GEOFENCE_RAIO_PADRAO: int = 100
    INFERENCIA_LIMIAR: float = 0.50


config = Config()
