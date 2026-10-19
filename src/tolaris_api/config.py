"""Configuração por variáveis de ambiente (prefixo TOLARIS_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
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
    proxy_saltos: int = 0
    """Quantos proxies confiáveis ficam na frente da API (o site Next conta como 1). 0 = ignora X-Forwarded-For."""
    importacao_max_mb: int = 25
    auditoria_retencao_meses: int = 24
    """Registros de atividade mais antigos que isso são apagados quando o administrador abre o registro."""

    imap_automatico: bool | None = None
    """Liga a verificação periódica das caixas de e-mail. Sem valor, liga só em produção."""
    imap_intervalo_minutos: int = 10
    imap_timeout_segundos: int = 30
    imap_dias_iniciais: int = 30
    """Na primeira verificação, só olha e-mails dos últimos N dias."""
    imap_permitir_rede_privada: bool = False
    """Aceita servidor IMAP em rede interna/localhost e portas diferentes de 993 (bloqueado por padrão, contra SSRF)."""

    @field_validator("database_url")
    @classmethod
    def _url_do_banco(cls, valor: str) -> str:
        """Aceita o endereço como os provedores (Neon, Render, Heroku) o entregam: ``postgres://`` ou ``postgresql://``."""
        valor = valor.strip()
        for prefixo in ("postgres://", "postgresql://"):
            if valor.startswith(prefixo):
                return "postgresql+psycopg://" + valor[len(prefixo):]
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
