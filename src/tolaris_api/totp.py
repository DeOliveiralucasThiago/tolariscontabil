"""Códigos de uso único de aplicativo autenticador (TOTP, RFC 6238) e códigos de recuperação. Só biblioteca padrão."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

PASSO_SEGUNDOS = 30
DIGITOS = 6
JANELA = 1
"""Aceita o intervalo anterior e o seguinte (relógio do celular um pouco fora)."""
EMISSOR = "Tolaris Contábil"
QUANTIDADE_RECUPERACAO = 8


def novo_segredo() -> str:
    """160 bits em base32, o tamanho recomendado pela RFC 4226."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(segredo: str, contador: int) -> str:
    chave = base64.b32decode(segredo + "=" * (-len(segredo) % 8), casefold=True)
    h = hmac.new(chave, struct.pack(">Q", contador), hashlib.sha1).digest()
    desloc = h[-1] & 0x0F
    numero = (struct.unpack(">I", h[desloc:desloc + 4])[0] & 0x7FFFFFFF) % 10**DIGITOS
    return f"{numero:0{DIGITOS}d}"


def passo_atual(agora: float | None = None) -> int:
    return int((time.time() if agora is None else agora) // PASSO_SEGUNDOS)


def codigo(segredo: str, passo: int) -> str:
    return _hotp(segredo, passo)


def verificar(segredo: str, informado: str, ultimo_passo: int | None = None, agora: float | None = None) -> int | None:
    """Intervalo em que o código vale, ou None. Intervalos já usados (<= ``ultimo_passo``) são recusados."""
    texto = "".join(informado.split())
    if not (texto.isdigit() and len(texto) == DIGITOS):
        return None
    atual = passo_atual(agora)
    aceito = None
    for passo in range(atual - JANELA, atual + JANELA + 1):
        igual = hmac.compare_digest(_hotp(segredo, passo), texto)  # percorre todos: tempo não depende de qual acertou
        if igual and (ultimo_passo is None or passo > ultimo_passo):
            aceito = passo
    return aceito


def uri(segredo: str, conta: str, emissor: str = EMISSOR) -> str:
    return (
        f"otpauth://totp/{quote(emissor)}:{quote(conta)}?secret={segredo}&issuer={quote(emissor)}"
        f"&algorithm=SHA1&digits={DIGITOS}&period={PASSO_SEGUNDOS}"
    )


# --- Códigos de recuperação ----------------------------------------------------------------
_ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"  # sem 0/o, 1/l/i: fácil de copiar do papel


def _normalizar(codigo_: str) -> str:
    return "".join(c for c in codigo_.lower() if c.isalnum())


def _hash(codigo_: str) -> str:
    return hashlib.sha256(_normalizar(codigo_).encode()).hexdigest()


def novos_codigos_recuperacao() -> tuple[list[str], list[str]]:
    """(códigos para mostrar uma única vez, hashes para guardar)."""
    mostrar = []
    for _ in range(QUANTIDADE_RECUPERACAO):
        bruto = "".join(secrets.choice(_ALFABETO) for _ in range(10))
        mostrar.append(f"{bruto[:5]}-{bruto[5:]}")
    return mostrar, [_hash(c) for c in mostrar]


def consumir_recuperacao(hashes: list[str] | None, informado: str) -> list[str] | None:
    """Lista de hashes sem o código usado, ou None se ele não existe. Códigos de recuperação não têm só dígitos."""
    if len(_normalizar(informado)) != 10:
        return None
    alvo = _hash(informado)
    restantes = [h for h in (hashes or []) if not hmac.compare_digest(h, alvo)]
    return restantes if len(restantes) < len(hashes or []) else None
