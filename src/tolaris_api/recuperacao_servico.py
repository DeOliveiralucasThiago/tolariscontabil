"""Análise de imposto pago a mais (monofásico e ICMS-ST) a partir dos itens das notas importadas."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tolaris_motor import brl, recuperacao, tabelas

from .models import Cliente, DocumentoFiscal, ItemFiscal
from .servicos import _num, serializar_resultado

PRODUTOS_NA_TELA = 30
PRIMEIRO_MES_DA_TABELA = date(2009, 1, 1)
ROTULO_MONO = {"nota": "CST PIS 04 na nota", "ncm": "NCM da lista", "verificar": "NCM de lista parcial"}
ROTULO_ST = {"nota": "ST indicado na nota", "cest": "Tem CEST (conferir a UF)"}


def _reais(centavos: int | None) -> Decimal:
    return Decimal(centavos or 0) / 100


def _data_do_mes(competencia: str) -> date:
    return max(PRIMEIRO_MES_DA_TABELA, date(int(competencia[:4]), int(competencia[5:7]), 1))


def analisar(db: Session, cliente: Cliente, anexo: str | None = None) -> dict[str, Any]:
    """Resultado da análise (mesmo formato quando salvo como simulação ``recuperacao``)."""
    avisos: list[str] = []
    anexo_cliente = recuperacao.anexo_do_cliente(cliente.atividade)
    escolhido = anexo or anexo_cliente or "I"
    if anexo is None and anexo_cliente is None:
        avisos.append("A atividade do cliente não é comércio nem indústria; a análise usou o Anexo I. "
                      "Ajuste a atividade no cadastro ou escolha o anexo.")
    if cliente.regime_atual not in (None, "simples"):
        avisos.append("O cliente está cadastrado fora do Simples Nacional. Esta análise vale para quem recolhe pelo "
                      "DAS; em outros regimes, a revenda de produto monofásico tem PIS/Cofins com alíquota zero.")

    itens = db.execute(
        select(
            ItemFiscal.competencia, ItemFiscal.ncm, ItemFiscal.cfop, ItemFiscal.cst_icms, ItemFiscal.cst_pis,
            ItemFiscal.cest, func.max(ItemFiscal.descricao), func.sum(ItemFiscal.valor_centavos),
            func.sum(ItemFiscal.quantidade_itens),
        )
        .where(ItemFiscal.cliente_id == cliente.id, ItemFiscal.tipo == "saida")
        .group_by(ItemFiscal.competencia, ItemFiscal.ncm, ItemFiscal.cfop, ItemFiscal.cst_icms, ItemFiscal.cst_pis,
                  ItemFiscal.cest)
    ).all()
    receitas = dict(
        db.execute(
            select(DocumentoFiscal.competencia, func.sum(DocumentoFiscal.valor_centavos))
            .where(DocumentoFiscal.cliente_id == cliente.id, DocumentoFiscal.tipo == "saida")
            .group_by(DocumentoFiscal.competencia)
        ).all()
    )
    sem_itens = dict(
        db.execute(
            select(DocumentoFiscal.competencia, func.count())
            .where(DocumentoFiscal.cliente_id == cliente.id, DocumentoFiscal.tipo == "saida", ~DocumentoFiscal.itens.any())
            .group_by(DocumentoFiscal.competencia)
        ).all()
    )

    acumulado: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    produtos: dict[tuple, dict[str, Any]] = {}
    grupos = {g["id"]: g for g in tabelas.vigente("monofasico", date.today())["grupos"]}
    for comp, ncm, cfop, cst_icms, cst_pis, cest, descricao, valor, qtd in itens:
        c = recuperacao.classificar(recuperacao.Item(ncm, cfop, cst_icms, cst_pis, cest), _data_do_mes(comp))
        if c.mono is None and c.st is None:
            continue
        v = _reais(valor)
        if c.mono:
            acumulado[comp][f"mono_{c.mono}"] += v
        if c.st:
            acumulado[comp][f"st_{c.st}"] += v
        chave = (ncm, c.mono, c.st, c.grupo)
        p = produtos.setdefault(chave, {"ncm": ncm, "descricao": descricao, "mono": c.mono, "st": c.st, "grupo": c.grupo,
                                        "valor": Decimal(0), "itens": 0, "maior": Decimal(0)})
        p["valor"] += v
        p["itens"] += int(qtd or 0)
        if v > p["maior"]:
            p["maior"], p["descricao"] = v, descricao

    meses = [
        recuperacao.MesBase(
            comp, _reais(receitas.get(comp)),
            **{k: acumulado[comp].get(k, Decimal(0)) for k in ("mono_nota", "mono_ncm", "mono_verificar", "st_nota", "st_cest")},
        )
        for comp in sorted(receitas)
    ]
    r = recuperacao.estimar(meses, escolhido)

    docs_sem_itens = sum(sem_itens.values())
    if docs_sem_itens and itens:
        avisos.append(f"{docs_sem_itens} notas de venda foram importadas sem itens (versões antigas ou SPED sem C170). "
                      "Importe os XML de novo para completar a análise.")
    memoria = serializar_resultado(r.resultado, Decimal(0))
    alertas = list(dict.fromkeys(avisos + memoria["alertas"]))

    lista_produtos = []
    for p in sorted(produtos.values(), key=lambda x: x["valor"], reverse=True)[:PRODUTOS_NA_TELA]:
        g = grupos.get(p["grupo"]) if p["grupo"] else None
        lista_produtos.append({
            "ncm": p["ncm"],
            "descricao": p["descricao"],
            "grupo": g["nome"] if g else None,
            "base_legal": g["base_legal"] if g else None,
            "observacao": g["observacao"] if g else None,
            "monofasico": ROTULO_MONO.get(p["mono"]),
            "st": ROTULO_ST.get(p["st"]),
            "certeza": "provavel" if (p["mono"] in ("nota", "ncm") or p["st"] == "nota") else "verificar",
            "valor": _num(p["valor"]),
            "itens": p["itens"],
        })

    comps = [m.competencia for m in r.meses]
    total = r.provavel
    return {
        "disponivel": bool(itens),
        "anexo": escolhido,
        "anexo_origem": "escolhido" if anexo else ("atividade" if anexo_cliente else "padrao"),
        "periodo": {"inicio": comps[0] if comps else None, "fim": comps[-1] if comps else None, "meses": len(comps)},
        "documentos_sem_itens": docs_sem_itens,
        "meses": [
            {
                "competencia": m.competencia,
                "receita": _num(m.receita),
                "base_monofasico": _num(m.base_monofasico),
                "base_st": _num(m.base_st),
                "base_verificar": _num(m.base_verificar),
                "rbt12": _num(m.rbt12),
                "rbt12_estimado": m.rbt12_estimado,
                "faixa": m.faixa,
                "aliquota_efetiva": _num(m.aliquota_efetiva, 6),
                "pis_cofins": _num(m.pis_cofins),
                "icms": _num(m.icms),
                "provavel": _num(m.provavel),
                "a_verificar": _num(m.a_verificar),
                "calculado": m.calculado,
            }
            for m in r.meses
        ],
        "totais": {
            "pis_cofins": _num(r.pis_cofins),
            "icms": _num(r.icms),
            "provavel": _num(total),
            "a_verificar": _num(r.a_verificar),
            "base_monofasico": _num(sum((m.base_monofasico for m in r.meses if m.calculado), Decimal(0))),
            "base_st": _num(sum((m.base_st for m in r.meses if m.calculado), Decimal(0))),
        },
        "economia_anual": _num(r.economia_anual),
        "produtos": lista_produtos,
        "tributos": memoria["tributos"],
        "memoria": memoria["memoria"],
        "alertas": alertas,
        "melhor": (f"{brl(total)} pagos a mais no período" if total > 0 else "Sem indício de pagamento a mais"),
        "economia_vs_pior": _num(r.economia_anual),
    }
