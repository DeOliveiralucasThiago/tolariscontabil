"""Ponte entre a API e o motor: executa simulações e serializa os resultados."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import tolaris_motor
from tolaris_motor import Comparativo, PerfilEmpresa, Resultado, comparar, simulacao_expressa

from .schemas import CompletaEntrada, ExpressaEntrada

ROTULOS_ATIVIDADE = {
    "comercio": "Comércio",
    "industria": "Indústria",
    "servico_anexo_iii": "Serviços (Anexo III)",
    "servico_anexo_iv": "Serviços (Anexo IV)",
    "servico_fator_r": "Serviços sujeitos ao fator R",
}


def _num(v: Decimal, casas: int = 2) -> float:
    return float(round(v, casas))


def serializar_resultado(r: Resultado, receita: Decimal) -> dict[str, Any]:
    return {
        "titulo": r.titulo,
        "aplicavel": r.aplicavel,
        "total": _num(r.total),
        "carga_efetiva": _num(r.total / receita, 6) if receita and r.aplicavel else None,
        "tributos": [{"nome": n, "valor": _num(v)} for n, v in r.tributos.items()],
        "memoria": [
            {"descricao": p.descricao, "formula": p.formula, "valor": _num(p.valor, 6), "base_legal": p.base_legal}
            for p in r.memoria
        ],
        "alertas": list(r.alertas),
    }


def serializar_comparativo(c: Comparativo) -> dict[str, Any]:
    receita = c.perfil.receita_bruta_anual
    return {
        "receita_anual": _num(receita),
        "atividade": c.perfil.atividade.value,
        "ano": c.perfil.ano,
        "regimes": [serializar_resultado(r, receita) for r in c.resultados],
        "melhor": c.melhor.titulo,
        "ranking": [r.titulo for r in c.aplicaveis],
        "economia_vs_segundo": _num(c.economia_vs_segundo),
        "economia_vs_pior": _num(c.economia_vs_pior),
        "alertas": list(c.alertas),
    }


def executar_expressa(e: ExpressaEntrada) -> dict[str, Any]:
    c = simulacao_expressa(
        faturamento_mensal=e.faturamento_mensal,
        folha_mensal=e.folha_mensal,
        atividade=e.atividade,
        pro_labore_mensal=e.pro_labore_mensal,
        margem_lucro=e.margem_lucro,
        ano=e.ano,
    )
    return serializar_comparativo(c)


def executar_completa(e: CompletaEntrada) -> dict[str, Any]:
    perfil = PerfilEmpresa(**e.model_dump())
    return serializar_comparativo(comparar(perfil))


def titulo_simulacao(tipo: str, resultado: dict[str, Any]) -> str:
    nome = "Simulação expressa" if tipo == "expressa" else "Planejamento tributário"
    return f"{nome} {resultado['ano']} — melhor: {resultado['melhor']}"


VERSAO_MOTOR = tolaris_motor.__version__
