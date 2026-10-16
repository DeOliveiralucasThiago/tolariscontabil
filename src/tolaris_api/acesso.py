"""Tokens de uso único (redefinição de senha, convite) e limite de tentativas de login."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import TentativaLogin, TokenAcesso


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: datetime) -> datetime:
    """SQLite devolve datas sem fuso; o banco grava sempre em UTC."""
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def novo_token() -> tuple[str, str]:
    """(token para o link, hash para o banco)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def criar_token(
    db: Session,
    tipo: str,
    escritorio_id: int,
    email: str,
    validade: timedelta,
    usuario_id: int | None = None,
    nome: str | None = None,
    papel: str | None = None,
    criado_por_id: int | None = None,
) -> tuple[str, TokenAcesso]:
    token, h = novo_token()
    registro = TokenAcesso(
        tipo=tipo,
        token_hash=h,
        escritorio_id=escritorio_id,
        usuario_id=usuario_id,
        email=email,
        nome=nome,
        papel=papel,
        criado_por_id=criado_por_id,
        expira_em=agora() + validade,
    )
    db.add(registro)
    return token, registro


def token_valido(db: Session, tipo: str, token: str) -> TokenAcesso:
    registro = db.scalar(select(TokenAcesso).where(TokenAcesso.token_hash == hash_token(token), TokenAcesso.tipo == tipo))
    if registro is None or registro.usado_em is not None or _aware(registro.expira_em) < agora():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link inválido ou expirado. Peça um novo.")
    return registro


# --- Limite de tentativas ----------------------------------------------------------
def ip_cliente(request: Request) -> str:
    """IP de quem fez o pedido. Atrás do site (que repassa /api) ou de um proxy, o IP direto é o do proxy: com
    ``proxy_saltos`` = N, vale o N-ésimo IP contado do fim de X-Forwarded-For (o que o proxy confiável acrescentou);
    o que o cliente escreveu antes disso é ignorado. Com 0, o cabeçalho nunca é usado."""
    saltos = get_settings().proxy_saltos
    if saltos > 0:
        cadeia = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(cadeia) >= saltos:
            return cadeia[-saltos][:64]
    return (request.client.host if request.client else "desconhecido")[:64]


def verificar_limite_login(db: Session, email: str, ip: str) -> None:
    cfg = get_settings()
    desde = agora() - timedelta(minutes=cfg.login_janela_minutos)
    falhas = select(func.count()).select_from(TentativaLogin).where(
        TentativaLogin.sucesso.is_(False), TentativaLogin.criado_em >= desde
    )
    por_email = db.scalar(falhas.where(TentativaLogin.email == email)) or 0
    por_ip = db.scalar(falhas.where(TentativaLogin.ip == ip)) or 0
    if por_email >= cfg.login_max_falhas_email or por_ip >= cfg.login_max_falhas_ip:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Muitas tentativas de login. Aguarde {cfg.login_janela_minutos} minutos ou redefina a senha.",
            headers={"Retry-After": str(cfg.login_janela_minutos * 60)},
        )


def registrar_tentativa(db: Session, email: str, ip: str, sucesso: bool) -> None:
    db.add(TentativaLogin(email=email, ip=ip, sucesso=sucesso))
    if sucesso:
        # Login certo zera as falhas daquele e-mail
        db.execute(delete(TentativaLogin).where(TentativaLogin.email == email, TentativaLogin.sucesso.is_(False)))
    # Limpeza de registros antigos (mantém a tabela pequena)
    db.execute(delete(TentativaLogin).where(TentativaLogin.criado_em < agora() - timedelta(days=1)))
    db.commit()


def limite_envio_redefinicao(db: Session, email: str) -> bool:
    """No máximo 3 pedidos de redefinição por e-mail por hora (silencioso)."""
    desde = agora() - timedelta(hours=1)
    n = db.scalar(
        select(func.count()).select_from(TokenAcesso).where(
            TokenAcesso.tipo == "redefinir_senha", TokenAcesso.email == email, TokenAcesso.criado_em >= desde
        )
    )
    return (n or 0) < 3
