"""Importação de NF-e (XML) e SPED Fiscal e o movimento mensal do cliente."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..importacao import ler_arquivos
from ..importar import gravar_leitura, ler_uploads
from ..models import DocumentoFiscal, ItemFiscal, Simulacao, Usuario
from ..recuperacao_servico import analisar
from ..schemas import (
    ImportacaoSaida,
    MesMovimento,
    MovimentoSaida,
    RecuperacaoEntrada,
    RecuperacaoPedido,
    SimulacaoSaida,
)
from ..seguranca import usuario_atual
from .clientes import obter_cliente
from .simulacoes import _salvar

router = APIRouter(tags=["importação fiscal"])


@router.post("/clientes/{cliente_id}/importacoes", response_model=ImportacaoSaida, status_code=status.HTTP_201_CREATED)
async def importar(
    cliente_id: int, arquivos: list[UploadFile], usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> ImportacaoSaida:
    cliente = obter_cliente(db, usuario, cliente_id)
    if not cliente.cnpj:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cadastre o CNPJ do cliente antes de importar documentos")
    leitura = ler_arquivos(await ler_uploads(arquivos), cliente.cnpj)
    return gravar_leitura(db, usuario.escritorio_id, cliente, leitura)


@router.get("/clientes/{cliente_id}/movimento", response_model=MovimentoSaida)
def movimento(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> MovimentoSaida:
    cliente = obter_cliente(db, usuario, cliente_id)
    linhas = db.execute(
        select(
            DocumentoFiscal.competencia,
            DocumentoFiscal.tipo,
            func.sum(DocumentoFiscal.valor_centavos),
            func.sum(DocumentoFiscal.icms_centavos),
            func.sum(DocumentoFiscal.ipi_centavos),
            func.sum(DocumentoFiscal.pis_centavos),
            func.sum(DocumentoFiscal.cofins_centavos),
            func.count(),
        )
        .where(DocumentoFiscal.cliente_id == cliente.id)
        .group_by(DocumentoFiscal.competencia, DocumentoFiscal.tipo)
    ).all()
    meses: dict[str, dict] = defaultdict(lambda: {"saidas": 0, "entradas": 0, "icms": 0, "ipi": 0, "pis": 0, "cofins": 0, "documentos": 0})
    for comp, tipo, valor, icms, ipi, pis, cofins, n in linhas:
        m = meses[comp]
        m["saidas" if tipo == "saida" else "entradas"] += valor or 0
        if tipo == "saida":  # tributos destacados nas vendas
            m["icms"] += icms or 0
            m["ipi"] += ipi or 0
            m["pis"] += pis or 0
            m["cofins"] += cofins or 0
        m["documentos"] += n
    ordenados = sorted(meses.items())
    ultimos = ordenados[-12:]
    reais = lambda c: round(c / 100, 2)  # noqa: E731
    return MovimentoSaida(
        meses=[MesMovimento(competencia=k, **{c: (reais(v) if c != "documentos" else v) for c, v in m.items()})
               for k, m in ordenados],
        receita_12m=reais(sum(m["saidas"] for _, m in ultimos)),
        compras_12m=reais(sum(m["entradas"] for _, m in ultimos)),
        meses_12m=len(ultimos),
        documentos=sum(m["documentos"] for m in meses.values()),
    )


@router.delete("/clientes/{cliente_id}/documentos", status_code=status.HTTP_204_NO_CONTENT)
def apagar_documentos(
    cliente_id: int,
    competencia: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> None:
    cliente = obter_cliente(db, usuario, cliente_id)
    for modelo in (ItemFiscal, DocumentoFiscal):  # itens primeiro: o delete em massa não aciona o cascade do ORM
        consulta = delete(modelo).where(modelo.cliente_id == cliente.id)
        if competencia:
            consulta = consulta.where(modelo.competencia == competencia)
        db.execute(consulta)
    db.commit()


# --- Imposto pago a mais (monofásico e ST) --------------------------------------------------------
@router.get("/clientes/{cliente_id}/recuperacao")
def recuperacao_previa(
    cliente_id: int,
    anexo: str | None = Query(default=None, pattern="^(I|II)$"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return analisar(db, obter_cliente(db, usuario, cliente_id), anexo)


@router.post("/clientes/{cliente_id}/recuperacao", response_model=SimulacaoSaida, status_code=status.HTTP_201_CREATED)
def recuperacao_salvar(
    cliente_id: int,
    pedido: RecuperacaoPedido,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> Simulacao:
    cliente = obter_cliente(db, usuario, cliente_id)
    resultado = analisar(db, cliente, pedido.anexo)
    if not resultado["disponivel"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Não há itens de notas de venda importados para este cliente. Importe os XML de NF-e na aba Movimento fiscal.",
        )
    entrada = RecuperacaoEntrada(
        anexo=resultado["anexo"], periodo_inicio=resultado["periodo"]["inicio"], periodo_fim=resultado["periodo"]["fim"]
    )
    sim = _salvar(db, usuario, cliente, "recuperacao", entrada, resultado)
    db.commit()
    return sim
