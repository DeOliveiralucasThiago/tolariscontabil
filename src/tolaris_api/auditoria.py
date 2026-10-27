"""Registro de atividades: ações sensíveis ficam gravadas com quem fez, quando e de que IP.

``auditar`` só adiciona o registro à sessão: quem chama faz o commit junto com a própria ação, então não existe
registro de algo que não aconteceu (nem ação sem registro).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .acesso import ip_cliente
from .models import RegistroAuditoria, Usuario

ip_da_requisicao: ContextVar[str | None] = ContextVar("ip_da_requisicao", default=None)
"""Preenchido pelo middleware: quem audita não precisa carregar o ``Request`` por todas as rotas."""

ROTULOS = {
    "login": "Entrou no sistema",
    "login_falha": "Tentativa de login recusada",
    "login_2fa_falha": "Código de verificação recusado",
    "codigo_recuperacao_usado": "Usou um código de recuperação",
    "senha_alterada": "Trocou a senha",
    "senha_redefinida": "Redefiniu a senha pelo e-mail",
    "2fa_ativado": "Ativou a verificação em duas etapas",
    "2fa_desativado": "Desativou a verificação em duas etapas",
    "2fa_codigos_novos": "Gerou novos códigos de recuperação",
    "2fa_resetado": "Verificação em duas etapas redefinida pelo administrador",
    "convite_criado": "Convidou um usuário",
    "convite_cancelado": "Cancelou um convite",
    "convite_aceito": "Aceitou um convite",
    "usuario_atualizado": "Alterou um usuário",
    "escritorio_atualizado": "Alterou os dados do escritório",
    "cliente_criado": "Cadastrou um cliente",
    "cliente_excluido": "Excluiu um cliente",
    "impedimentos_atualizados": "Atualizou a conferência dos impedimentos do Simples de um cliente",
    "cliente_exportado": "Exportou os dados de um cliente",
    "clientes_importados": "Importou clientes por planilha",
    "documentos_importados": "Importou documentos fiscais",
    "documentos_apagados": "Apagou documentos fiscais",
    "financeiro_importado": "Importou dados contábeis",
    "financeiro_apagado": "Apagou dados contábeis",
    "portal_link_gerado": "Gerou o link do portal do cliente",
    "caixa_link_gerado": "Gerou o link de envio de notas",
    "caixa_link_desativado": "Desativou o link de envio de notas",
    "caixa_envio": "Cliente enviou notas pelo link",
    "relatorio_enviado": "Enviou um relatório por e-mail",
    "proposta_aceita": "Cliente aceitou uma proposta",
    "caixa_email_configurada": "Configurou a caixa de e-mail de notas",
    "caixa_email_removida": "Removeu a caixa de e-mail de notas",
}


def auditar(
    db: Session,
    escritorio_id: int,
    acao: str,
    usuario: Usuario | None = None,
    *,
    entidade: str | None = None,
    entidade_id: int | None = None,
    detalhe: dict[str, Any] | None = None,
    request: Request | None = None,
    ip: str | None = None,
) -> None:
    if acao not in ROTULOS:
        raise ValueError(f"Ação de auditoria desconhecida: {acao}")
    db.add(RegistroAuditoria(
        escritorio_id=escritorio_id,
        usuario_id=usuario.id if usuario else None,
        usuario_nome=f"{usuario.nome} <{usuario.email}>"[:260] if usuario else None,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        detalhe=detalhe or None,
        ip=ip or (ip_cliente(request) if request is not None else ip_da_requisicao.get()),
    ))
