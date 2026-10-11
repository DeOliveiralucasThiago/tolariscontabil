"""Configuração por variáveis de ambiente (prefixo TOLARIS_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TOLARIS_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./tolaris.db"
    secret_key: str = "dev-somente-local-troque-esta-chave-em-producao"
    sessao_horas: int = 12
    cookie_secure: bool = False
    """True em produção (HTTPS)."""
    cookie_nome: str = "tolaris_sessao"
    brasilapi_url: str = "https://brasilapi.com.br/api/cnpj/v1"
    cnpj_timeout_segundos: float = 10.0
    logo_max_bytes: int = 512 * 1024
    ambiente: str = "desenvolvimento"


@lru_cache
def get_settings() -> Settings:
    return Settings()
