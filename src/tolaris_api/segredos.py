"""Cifra de segredos guardados no banco (hoje, só a senha da caixa de e-mail).

A chave deriva de TOLARIS_SECRET_KEY: quem tem o banco mas não tem a chave não lê a senha. Trocar a chave
invalida as senhas guardadas (o escritório precisa digitá-las de novo), como já acontece com as sessões.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class SegredoIlegivel(Exception):
    pass


def _fernet() -> Fernet:
    bruto = hmac.new(get_settings().secret_key.encode(), b"tolaris/segredos/v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(bruto))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(cifrado: str) -> str:
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken:
        raise SegredoIlegivel("Não foi possível ler a senha guardada (a chave do servidor mudou?). Digite a senha de novo.") from None
