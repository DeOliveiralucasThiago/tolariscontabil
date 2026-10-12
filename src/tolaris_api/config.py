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

    url_publica: str = "http://localhost:3000"
    """Endereço do site, usado nos links enviados por e-mail."""
    email_backend: str = "console"
    """console (só registra), arquivo (grava em email_pasta), smtp ou resend."""
    email_pasta: str = "./caixa-de-saida"
    email_remetente: str = "Tolaris Contábil <nao-responda@localhost>"
    smtp_host: str = "localhost"
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = ""
    smtp_tls: bool = True
    resend_api_key: str = ""

    token_redefinicao_minutos: int = 60
    convite_dias: int = 7
    login_max_falhas_email: int = 5
    login_max_falhas_ip: int = 30
    login_janela_minutos: int = 15
    importacao_max_mb: int = 25


@lru_cache
def get_settings() -> Settings:
    return Settings()
