"""Configuração da verificação em duas etapas (aplicativo autenticador) do próprio usuário."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .. import dois_fatores as servico
from ..auditoria import auditar
from ..db import get_db
from ..models import Usuario
from ..schemas import CodigoEntrada, CodigosRecuperacaoSaida, Configurar2faSaida, SenhaCodigoEntrada, SenhaEntrada
from ..seguranca import criar_token, definir_cookie, usuario_atual, verificar_senha

router = APIRouter(prefix="/auth/2fa", tags=["verificação em duas etapas"])


@router.post("/configurar", response_model=Configurar2faSaida)
def configurar(dados: SenhaEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> Configurar2faSaida:
    """Começa a configuração: gera o segredo e o QR. Só vale depois de confirmar um código em /ativar."""
    if usuario.totp_ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "A verificação em duas etapas já está ativa. Desative para configurar de novo.")
    if not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha incorreta")
    segredo, uri, qr = servico.iniciar_configuracao(usuario)
    db.commit()
    return Configurar2faSaida(segredo=segredo, uri=uri, qr_svg=qr)


@router.post("/ativar", response_model=CodigosRecuperacaoSaida)
def ativar(
    dados: CodigoEntrada, request: Request, resposta: Response, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> CodigosRecuperacaoSaida:
    codigos = servico.confirmar_ativacao(usuario, dados.codigo)
    if codigos is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido. Confira a hora do celular e tente o próximo código.")
    usuario.sessao_versao += 1  # as outras sessões abertas caem; esta continua
    auditar(db, usuario.escritorio_id, "2fa_ativado", usuario, request=request)
    db.commit()
    definir_cookie(resposta, criar_token(usuario))
    return CodigosRecuperacaoSaida(codigos_recuperacao=codigos)


@router.post("/desativar", status_code=status.HTTP_204_NO_CONTENT)
def desativar(
    dados: SenhaCodigoEntrada, request: Request, resposta: Response, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> None:
    if not usuario.totp_ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "A verificação em duas etapas não está ativa")
    metodo = servico.exigir_senha_e_codigo(usuario, dados.senha, dados.codigo)
    servico.limpar(usuario)
    auditar(db, usuario.escritorio_id, "2fa_desativado", usuario, detalhe={"segundo_fator": metodo}, request=request)
    db.commit()
    definir_cookie(resposta, criar_token(usuario))


@router.post("/novos-codigos", response_model=CodigosRecuperacaoSaida)
def novos_codigos(
    dados: SenhaCodigoEntrada, request: Request, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> CodigosRecuperacaoSaida:
    """Gera outro conjunto de códigos de recuperação; os antigos deixam de valer."""
    if not usuario.totp_ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "A verificação em duas etapas não está ativa")
    servico.exigir_senha_e_codigo(usuario, dados.senha, dados.codigo)
    codigos = servico.gerar_codigos(usuario)
    auditar(db, usuario.escritorio_id, "2fa_codigos_novos", usuario, request=request)
    db.commit()
    return CodigosRecuperacaoSaida(codigos_recuperacao=codigos)
