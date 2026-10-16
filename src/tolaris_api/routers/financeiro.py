"""Dados contábeis mensais do cliente trazidos de planilha (CSV/XLSX) exportada do sistema de contabilidade."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import planilha as pl
from ..auditoria import auditar
from ..db import get_db
from ..importar import ler_uploads
from ..models import FinanceiroMensal, Usuario
from ..schemas import (
    FinanceiroImportacaoSaida,
    FinanceiroMes,
    FinanceiroPlanejamento,
    FinanceiroPrevia,
    FinanceiroSaida,
)
from ..seguranca import usuario_atual
from .clientes import obter_cliente

router = APIRouter(tags=["dados contábeis"])


def _centavos_para_reais(v: int | None) -> float | None:
    return None if v is None else round(v / 100, 2)


def _mes(m: FinanceiroMensal) -> FinanceiroMes:
    return FinanceiroMes(
        competencia=m.competencia,
        **{c: _centavos_para_reais(getattr(m, f"{c}_centavos")) for c in pl.CAMPOS},
    )


def planejamento_de(meses: list[FinanceiroMensal]) -> FinanceiroPlanejamento | None:
    """Últimos 12 meses somados; com menos de 12, a média dos meses informados vezes 12 (marcado como anualizado)."""
    com_receita = [m for m in sorted(meses, key=lambda m: m.competencia) if m.receita_centavos]
    if not com_receita:
        return None
    ultimos = sorted(meses, key=lambda m: m.competencia)[-12:]
    n = len(ultimos)
    fator = 12 / n

    def anual(campo: str) -> float:
        soma = sum(getattr(m, f"{campo}_centavos") or 0 for m in ultimos)
        return round(soma * fator / 100, 2)

    return FinanceiroPlanejamento(
        meses=n,
        anualizado=n < 12,
        periodo_inicio=ultimos[0].competencia,
        periodo_fim=ultimos[-1].competencia,
        receita_bruta_anual=anual("receita"),
        compras_anual=anual("compras"),
        folha_clt_anual=anual("folha"),
        pro_labore_anual=anual("pro_labore"),
        despesas_creditaveis_anual=anual("despesas_creditaveis"),
        outras_despesas_anual=anual("outras_despesas"),
    )


def _estado(db: Session, cliente_id: int) -> FinanceiroSaida:
    meses = list(db.scalars(select(FinanceiroMensal).where(FinanceiroMensal.cliente_id == cliente_id).order_by(FinanceiroMensal.competencia)))
    return FinanceiroSaida(meses=[_mes(m) for m in meses], planejamento=planejamento_de(meses))


async def _tabela(arquivos: list[UploadFile]) -> tuple[list[str], list[list[str]]]:
    if len(arquivos) != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Envie uma planilha por vez")
    nome = arquivos[0].filename or ""
    (_, conteudo), = await ler_uploads(arquivos)
    try:
        return pl.ler_tabela(nome, conteudo)
    except pl.PlanilhaInvalida as erro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro)) from None


@router.get("/financeiro/modelo.csv")
def modelo(_: Usuario = Depends(usuario_atual)) -> Response:
    return Response(
        pl.modelo_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modelo-dados-contabeis.csv"'},
    )


@router.post("/clientes/{cliente_id}/financeiro/previa", response_model=FinanceiroPrevia)
async def previa(
    cliente_id: int, arquivos: list[UploadFile], usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> FinanceiroPrevia:
    obter_cliente(db, usuario, cliente_id)
    cabecalhos, linhas = await _tabela(arquivos)
    sugestao = pl.sugerir_mapeamento(cabecalhos)
    return FinanceiroPrevia(
        cabecalhos=cabecalhos, amostra=linhas[:5], total_linhas=len(linhas), sugestao=sugestao, rotulos=pl.ROTULOS
    )


@router.post(
    "/clientes/{cliente_id}/financeiro/importar", response_model=FinanceiroImportacaoSaida, status_code=status.HTTP_201_CREATED
)
async def importar(
    cliente_id: int,
    arquivos: list[UploadFile],
    mapeamento: str = Form(),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> FinanceiroImportacaoSaida:
    cliente = obter_cliente(db, usuario, cliente_id)
    cabecalhos, linhas = await _tabela(arquivos)
    try:
        bruto = json.loads(mapeamento)
        if not isinstance(bruto, dict):
            raise ValueError
        escolhido = pl.validar_mapeamento(bruto, len(cabecalhos))
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mapeamento de colunas inválido") from None
    except pl.PlanilhaInvalida as erro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro)) from None

    res = pl.converter(linhas, escolhido)
    if not res.meses:
        motivo = f" Primeiro problema: linha {res.ignoradas[0][0]}, {res.ignoradas[0][1]}." if res.ignoradas else ""
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nenhuma linha pôde ser importada." + motivo)

    existentes = {
        m.competencia: m
        for m in db.scalars(
            select(FinanceiroMensal).where(FinanceiroMensal.cliente_id == cliente.id, FinanceiroMensal.competencia.in_(res.meses))
        )
    }
    novos = atualizados = 0
    for comp, valores in res.meses.items():
        linha = existentes.get(comp)
        if linha is None:
            linha = FinanceiroMensal(escritorio_id=usuario.escritorio_id, cliente_id=cliente.id, competencia=comp)
            db.add(linha)
            novos += 1
        else:
            atualizados += 1
        for campo, valor in valores.items():
            if valor is not None:  # a planilha não informou: mantém o que já havia
                setattr(linha, f"{campo}_centavos", valor)
    auditar(db, usuario.escritorio_id, "financeiro_importado", usuario, entidade="cliente", entidade_id=cliente.id,
            detalhe={"meses_novos": novos, "meses_atualizados": atualizados})
    db.commit()
    return FinanceiroImportacaoSaida(
        meses_novos=novos,
        meses_atualizados=atualizados,
        competencias=sorted(res.meses),
        ignoradas=[{"linha": n, "motivo": motivo} for n, motivo in res.ignoradas[:20]],
        total_ignoradas=len(res.ignoradas),
        avisos=res.avisos,
    )


@router.get("/clientes/{cliente_id}/financeiro", response_model=FinanceiroSaida)
def listar(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> FinanceiroSaida:
    return _estado(db, obter_cliente(db, usuario, cliente_id).id)


@router.delete("/clientes/{cliente_id}/financeiro", status_code=status.HTTP_204_NO_CONTENT)
def apagar(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> None:
    cliente = obter_cliente(db, usuario, cliente_id)
    db.execute(delete(FinanceiroMensal).where(FinanceiroMensal.cliente_id == cliente.id))
    auditar(db, usuario.escritorio_id, "financeiro_apagado", usuario, entidade="cliente", entidade_id=cliente.id)
    db.commit()
