"""Envio de relatórios por e-mail, publicação e portal do cliente (link público com token)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tolaris_motor import brl

from ..acesso import _aware, agora, hash_token, novo_token
from ..auditoria import auditar
from ..config import get_settings
from ..db import get_db
from ..emails import Anexo, ErroEnvio, Mensagem, enviar, enviar_sem_falhar, montar_html
from ..honorarios import FUSO, expirada, para_portal
from ..models import Cliente, Envio, Escritorio, PortalCliente, Simulacao, Usuario
from ..pdf import gerar_proposta, nome_arquivo, titulo_documento
from ..schemas import (
    AceiteEntrada,
    AceiteSaida,
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
    db.flush()
    auditar(db, escritorio.id, "relatorio_enviado", usuario, entidade="simulacao", entidade_id=sim.id,
            detalhe={"cliente_id": cliente.id, "status": envio.status, "destinatarios": len(destinatarios)})
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
    if dados.publicada and not sim.publicada:
        sim.publicada_em = agora()
    elif not dados.publicada:
        sim.publicada_em = None
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
    auditar(db, usuario.escritorio_id, "portal_link_gerado", usuario, entidade="cliente", entidade_id=cliente.id)
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
            PortalSimulacao(
                id=s.id, tipo=s.tipo, titulo=titulo_documento(s), resultado=s.resultado, criado_em=s.criado_em,
                honorarios=para_portal(s.honorarios) if s.honorarios else None,
                aceite_em=s.aceite_em, aceite_nome=s.aceite_nome,
            )
            for s in sims
        ],
    )


@router.get("/portal/{token}/logo")
def logo_portal(token: str, db: Session = Depends(get_db)) -> Response:
    _, _, escritorio = _portal_publico(db, token)
    if escritorio.logo is None:
        raise _NAO_ENCONTRADO
    return Response(escritorio.logo, media_type=escritorio.logo_mime, headers={"Cache-Control": "private, max-age=300"})


def _simulacao_publicada(db: Session, cliente: Cliente, simulacao_id: int) -> Simulacao:
    sim = db.get(Simulacao, simulacao_id)
    if sim is None or sim.cliente_id != cliente.id or not sim.publicada:
        raise _NAO_ENCONTRADO
    return sim


def _registrar_abertura(sim: Simulacao) -> None:
    """Confirmação de leitura: aberturas seguidas em menos de 10 minutos (recarregar a página) contam uma só."""
    momento = agora()
    ultima = _aware(sim.visto_ultima_em) if sim.visto_ultima_em else None
    if sim.visto_primeira_em is None:
        sim.visto_primeira_em = momento
    if ultima is None or momento - ultima >= timedelta(minutes=10):
        sim.aberturas = (sim.aberturas or 0) + 1
    sim.visto_ultima_em = momento


@router.get("/portal/{token}/simulacoes/{simulacao_id}.pdf")
def pdf_portal(token: str, simulacao_id: int, db: Session = Depends(get_db)) -> Response:
    _, cliente, escritorio = _portal_publico(db, token)
    sim = _simulacao_publicada(db, cliente, simulacao_id)
    _registrar_abertura(sim)
    db.commit()
    pdf = gerar_proposta(escritorio, cliente, sim)
    return Response(
        pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{nome_arquivo(sim)}"'}
    )


@router.post("/portal/{token}/simulacoes/{simulacao_id}/visto", status_code=status.HTTP_204_NO_CONTENT)
def marcar_visto(token: str, simulacao_id: int, db: Session = Depends(get_db)) -> None:
    """O portal avisa que o cliente abriu o relatório na tela."""
    _, cliente, _ = _portal_publico(db, token)
    _registrar_abertura(_simulacao_publicada(db, cliente, simulacao_id))
    db.commit()


@router.post("/portal/{token}/simulacoes/{simulacao_id}/aceite", response_model=AceiteSaida)
def aceitar_proposta(
    token: str, simulacao_id: int, dados: AceiteEntrada, requisicao: Request, db: Session = Depends(get_db)
) -> AceiteSaida:
    """Aceite eletrônico simples da proposta de honorários: guarda nome, data/hora e IP e avisa o escritório."""
    _, cliente, escritorio = _portal_publico(db, token)
    sim = _simulacao_publicada(db, cliente, simulacao_id)
    h = sim.honorarios
    if not h:
        raise _NAO_ENCONTRADO
    if sim.aceite_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta proposta já foi aceita")
    if expirada(h):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Esta proposta venceu em {h['valido_ate'][8:10]}/{h['valido_ate'][5:7]}/{h['valido_ate'][:4]}. "
            "Peça uma nova ao seu escritório.",
        )
    sim.aceite_em = agora()
    sim.aceite_nome = dados.nome
    sim.aceite_ip = requisicao.client.host[:45] if requisicao.client else None
    _registrar_abertura(sim)
    auditar(db, escritorio.id, "proposta_aceita", entidade="simulacao", entidade_id=sim.id,
            detalhe={"cliente_id": cliente.id})
    db.commit()

    criador = db.get(Usuario, sim.criado_por_id) if sim.criado_por_id else None
    destino = escritorio.email or (criador.email if criador else None)
    if destino:
        quando = sim.aceite_em.astimezone(FUSO).strftime("%d/%m/%Y às %H:%M")
        adesao = f" e adesão de {brl(h['adesao'])}" if h.get("adesao") else ""
        paragrafos = [
            f"{dados.nome} aceitou, pelo portal, a proposta de honorários de {brl(h['valor_mensal'])} por mês{adesao} "
            f"para {cliente.razao_social}.",
            f"Aceite registrado em {quando}. É um aceite eletrônico simples: formalize o contrato de prestação de "
            "serviços pelo procedimento do escritório.",
        ]
        enviar_sem_falhar(Mensagem(
            para=[destino],
            assunto=f"Proposta aceita — {cliente.razao_social}",
            texto="\n\n".join(paragrafos),
            html=montar_html("Proposta aceita", paragrafos, cor=escritorio.cor_primaria, rodape="Tolaris Contábil"),
            nome_remetente="Tolaris Contábil",
        ))
    return AceiteSaida(aceite_em=sim.aceite_em, aceite_nome=sim.aceite_nome)
