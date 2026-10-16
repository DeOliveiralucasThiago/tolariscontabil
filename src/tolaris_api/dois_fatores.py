"""Regras da verificação em duas etapas: segredo cifrado, códigos do aplicativo e códigos de recuperação."""

from __future__ import annotations

import io

import segno
from fastapi import HTTPException, status

from . import totp
from .models import Usuario
from .segredos import SegredoIlegivel, cifrar, decifrar
from .seguranca import verificar_senha


def segredo_do_usuario(usuario: Usuario) -> str | None:
    if not usuario.totp_segredo_cifrado:
        return None
    try:
        return decifrar(usuario.totp_segredo_cifrado)
    except SegredoIlegivel:
        return None  # a chave do servidor mudou: o código nunca bate; o administrador redefine a verificação


def iniciar_configuracao(usuario: Usuario) -> tuple[str, str, str]:
    """Gera um segredo novo (ainda inativo). Devolve (segredo, uri, QR em SVG)."""
    segredo = totp.novo_segredo()
    usuario.totp_segredo_cifrado = cifrar(segredo)
    usuario.totp_ativo = False
    usuario.totp_ultimo_passo = None
    uri = totp.uri(segredo, usuario.email)
    saida = io.BytesIO()
    segno.make(uri, error="m").save(saida, kind="svg", xmldecl=False, svgns=True, nl=False, scale=5, border=2, dark="#1f3a5f")
    return segredo, uri, saida.getvalue().decode()


def confirmar_ativacao(usuario: Usuario, codigo: str) -> list[str] | None:
    """Ativa se o código bate com o segredo pendente. Devolve os códigos de recuperação (mostrados uma vez) ou None."""
    segredo = segredo_do_usuario(usuario)
    if segredo is None or usuario.totp_ativo:
        return None
    passo = totp.verificar(segredo, codigo)
    if passo is None:
        return None
    usuario.totp_ativo = True
    usuario.totp_ultimo_passo = passo
    return gerar_codigos(usuario)


def gerar_codigos(usuario: Usuario) -> list[str]:
    mostrar, hashes = totp.novos_codigos_recuperacao()
    usuario.codigos_recuperacao = hashes
    return mostrar


def aceitar_segundo_fator(usuario: Usuario, informado: str) -> str | None:
    """"aplicativo" ou "recuperacao" se o código vale (e já o consome), senão None."""
    segredo = segredo_do_usuario(usuario)
    if segredo is not None:
        passo = totp.verificar(segredo, informado, usuario.totp_ultimo_passo)
        if passo is not None:
            usuario.totp_ultimo_passo = passo
            return "aplicativo"
    restantes = totp.consumir_recuperacao(usuario.codigos_recuperacao, informado)
    if restantes is not None:
        usuario.codigos_recuperacao = restantes
        return "recuperacao"
    return None


def exigir_senha_e_codigo(usuario: Usuario, senha: str, codigo: str) -> str:
    """Operações sensíveis pedem a senha e um código válido. Devolve o método usado."""
    if not verificar_senha(senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha incorreta")
    metodo = aceitar_segundo_fator(usuario, codigo)
    if metodo is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido")
    return metodo


def limpar(usuario: Usuario) -> None:
    usuario.totp_ativo = False
    usuario.totp_segredo_cifrado = None
    usuario.totp_ultimo_passo = None
    usuario.codigos_recuperacao = None
    usuario.sessao_versao += 1
