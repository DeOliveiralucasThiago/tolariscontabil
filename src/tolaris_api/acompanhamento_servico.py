"""Planejado × realizado e projeção de limites de um cliente.

O planejamento mais recente (simulação expressa ou completa) é comparado com o que já aconteceu: receita, compras,
folha e despesas dos últimos 12 meses, vindos das notas importadas e da planilha de dados contábeis. Com os números
reais, o comparativo de regimes é refeito para dizer se a recomendação ainda vale. A receita mensal também é
projetada para avisar com antecedência quando um limite de enquadramento será ultrapassado.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tolaris_motor import PerfilEmpresa, avisos, brl, pct
from tolaris_motor import projecao as pj

from .models import Cliente, DocumentoFiscal, FinanceiroMensal, Simulacao
from .servicos import recalcular_resultado

CAMPOS = ("receita", "compras", "folha", "pro_labore", "despesas_creditaveis", "outras_despesas")
ROTULOS = {
    "receita": "Receita",
    "compras": "Compras",
    "folha": "Folha de salários",
    "pro_labore": "Pró-labore",
    "despesas_creditaveis": "Despesas com crédito de PIS/Cofins",
    "outras_despesas": "Outras despesas",
}
CAMPO_DO_PERFIL = {
    "receita": "receita_bruta_anual",
    "compras": "compras_anual",
    "folha": "folha_clt_anual",
    "pro_labore": "pro_labore_anual",
    "despesas_creditaveis": "despesas_creditaveis_anual",
    "outras_despesas": "outras_despesas_anual",
}
MIN_MESES_COMPARACAO = 3
MIN_MESES_REAVALIACAO = 6
DESVIO_RELEVANTE = Decimal("0.20")

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
Series = dict[str, dict[str, Decimal]]
"""campo -> competência -> R$."""


def curta(comp: str) -> str:
    return f"{_MESES[int(comp[5:7]) - 1]}/{comp[2:4]}"


def perfil_da_simulacao(sim: Simulacao) -> PerfilEmpresa | None:
    """Perfil anual da empresa a partir de uma simulação expressa ou completa."""
    e = sim.entrada
    try:
        if sim.tipo == "completa":
            campos = {k: e[k] for k in PerfilEmpresa.__dataclass_fields__ if k in e}
            return PerfilEmpresa(**campos)
        if sim.tipo == "expressa":
            return PerfilEmpresa(
                atividade=e["atividade"],
                receita_bruta_anual=Decimal(str(e["faturamento_mensal"])) * 12,
                folha_clt_anual=Decimal(str(e["folha_mensal"])) * 12,
                pro_labore_anual=Decimal(str(e.get("pro_labore_mensal", 0))) * 12,
                ano=e.get("ano", 2026),
            )
    except (KeyError, ValueError, TypeError):
        return None
    return None


# --- Dados -----------------------------------------------------------------------------------
def montar_series(
    financeiro: list[FinanceiroMensal], saidas: dict[str, int], entradas: dict[str, int]
) -> Series:
    """Receita e compras vêm da planilha contábil quando ela traz o mês; senão, das notas. O resto, só da planilha."""
    series: Series = {c: {} for c in CAMPOS}
    for comp, centavos in saidas.items():
        series["receita"][comp] = Decimal(centavos) / 100
    for comp, centavos in entradas.items():
        series["compras"][comp] = Decimal(centavos) / 100
    for f in financeiro:
        for campo in CAMPOS:
            v = getattr(f, f"{campo}_centavos")
            if v is not None:
                series[campo][f.competencia] = Decimal(v) / 100
    return series


def carregar_series(
    db: Session, escritorio_id: int, cliente_id: int | None = None, com_planilha: set[int] | None = None
) -> dict[int, Series]:
    """Séries de um cliente (ou de todos do escritório) com poucas consultas. ``com_planilha`` recebe os clientes
    que têm dados contábeis importados."""
    filtro_doc = [DocumentoFiscal.escritorio_id == escritorio_id]
    filtro_fin = [FinanceiroMensal.escritorio_id == escritorio_id]
    if cliente_id is not None:
        filtro_doc.append(DocumentoFiscal.cliente_id == cliente_id)
        filtro_fin.append(FinanceiroMensal.cliente_id == cliente_id)
    saidas: dict[int, dict[str, int]] = defaultdict(dict)
    entradas: dict[int, dict[str, int]] = defaultdict(dict)
    for cid, comp, tipo, total in db.execute(
        select(DocumentoFiscal.cliente_id, DocumentoFiscal.competencia, DocumentoFiscal.tipo, func.sum(DocumentoFiscal.valor_centavos))
        .where(*filtro_doc)
        .group_by(DocumentoFiscal.cliente_id, DocumentoFiscal.competencia, DocumentoFiscal.tipo)
    ):
        (saidas if tipo == "saida" else entradas)[cid][comp] = total or 0
    fin: dict[int, list[FinanceiroMensal]] = defaultdict(list)
    for f in db.scalars(select(FinanceiroMensal).where(*filtro_fin)):
        fin[f.cliente_id].append(f)
    if com_planilha is not None:
        com_planilha.update(fin)
    ids = set(saidas) | set(entradas) | set(fin)
    return {cid: montar_series(fin.get(cid, []), saidas.get(cid, {}), entradas.get(cid, {})) for cid in ids}


def plano_do_cliente(db: Session, cliente_id: int) -> Simulacao | None:
    """Última simulação completa ou, na falta dela, a expressa mais recente."""
    for tipo in ("completa", "expressa"):
        sim = db.scalar(
            select(Simulacao).where(Simulacao.cliente_id == cliente_id, Simulacao.tipo == tipo).order_by(Simulacao.id.desc()).limit(1)
        )
        if sim is not None:
            return sim
    return None


# --- Análise ------------------------------------------------------------------------------------
def _r(v: Decimal | float | None) -> float | None:
    return None if v is None else float(round(Decimal(str(v)), 2))


def _janela(receita: dict[str, Decimal]) -> list[str]:
    ultimo = max(receita)
    return [c for c in (pj.proximo_mes(ultimo, -n) for n in range(11, -1, -1)) if c in receita]


def _entrada_real(base: Simulacao, realizado: dict[str, Decimal | None]) -> dict[str, Any]:
    e = dict(base.entrada)
    if base.tipo == "completa":
        for campo, v in realizado.items():
            if v is not None:
                e[CAMPO_DO_PERFIL[campo]] = float(round(v, 2))
        if realizado.get("folha") is not None or realizado.get("pro_labore") is not None:
            e["folha_fator_r_anual"] = None  # o valor informado no planejamento ficou velho
    else:  # expressa: mensal
        e["faturamento_mensal"] = float(round(realizado["receita"] / 12, 2))  # type: ignore[operator]
        if realizado.get("folha") is not None:
            e["folha_mensal"] = float(round(realizado["folha"] / 12, 2))  # type: ignore[operator]
        if realizado.get("pro_labore") is not None:
            e["pro_labore_mensal"] = float(round(realizado["pro_labore"] / 12, 2))  # type: ignore[operator]
    return e


def _totais(resultado: dict[str, Any]) -> dict[str, float]:
    return {r["titulo"]: r["total"] for r in resultado.get("regimes", []) if r.get("total") is not None}


def _reavaliar(base: Simulacao, realizado: dict[str, Decimal | None]) -> dict[str, Any] | None:
    try:
        planejado = recalcular_resultado(base.tipo, base.entrada)
        real = recalcular_resultado(base.tipo, _entrada_real(base, realizado))
    except Exception:  # noqa: BLE001 - números reais fora do que o motor aceita (ex.: receita acima do limite): sem reavaliação
        return None
    return {
        "melhor_planejado": planejado["melhor"],
        "melhor_realizado": real["melhor"],
        "mudou": planejado["melhor"] != real["melhor"],
        "economia_planejada": _r(planejado.get("economia_vs_pior")),
        "economia_realizada": _r(real.get("economia_vs_pior")),
        "totais_planejados": _totais(planejado),
        "totais_realizados": _totais(real),
    }


def _fator_r_real(base_perfil: PerfilEmpresa, realizado: dict[str, Decimal | None]) -> avisos.Aviso | None:
    if realizado.get("folha") is None and realizado.get("pro_labore") is None:
        return None
    mudancas = {CAMPO_DO_PERFIL[c]: v for c, v in realizado.items() if v is not None and c in ("receita", "folha", "pro_labore")}
    perfil = replace(base_perfil, folha_fator_r_anual=None, **mudancas)
    return avisos.avaliar_fator_r(perfil)


def _serie_grafico(receita: dict[str, Decimal], proj: pj.Projecao) -> list[dict[str, Any]]:
    """RBT12 realizado (onde os 12 meses da janela são conhecidos) seguido do RBT12 projetado."""
    pontos: list[dict[str, Any]] = []
    for comp in sorted(receita)[-12:]:
        janela = [pj.proximo_mes(comp, -n) for n in range(11, -1, -1)]
        if all(j in receita for j in janela):
            pontos.append({"competencia": comp, "rbt12": _r(sum((receita[j] for j in janela), Decimal(0))), "projetado": False})
    pontos.append({"competencia": proj.ultimo_mes, "rbt12": _r(proj.rbt12_atual), "projetado": False, "ancora": True})
    vistos = set()
    unicos = []
    for p in pontos:  # a âncora repete o último ponto real quando a janela é completa
        if p["competencia"] in vistos:
            continue
        vistos.add(p["competencia"])
        unicos.append(p)
    return unicos + [{"competencia": x.competencia, "rbt12": _r(x.rbt12), "projetado": True} for x in proj.pontos]


def analisar(cliente: Cliente, base: Simulacao | None, series: Series | None, hoje: date | None = None) -> dict[str, Any]:
    hoje = hoje or date.today()
    receita = (series or {}).get("receita") or {}
    if not receita:
        return {
            "disponivel": False,
            "motivo": "Ainda não há receita realizada. Importe as notas de venda ou a planilha de dados contábeis na aba Movimento fiscal.",
        }
    janela = _janela(receita)
    n = len(janela)
    saida: dict[str, Any] = {
        "disponivel": True,
        "meses": n,
        "periodo": {"inicio": janela[0], "fim": max(receita)},
        "plano": None,
        "comparacao": [],
        "reavaliacao": None,
        "fator_r": None,
        "projecao": None,
        "resumo": [],
    }

    # Realizado dos últimos 12 meses, anualizado pelos meses com receita informada
    realizado: dict[str, Decimal | None] = {}
    for campo in CAMPOS:
        valores = [(series or {}).get(campo, {}).get(c) for c in janela]
        informados = [v for v in valores if v is not None]
        realizado[campo] = (sum(informados, Decimal(0)) / len(informados) * 12) if informados and (campo == "receita" or len(informados) >= max(3, n // 2)) else None
    saida["realizado_anualizado"] = {c: _r(v) for c, v in realizado.items()}

    base_perfil = perfil_da_simulacao(base) if base is not None else None
    if base is not None and base_perfil is not None and n >= MIN_MESES_COMPARACAO:
        saida["plano"] = {"simulacao_id": base.id, "titulo": base.titulo, "tipo": base.tipo, "criado_em": base.criado_em.isoformat()}
        for campo in CAMPOS:
            plan = Decimal(str(getattr(base_perfil, CAMPO_DO_PERFIL[campo])))
            real = realizado[campo]
            dif = None if real is None else real - plan
            saida["comparacao"].append({
                "campo": campo, "rotulo": ROTULOS[campo], "planejado": _r(plan), "realizado": _r(real),
                "diferenca": _r(dif), "diferenca_pct": _r(dif / plan) if dif is not None and plan > 0 else None,
            })
        receita_plan = Decimal(str(base_perfil.receita_bruta_anual))
        desvio = realizado["receita"] / receita_plan - 1 if receita_plan > 0 and realizado["receita"] is not None else None  # type: ignore[operator]
        saida["desvio_receita"] = _r(desvio)
        frase = f"Receita dos últimos {n} {'mês' if n == 1 else 'meses'}, anualizada: {brl(realizado['receita'])}"
        if desvio is not None:
            frase += f", {pct(abs(desvio), 0)} {'acima' if desvio >= 0 else 'abaixo'} do planejado ({brl(receita_plan)})."
        saida["resumo"].append(frase)
        if n >= MIN_MESES_REAVALIACAO:
            re = _reavaliar(base, realizado)
            saida["reavaliacao"] = re
            if re:
                if re["mudou"]:
                    saida["resumo"].append(
                        f"Com os números reais, a melhor opção passou de {re['melhor_planejado']} para {re['melhor_realizado']}."
                    )
                else:
                    saida["resumo"].append(f"Com os números reais, a recomendação continua a mesma ({re['melhor_realizado']}).")
            fr = _fator_r_real(base_perfil, realizado)
            if fr is not None:
                saida["fator_r"] = {"titulo": fr.titulo, "detalhe": fr.detalhe, "gravidade": fr.gravidade}

    proj = pj.projetar(receita)
    if proj is not None:
        cruz = pj.cruzamentos(proj, pj.limites_do_regime(cliente.regime_atual, hoje))
        saida["projecao"] = {
            "meses_base": proj.meses_base,
            "confianca": proj.confianca,
            "rbt12_atual": _r(proj.rbt12_atual),
            "rbt12_em_12_meses": _r(proj.pontos[-1].rbt12),
            "tendencia_mensal": _r(proj.tendencia_mensal),
            "media_mensal": _r(proj.media_mensal),
            "cruzamentos": [
                {"codigo": c.codigo, "rotulo": c.rotulo, "limite": _r(c.limite), "competencia": c.competencia, "em_meses": c.em_meses}
                for c in cruz
            ],
            "limites": [{"codigo": l.codigo, "rotulo": l.rotulo, "valor": _r(l.valor)} for l in pj.limites_do_regime(cliente.regime_atual, hoje)],
            "serie": _serie_grafico(receita, proj),
        }
        sentido = "crescendo" if proj.tendencia_mensal > 0 else "caindo" if proj.tendencia_mensal < 0 else "estável"
        saida["resumo"].append(
            f"Pelo ritmo dos últimos {proj.meses_base} meses a receita está {sentido}"
            + (f" ({brl(abs(proj.tendencia_mensal))} por mês)" if proj.tendencia_mensal else "")
            + f"; em 12 meses o RBT12 iria de {brl(proj.rbt12_atual)} para {brl(proj.pontos[-1].rbt12)}."
        )
    return saida
