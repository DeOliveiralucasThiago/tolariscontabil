"""Senhas (scrypt da biblioteca padrão), sessão por JWT em cookie httpOnly e usuário atual."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Usuario

# Parâmetros scrypt (OWASP): N=2^15, r=8, p=1
_N, _R, _P, _TAM = 2**15, 8, 1, 32
_MAXMEM = 128 * _N * _R * 2


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=_TAM, maxmem=_MAXMEM)
    b64 = base64.b64encode
    return f"scrypt${_N}${_R}${_P}${b64(sal).decode()}${b64(dk).decode()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        _, n, r, p, sal, dk = armazenado.split("$")
        esperado = base64.b64decode(dk)
        calculado = hashlib.scrypt(
            senha.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p),
            dklen=len(esperado), maxmem=_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculado, esperado)


def criar_token(usuario: Usuario) -> str:
    cfg = get_settings()
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "esc": usuario.escritorio_id,
        "iat": agora,
        "exp": agora + timedelta(hours=cfg.sessao_horas),
    }
    return jwt.encode(payload, cfg.secret_key, algorithm="HS256")


def definir_cookie(resposta: Response, token: str) -> None:
    cfg = get_settings()
    resposta.set_cookie(
        cfg.cookie_nome,
        token,
        max_age=cfg.sessao_horas * 3600,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="lax",
        path="/",
    )


def apagar_cookie(resposta: Response) -> None:
    resposta.delete_cookie(get_settings().cookie_nome, path="/")


_NAO_AUTENTICADO = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    cfg = get_settings()
    token = request.cookies.get(cfg.cookie_nome)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        raise _NAO_AUTENTICADO
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=["HS256"])
        usuario = db.get(Usuario, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _NAO_AUTENTICADO from None
    if usuario is None or not usuario.ativo or usuario.escritorio_id != payload.get("esc"):
        raise _NAO_AUTENTICADO
    return usuario
