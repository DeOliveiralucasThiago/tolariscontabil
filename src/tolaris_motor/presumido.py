"""Lucro Presumido: IRPJ/CSLL trimestrais, PIS/Cofins cumulativos, ISS/ICMS e INSS patronal."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from . import tabelas
from .base import ZERO, D, Resultado, brl, pct
from .empresa import PerfilEmpresa, inss_patronal_regime_normal, tributo_sobre_receita_local


def _base_presumida(
    res: Resultado,
    tributo: str,
    receita_trim: Decimal,
    percentual: Decimal,
    lc224: dict | None,
    inicio_acrescimo: str,
    inicio_trimestre: date,
    trimestre: int,
) -> Decimal:
    base = receita_trim * percentual
    formula = f"{brl(receita_trim)} x {pct(percentual, 1)}"
    if lc224 and inicio_trimestre >= date.fromisoformat(lc224[inicio_acrescimo]):
        limite_trim = D(lc224["receita_anual_isenta"]) / 4
        excedente = max(ZERO, receita_trim - limite_trim)
        if excedente > 0:
            acrescimo = excedente * percentual * D(lc224["acrescimo_relativo"])
            base += acrescimo
            formula += (
                f" + acréscimo LC 224/2025: {brl(excedente)} excedente x {pct(percentual, 1)} x "
                f"{pct(lc224['acrescimo_relativo'], 0)}"
            )
    return res.passo(f"{trimestre}º tri - base presumida {tributo}", formula, base, "Lei 9.249/1995, arts. 15 e 20")


def calcular(perfil: PerfilEmpresa) -> Resultado:
    """Apuração anual = soma de 4 trimestres iguais (receita distribuída uniformemente)."""
    res = Resultado("Lucro Presumido")
    tab = tabelas.vigente("lucro_presumido", date(perfil.ano, 1, 1))
    presuncoes = tabelas.carregar("lucro_presumido")["presuncoes"]
    receita = perfil.receita_bruta_anual

    if receita > D(tab["limite_receita_anual"]):
        res.aplicavel = False
        res.alerta(f"Receita acima de {brl(tab['limite_receita_anual'])}: Lucro Real obrigatório.")
        return res
    if perfil.presuncao not in presuncoes:
        raise ValueError(f"Presunção desconhecida: {perfil.presuncao}")

    p = presuncoes[perfil.presuncao]
    p_irpj, p_csll = D(p["irpj"]), D(p["csll"])
    res.passo(
        "Percentuais de presunção",
        f"{p['descricao']}: IRPJ {pct(p_irpj, 1)}, CSLL {pct(p_csll, 1)}",
        p_irpj,
        "Lei 9.249/1995, art. 15, §1º e art. 20",
    )

    lc224 = tab.get("lc224")
    receita_trim = receita / 4
    limite_adicional = D(tab["irpj_adicional_limite_trimestral"])
    irpj_total = csll_total = ZERO
    for t in range(1, 5):
        inicio = date(perfil.ano, 3 * t - 2, 1)
        base_irpj = _base_presumida(res, "IRPJ", receita_trim, p_irpj, lc224, "irpj_inicio", inicio, t)
        irpj = base_irpj * D(tab["irpj_aliquota"])
        adicional = max(ZERO, base_irpj - limite_adicional) * D(tab["irpj_adicional_aliquota"])
        irpj_total += res.passo(
            f"{t}º tri - IRPJ",
            f"{brl(base_irpj)} x {pct(tab['irpj_aliquota'], 0)} + adicional "
            f"{pct(tab['irpj_adicional_aliquota'], 0)} sobre o que exceder {brl(limite_adicional)}",
            irpj + adicional,
            "Lei 9.430/1996, arts. 3º e 4º",
        )
        base_csll = _base_presumida(res, "CSLL", receita_trim, p_csll, lc224, "csll_inicio", inicio, t)
        csll_total += res.passo(
            f"{t}º tri - CSLL",
            f"{brl(base_csll)} x {pct(tab['csll_aliquota'], 0)}",
            base_csll * D(tab["csll_aliquota"]),
            "Lei 7.689/1988, art. 3º",
        )

    res.tributos["IRPJ"] = irpj_total
    res.tributos["CSLL"] = csll_total
    res.tributos["PIS"] = res.passo(
        "PIS cumulativo", f"{brl(receita)} x {pct(tab['pis_cumulativo'])}",
        receita * D(tab["pis_cumulativo"]), "Lei 9.715/1998",
    )
    res.tributos["Cofins"] = res.passo(
        "Cofins cumulativa", f"{brl(receita)} x {pct(tab['cofins_cumulativo'])}",
        receita * D(tab["cofins_cumulativo"]), "Lei 9.718/1998",
    )
    tributo_sobre_receita_local(perfil, res)
    res.tributos["INSS patronal"] = inss_patronal_regime_normal(perfil, res)

    if lc224 and receita > D(lc224["receita_anual_isenta"]):
        res.alerta(
            "Aplicado o acréscimo de 10% na presunção (LC 224/2025) sobre a receita acima de R$ 5 mi/ano. "
            "A regra é questionada no STF (ADIs 7920 e 7936) e há liminares afastando-a; confirme a situação do cliente."
        )
    return res
