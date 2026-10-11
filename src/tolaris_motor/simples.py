"""Simples Nacional: alíquota efetiva por anexo/faixa, fator R e DAS anual estimado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from . import tabelas
from .base import ZERO, D, Numero, Resultado, brl, pct
from .empresa import ALIQUOTA_CPP, Atividade, PerfilEmpresa

BASE_LEGAL_ALIQUOTA = "LC 123/2006, art. 18, §1º e §1º-A"
BASE_LEGAL_FATOR_R = "LC 123/2006, art. 18, §5º-J, §5º-M e §24"


def _tabela(data: date) -> dict:
    return tabelas.vigente("simples_nacional", data)


def faixa(anexo: str, rbt12: Numero, data: date | None = None) -> tuple[int, dict]:
    """Retorna (número da faixa 1..6, dados da faixa) para a receita bruta dos últimos 12 meses."""
    rbt12 = D(rbt12)
    tab = _tabela(data or date.today())
    faixas = tab["anexos"][anexo]["faixas"]
    for i, f in enumerate(faixas, start=1):
        if rbt12 <= D(f["ate"]):
            return i, f
    raise ValueError(f"RBT12 de {brl(rbt12)} excede o limite do Simples Nacional")


def aliquota_efetiva(anexo: str, rbt12: Numero, data: date | None = None) -> Decimal:
    """(RBT12 x alíquota nominal - parcela a deduzir) / RBT12.

    Para RBT12 zero (empresa em início de atividade) aplica-se a alíquota nominal da 1ª faixa.
    """
    rbt12 = D(rbt12)
    _, f = faixa(anexo, rbt12, data)
    if rbt12 == 0:
        return D(f["aliquota"])
    return (rbt12 * D(f["aliquota"]) - D(f["deduzir"])) / rbt12


def folha_fator_r(perfil: PerfilEmpresa) -> Decimal:
    """Folha de salários para o fator R: salários + pró-labore + FGTS (salvo valor informado)."""
    if perfil.folha_fator_r_anual is not None:
        return perfil.folha_fator_r_anual
    return perfil.folha_clt_anual + perfil.pro_labore_anual + perfil.fgts_anual


def fator_r(folha_12m: Numero, rbt12: Numero) -> Decimal:
    rbt12 = D(rbt12)
    return D(folha_12m) / rbt12 if rbt12 > 0 else ZERO


def pro_labore_minimo_fator_r(
    rbt12: Numero, folha_atual_12m: Numero, data: date | None = None
) -> Decimal:
    """Pró-labore MENSAL adicional necessário para o fator R atingir 28% (Anexo III em vez do V)."""
    minimo = D(_tabela(data or date.today())["fator_r_minimo"])
    falta = D(rbt12) * minimo - D(folha_atual_12m)
    return max(ZERO, falta) / 12


def anexo_da_atividade(perfil: PerfilEmpresa, res: Resultado | None = None) -> str:
    a = perfil.atividade
    if a is Atividade.COMERCIO:
        return "I"
    if a is Atividade.INDUSTRIA:
        return "II"
    if a is Atividade.SERVICO_ANEXO_III:
        return "III"
    if a is Atividade.SERVICO_ANEXO_IV:
        return "IV"
    data = date(perfil.ano, 1, 1)
    minimo = D(_tabela(data)["fator_r_minimo"])
    folha = folha_fator_r(perfil)
    r = fator_r(folha, perfil.receita_bruta_anual)
    anexo = "III" if r >= minimo else "V"
    if res is not None:
        origem = "informada" if perfil.folha_fator_r_anual is not None else "salários + pró-labore + FGTS 8%"
        res.passo(
            "Fator R (folha 12 meses / RBT12)",
            f"{brl(folha)} ({origem}) / {brl(perfil.receita_bruta_anual)} = {pct(r)} "
            f"-> Anexo {anexo}",
            r,
            BASE_LEGAL_FATOR_R,
        )
        if anexo == "V":
            extra = pro_labore_minimo_fator_r(perfil.receita_bruta_anual, folha, data)
            res.alerta(
                f"Fator R abaixo de {pct(minimo, 0)}: acrescentar cerca de {brl(extra)}/mês de "
                "pró-labore levaria ao Anexo III. Compare o custo do INSS sobre esse pró-labore."
            )
    return anexo


def calcular(perfil: PerfilEmpresa) -> Resultado:
    """DAS anual estimado supondo faturamento mensal constante (RBT12 = receita anual)."""
    res = Resultado("Simples Nacional")
    data = date(perfil.ano, 1, 1)
    tab = _tabela(data)
    receita = perfil.receita_bruta_anual

    if receita > D(tab["limite_receita_anual"]):
        res.aplicavel = False
        res.alerta(f"Receita acima de {brl(tab['limite_receita_anual'])}: empresa não pode optar pelo Simples.")
        return res

    anexo = anexo_da_atividade(perfil, res)
    n, f = faixa(anexo, receita, data)
    aliq = aliquota_efetiva(anexo, receita, data)
    res.passo(
        f"Alíquota efetiva - Anexo {anexo}, {n}ª faixa",
        f"({brl(receita)} x {pct(D(f['aliquota']))} - {brl(f['deduzir'])}) / {brl(receita)} = {pct(aliq, 4)}",
        aliq,
        BASE_LEGAL_ALIQUOTA,
    )
    res.tributos["DAS"] = res.passo(
        "DAS anual", f"{brl(receita)} x {pct(aliq, 4)}", receita * aliq, "LC 123/2006, art. 13"
    )

    if anexo == "IV":
        aliq_folha = ALIQUOTA_CPP + perfil.rat
        res.tributos["INSS patronal (fora do DAS)"] = res.passo(
            "CPP fora do DAS (Anexo IV)",
            f"{brl(perfil.folha_clt_anual)} x ({pct(ALIQUOTA_CPP)} + {pct(perfil.rat)} RAT) + "
            f"{brl(perfil.pro_labore_anual)} x {pct(ALIQUOTA_CPP)}",
            perfil.folha_clt_anual * aliq_folha + perfil.pro_labore_anual * ALIQUOTA_CPP,
            "LC 123/2006, art. 18, §5º-C e art. 13, VI",
        )

    if receita > D(tab["sublimite_icms_iss"]):
        res.alerta(
            f"Receita acima do sublimite de {brl(tab['sublimite_icms_iss'])}: ICMS/ISS passam a ser "
            "recolhidos fora do DAS. Este cálculo usa a alíquota cheia do DAS (aproximação)."
        )
    res.alerta("Estimativa com faturamento mensal constante; o DAS real varia mês a mês com o RBT12.")
    return res
