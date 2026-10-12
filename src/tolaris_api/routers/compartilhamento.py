"""Envio de relatórios por e-mail, publicação e portal do cliente (link público com token)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..acesso import agora, hash_token, novo_token
from ..config import get_settings
from ..db import get_db
from ..emails import Anexo, ErroEnvio, Mensagem, enviar, montar_html
from ..models import Cliente, Envio, Escritorio, PortalCliente, Simulacao, Usuario
from ..pdf import gerar_proposta, nome_arquivo, titulo_documento
from ..schemas import (
    EnviarEntrada,
    EnvioSaida,
    PortalEstado,
    PortalGerarEntrada,
    PortalLink,
    PortalPublico,
    PortalSimulacao,
    PublicarEntrada,
    SimulacaoSaida,
)
from ..seguranca import usuario_atual
from .clientes import obter_cliente
from .simulacoes import _obter_simulacao

router = APIRouter(tags=["envio e portal"])


def _paragrafos(texto: str) -> list[str]:
    return [p.strip() for p in texto.split("\n") if p.strip()]


# --- Envio por e-mail ------------------------------------------------------------------------
@router.post("/simulacoes/{simulacao_id}/enviar", response_model=EnvioSaida, status_code=status.HTTP_201_CREATED)
def enviar_relatorio(
    simulacao_id: int, dados: EnviarEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> Envio:
    sim = _obter_simulacao(db, usuario, simulacao_id)
    escritorio = db.get(Escritorio, usuario.escritorio_id)
    cliente = sim.cliente
    titulo = titulo_documento(sim)
    assunto = dados.assunto or f"{titulo} — {cliente.razao_social}"
    mensagem = dados.mensagem or (
        f"Olá,\n\nSegue em anexo o relatório \"{titulo}\" elaborado pelo escritório {escritorio.nome} "
        f"para {cliente.razao_social}.\n\nFicamos à disposição para conversar sobre os resultados."
    )
    assinatura = f"{usuario.nome} — {escritorio.nome}"
    destinatarios = [str(e).lower() for e in dados.para]
    envio = Envio(
        escritorio_id=escritorio.id,
        simulacao_id=sim.id,
        para=", ".join(destinatarios),
        assunto=assunto,
        status="enviado",
        enviado_por_id=usuario.id,
    )
    try:
        pdf = gerar_proposta(escritorio, cliente, sim, usuario)
        enviar(
            Mensagem(
                para=destinatarios,
                assunto=assunto,
                texto=f"{mensagem}\n\n{assinatura}",
                html=montar_html(titulo, _paragrafos(mensagem) + [assinatura], cor=escritorio.cor_primaria,
                                 rodape=f"Enviado por {escritorio.nome} com o Tolaris Contábil."),
                nome_remetente=escritorio.nome,
                responder_para=escritorio.email or usuario.email,
                anexos=[Anexo(nome_arquivo(sim), pdf)],
            )
        )
    except ErroEnvio as erro:
        envio.status, envio.erro = "falhou", str(erro)[:1000]
    db.add(envio)
    db.commit()
    if envio.status == "falhou":
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Não foi possível enviar o e-mail agora. Tente novamente.")
    return envio


@router.get("/simulacoes/{simulacao_id}/envios", response_model=list[EnvioSaida])
def listar_envios(simulacao_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> list[Envio]:
    return _obter_simulacao(db, usuario, simulacao_id).envios


# --- Publicação e portal -------------------------------------------------------------------------
@router.patch("/simulacoes/{simulacao_id}/publicacao", response_model=SimulacaoSaida)
def publicar(
    simulacao_id: int, dados: PublicarEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> Simulacao:
    sim = _obter_simulacao(db, usuario, simulacao_id)
    sim.publicada = dados.publicada
    db.commit()
    return sim


def _portal(db: Session, cliente_id: int) -> PortalCliente | None:
    return db.scalar(select(PortalCliente).where(PortalCliente.cliente_id == cliente_id))


def _publicadas(db: Session, cliente_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Simulacao).where(Simulacao.cliente_id == cliente_id, Simulacao.publicada.is_(True))
    ) or 0


@router.get("/clientes/{cliente_id}/portal", response_model=PortalEstado)
def estado_portal(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> PortalEstado:
    cliente = obter_cliente(db, usuario, cliente_id)
    portal = _portal(db, cliente.id)
    if portal is None or not portal.ativo:
        return PortalEstado(ativo=False, publicadas=_publicadas(db, cliente.id))
    return PortalEstado(
        ativo=True, criado_em=portal.criado_em, ultimo_acesso_em=portal.ultimo_acesso_em, publicadas=_publicadas(db, cliente.id)
    )


@router.post("/clientes/{cliente_id}/portal", response_model=PortalLink, status_code=status.HTTP_201_CREATED)
def gerar_link(
    cliente_id: int, dados: PortalGerarEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> PortalLink:
    """Gera um link novo (o anterior deixa de funcionar). O link só é mostrado agora."""
    cliente = obter_cliente(db, usuario, cliente_id)
    token, h = novo_token()
    portal = _portal(db, cliente.id)
    if portal is None:
        portal = PortalCliente(escritorio_id=usuario.escritorio_id, cliente_id=cliente.id, token_hash=h)
        db.add(portal)
    portal.token_hash, portal.ativo, portal.criado_em = h, True, agora()
    portal.criado_por_id, portal.ultimo_acesso_em = usuario.id, None
    db.commit()
    link = f"{get_settings().url_publica}/portal/{token}"
    resultado = PortalLink(link=link, enviado_para=[])
    if dados.enviar_para:
        escritorio = db.get(Escritorio, usuario.escritorio_id)
        mensagem = dados.mensagem or (
            f"Olá,\n\nO escritório {escritorio.nome} disponibilizou os relatórios de {cliente.razao_social} "
            "em um portal exclusivo. Use o botão abaixo para acessar quando quiser."
        )
        destinatarios = [str(e).lower() for e in dados.enviar_para]
        try:
            enviar(Mensagem(
                para=destinatarios,
                assunto=f"Seus relatórios — {escritorio.nome}",
                texto=f"{mensagem}\n\nAcesse: {link}\n\n{usuario.nome} — {escritorio.nome}",
                html=montar_html("Seus relatórios", _paragrafos(mensagem), cor=escritorio.cor_primaria,
                                 botao=("Abrir portal", link), rodape=f"{usuario.nome} — {escritorio.nome}"),
                nome_remetente=escritorio.nome,
                responder_para=escritorio.email or usuario.email,
            ))
            resultado.enviado_para = destinatarios
        except ErroEnvio:
            resultado.envio_erro = "O link foi gerado, mas o e-mail não pôde ser enviado. Copie e envie o link."
    return resultado


@router.delete("/clientes/{cliente_id}/portal", status_code=status.HTTP_204_NO_CONTENT)
def desativar_portal(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> None:
    portal = _portal(db, obter_cliente(db, usuario, cliente_id).id)
    if portal:
        portal.ativo = False
        db.commit()


# --- Acesso público pelo link -------------------------------------------------------------------------
_NAO_ENCONTRADO = HTTPException(status.HTTP_404_NOT_FOUND, "Link inválido ou desativado")


def _portal_publico(db: Session, token: str) -> tuple[PortalCliente, Cliente, Escritorio]:
    portal = db.scalar(select(PortalCliente).where(PortalCliente.token_hash == hash_token(token)))
    if portal is None or not portal.ativo:
        raise _NAO_ENCONTRADO
    cliente = db.get(Cliente, portal.cliente_id)
    escritorio = db.get(Escritorio, portal.escritorio_id)
    if cliente is None or escritorio is None or cliente.escritorio_id != escritorio.id:
        raise _NAO_ENCONTRADO
    return portal, cliente, escritorio


@router.get("/portal/{token}", response_model=PortalPublico)
def ver_portal(token: str, db: Session = Depends(get_db)) -> PortalPublico:
    portal, cliente, escritorio = _portal_publico(db, token)
    portal.ultimo_acesso_em = agora()
    db.commit()
    sims = db.scalars(
        select(Simulacao)
        .where(Simulacao.cliente_id == cliente.id, Simulacao.publicada.is_(True))
        .order_by(Simulacao.criado_em.desc())
    )
    return PortalPublico(
        escritorio={
            "nome": escritorio.nome,
            "cor_primaria": escritorio.cor_primaria,
            "tem_logo": escritorio.logo_mime is not None,
            "email": escritorio.email,
            "telefone": escritorio.telefone,
            "contador_responsavel": escritorio.contador_responsavel,
            "crc": escritorio.crc,
        },
        cliente=cliente.razao_social,
        simulacoes=[
            PortalSimulacao(id=s.id, tipo=s.tipo, titulo=titulo_documento(s), resultado=s.resultado, criado_em=s.criado_em)
            for s in sims
        ],
    )


@router.get("/portal/{token}/logo")
def logo_portal(token: str, db: Session = Depends(get_db)) -> Response:
    _, _, escritorio = _portal_publico(db, token)
    if escritorio.logo is None:
        raise _NAO_ENCONTRADO
    return Response(escritorio.logo, media_type=escritorio.logo_mime, headers={"Cache-Control": "private, max-age=300"})


@router.get("/portal/{token}/simulacoes/{simulacao_id}.pdf")
def pdf_portal(token: str, simulacao_id: int, db: Session = Depends(get_db)) -> Response:
    _, cliente, escritorio = _portal_publico(db, token)
    sim = db.get(Simulacao, simulacao_id)
    if sim is None or sim.cliente_id != cliente.id or not sim.publicada:
        raise _NAO_ENCONTRADO
    pdf = gerar_proposta(escritorio, cliente, sim)
    return Response(
        pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{nome_arquivo(sim)}"'}
    )
