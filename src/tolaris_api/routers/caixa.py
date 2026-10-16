"""Link de envio de notas: o cliente (ou o sistema emissor dele) manda XML e ZIP sem login.

O escritório gera o link na aba Movimento fiscal do cliente. O token só aparece quando é gerado
(no banco fica o hash) e um link novo desativa o anterior.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..acesso import agora, hash_token, novo_token
from ..config import get_settings
from ..db import get_db
from ..emails import ErroEnvio, Mensagem, enviar, montar_html
from ..importacao import ler_arquivos
from ..importar import gravar_leitura, ler_uploads
from ..models import CaixaCliente, Cliente, Escritorio, Usuario
from ..schemas import CaixaEstado, CaixaGerarEntrada, CaixaLink, CaixaPublica, ImportacaoSaida
from ..seguranca import usuario_atual
from .clientes import obter_cliente

router = APIRouter(tags=["caixa de notas"])

ENVIOS_POR_HORA = 30
_envios_recentes: dict[int, deque[float]] = defaultdict(deque)
"""Por caixa, os instantes dos envios na última hora (em memória: vale por processo)."""


def _caixa(db: Session, cliente_id: int) -> CaixaCliente | None:
    return db.scalar(select(CaixaCliente).where(CaixaCliente.cliente_id == cliente_id))


# --- Lado do escritório -----------------------------------------------------------------------------
@router.get("/clientes/{cliente_id}/caixa", response_model=CaixaEstado)
def estado_caixa(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> CaixaEstado:
    caixa = _caixa(db, obter_cliente(db, usuario, cliente_id).id)
    if caixa is None or not caixa.ativo:
        return CaixaEstado(ativo=False)
    return CaixaEstado(
        ativo=True, criado_em=caixa.criado_em, ultimo_envio_em=caixa.ultimo_envio_em,
        total_envios=caixa.total_envios, total_notas=caixa.total_notas,
    )


@router.post("/clientes/{cliente_id}/caixa", response_model=CaixaLink, status_code=status.HTTP_201_CREATED)
def gerar_link_caixa(
    cliente_id: int, dados: CaixaGerarEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> CaixaLink:
    """Gera um link novo (o anterior deixa de funcionar). O link só é mostrado agora."""
    cliente = obter_cliente(db, usuario, cliente_id)
    if not cliente.cnpj:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cadastre o CNPJ do cliente antes de gerar o link de envio")
    token, h = novo_token()
    caixa = _caixa(db, cliente.id)
    if caixa is None:
        caixa = CaixaCliente(escritorio_id=usuario.escritorio_id, cliente_id=cliente.id, token_hash=h)
        db.add(caixa)
    caixa.token_hash, caixa.ativo, caixa.criado_em, caixa.criado_por_id = h, True, agora(), usuario.id
    db.commit()
    link = f"{get_settings().url_publica}/enviar/{token}"
    resultado = CaixaLink(link=link)
    if dados.enviar_para:
        escritorio = db.get(Escritorio, usuario.escritorio_id)
        mensagem = dados.mensagem or (
            f"Olá,\n\nO escritório {escritorio.nome} precisa das notas fiscais de {cliente.razao_social}. "
            "Use o botão abaixo para enviar os arquivos XML (pode ser um .zip com todos do mês). "
            "Não é preciso criar conta."
        )
        destinatarios = [str(e).lower() for e in dados.enviar_para]
        try:
            enviar(Mensagem(
                para=destinatarios,
                assunto=f"Envio das notas fiscais — {escritorio.nome}",
                texto=f"{mensagem}\n\nEnviar notas: {link}\n\n{usuario.nome} — {escritorio.nome}",
                html=montar_html("Envio das notas fiscais", [p.strip() for p in mensagem.split("\n") if p.strip()],
                                 cor=escritorio.cor_primaria, botao=("Enviar notas", link),
                                 rodape=f"{usuario.nome} — {escritorio.nome}"),
                nome_remetente=escritorio.nome,
                responder_para=escritorio.email or usuario.email,
            ))
            resultado.enviado_para = destinatarios
        except ErroEnvio:
            resultado.envio_erro = "O link foi gerado, mas o e-mail não pôde ser enviado. Copie e envie o link."
    return resultado


@router.delete("/clientes/{cliente_id}/caixa", status_code=status.HTTP_204_NO_CONTENT)
def desativar_caixa(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> None:
    caixa = _caixa(db, obter_cliente(db, usuario, cliente_id).id)
    if caixa:
        caixa.ativo = False
        db.commit()


# --- Lado do cliente (público, pelo link) -----------------------------------------------------------------
_NAO_ENCONTRADO = HTTPException(status.HTTP_404_NOT_FOUND, "Link inválido ou desativado")


def _caixa_publica(db: Session, token: str) -> tuple[CaixaCliente, Cliente, Escritorio]:
    caixa = db.scalar(select(CaixaCliente).where(CaixaCliente.token_hash == hash_token(token)))
    if caixa is None or not caixa.ativo:
        raise _NAO_ENCONTRADO
    cliente, escritorio = db.get(Cliente, caixa.cliente_id), db.get(Escritorio, caixa.escritorio_id)
    if cliente is None or escritorio is None or cliente.escritorio_id != escritorio.id or not cliente.cnpj:
        raise _NAO_ENCONTRADO
    return caixa, cliente, escritorio


@router.get("/caixa/{token}", response_model=CaixaPublica)
def ver_caixa(token: str, db: Session = Depends(get_db)) -> CaixaPublica:
    _, cliente, escritorio = _caixa_publica(db, token)
    return CaixaPublica(
        escritorio={
            "nome": escritorio.nome, "cor_primaria": escritorio.cor_primaria, "tem_logo": escritorio.logo_mime is not None,
            "email": escritorio.email, "telefone": escritorio.telefone,
        },
        cliente=cliente.razao_social,
        limite_mb=get_settings().importacao_max_mb,
    )


@router.get("/caixa/{token}/logo")
def logo_caixa(token: str, db: Session = Depends(get_db)) -> Response:
    _, _, escritorio = _caixa_publica(db, token)
    if escritorio.logo is None:
        raise _NAO_ENCONTRADO
    return Response(escritorio.logo, media_type=escritorio.logo_mime, headers={"Cache-Control": "private, max-age=300"})


def _limitar(caixa_id: int) -> None:
    agora_s, fila = time.monotonic(), _envios_recentes[caixa_id]
    while fila and agora_s - fila[0] > 3600:
        fila.popleft()
    if len(fila) >= ENVIOS_POR_HORA:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Muitos envios seguidos. Tente de novo em alguns minutos.",
            headers={"Retry-After": str(int(3600 - (agora_s - fila[0])) + 1)},
        )
    fila.append(agora_s)


@router.post("/caixa/{token}/arquivos", response_model=ImportacaoSaida, status_code=status.HTTP_201_CREATED)
async def receber_arquivos(token: str, arquivos: list[UploadFile], db: Session = Depends(get_db)) -> ImportacaoSaida:
    caixa, cliente, _ = _caixa_publica(db, token)
    _limitar(caixa.id)
    resultado = gravar_leitura(db, caixa.escritorio_id, cliente, ler_arquivos(await ler_uploads(arquivos), cliente.cnpj))
    caixa.ultimo_envio_em, caixa.total_envios = agora(), (caixa.total_envios or 0) + 1
    caixa.total_notas = (caixa.total_notas or 0) + resultado.importados
    db.commit()
    resultado.ignorados = resultado.ignorados[:20]
    return resultado
