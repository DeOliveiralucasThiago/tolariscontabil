"""Configuração da caixa de e-mail (IMAP) de onde o escritório recebe as notas dos clientes. Só administradores."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import caixa_email as servico
from ..auditoria import auditar
from ..config import get_settings
from ..db import get_db
from ..models import CaixaEmail, Usuario
from ..schemas import CaixaEmailEntrada, CaixaEmailSaida
from ..segredos import cifrar
from ..seguranca import somente_admin

router = APIRouter(prefix="/escritorio/caixa-email", tags=["caixa de e-mail"])


def _caixa(db: Session, usuario: Usuario) -> CaixaEmail | None:
    return db.scalar(select(CaixaEmail).where(CaixaEmail.escritorio_id == usuario.escritorio_id))


def _saida(c: CaixaEmail | None) -> CaixaEmailSaida:
    auto = servico.automatico_ligado()
    base = {"automatico": auto, "intervalo_minutos": get_settings().imap_intervalo_minutos if auto else 0}
    if c is None:
        return CaixaEmailSaida(configurada=False, **base)
    return CaixaEmailSaida(
        configurada=True, host=c.host, porta=c.porta, usuario=c.usuario, pasta=c.pasta, ativo=c.ativo,
        ultima_verificacao_em=c.ultima_verificacao_em, ultimo_resultado=c.ultimo_resultado, **base,
    )


@router.get("", response_model=CaixaEmailSaida)
def estado(usuario: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> CaixaEmailSaida:
    return _saida(_caixa(db, usuario))


@router.put("", response_model=CaixaEmailSaida)
def salvar(dados: CaixaEmailEntrada, usuario: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> CaixaEmailSaida:
    host = dados.host.strip().rstrip(".").lower()
    try:
        servico.validar_destino(host, dados.porta)
    except servico.ErroCaixa as erro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro)) from None
    caixa = _caixa(db, usuario)
    mudou_destino = caixa is None or (caixa.host, caixa.porta, caixa.usuario) != (host, dados.porta, dados.usuario.strip())
    if mudou_destino and not dados.senha:
        # Sem a senha de novo, a senha guardada seguiria para outro servidor/usuário.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe a senha da caixa de e-mail.")
    if caixa is None:
        caixa = CaixaEmail(escritorio_id=usuario.escritorio_id)
        db.add(caixa)
    if mudou_destino or caixa.pasta != dados.pasta:
        caixa.ultimo_uid = caixa.uid_validade = None  # outra caixa: recomeça da janela inicial
    caixa.host, caixa.porta, caixa.usuario = host, dados.porta, dados.usuario.strip()
    caixa.pasta, caixa.ativo = dados.pasta.strip(), dados.ativo
    if dados.senha:
        caixa.senha_cifrada = cifrar(dados.senha)
    auditar(db, usuario.escritorio_id, "caixa_email_configurada", usuario,
            detalhe={"host": host, "usuario": caixa.usuario, "senha_trocada": bool(dados.senha)})
    db.commit()
    return _saida(caixa)


@router.post("/verificar", response_model=CaixaEmailSaida)
def verificar_agora(usuario: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> CaixaEmailSaida:
    caixa = _caixa(db, usuario)
    if caixa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Configure a caixa de e-mail primeiro")
    servico.verificar(db, caixa)
    return _saida(caixa)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remover(usuario: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> None:
    caixa = _caixa(db, usuario)
    if caixa is not None:
        db.delete(caixa)
        auditar(db, usuario.escritorio_id, "caixa_email_removida", usuario)
        db.commit()
