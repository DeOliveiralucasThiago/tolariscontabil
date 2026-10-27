"""Lucro Real anual (estimativa gerencial): PIS/Cofins não cumulativos e IRPJ/CSLL sobre o lucro."""

from __future__ import annotations

from decimal import Decimal

from . import consumo
from .base import ZERO, D, Resultado, brl, pct
from .empresa import PerfilEmpresa, inss_patronal_regime_normal, tributo_sobre_receita_local
from .simples import alerta_exportacao

PIS_NC = D("0.0165")
COFINS_NC = D("0.076")
IRPJ = D("0.15")
IRPJ_ADICIONAL = D("0.10")
IRPJ_ADICIONAL_LIMITE_ANUAL = D("240000")
CSLL = D("0.09")


def calcular(
    perfil: PerfilEmpresa, adicoes: Decimal | int = 0, exclusoes: Decimal | int = 0
) -> Resultado:
    """Lucro Real anual sem LALUR detalhado: ``adicoes``/``exclusoes`` permitem ajustar o lucro contábil."""
    res = Resultado("Lucro Real")
    receita = perfil.receita_bruta_anual
    interna = perfil.receita_interna_anual
    base_credito = perfil.compras_anual + perfil.despesas_creditaveis_anual

    novo = consumo.usa_ibs_cbs(perfil.ano)
    receita_lucro = receita
    credito_ibs_cbs = ZERO
    if novo:
        credito_ibs_cbs = consumo.lancar_ibs_cbs(perfil, res, nao_cumulativo=True).credito_aproveitado
        receita_lucro = res.passo(
            "Receita para o lucro",
            f"{brl(receita)} sem PIS/Cofins, CBS e IBS (e sem o ICMS/ISS já retirado pela transição)",
            consumo.receita_base_irpj(perfil, nao_cumulativo=True),
            "Lei 9.249/1995, art. 15 (receita bruta); IBS e CBS fora da receita bruta é tese, sem decisão judicial",
        )
    else:
        for nome, aliq, lei in (("PIS", PIS_NC, "Lei 10.637/2002"), ("Cofins", COFINS_NC, "Lei 10.833/2003")):
            debito = res.passo(f"{nome} - débito", f"{brl(interna)} x {pct(aliq)}", interna * aliq, lei)
            credito = res.passo(
                f"{nome} - crédito",
                f"({brl(perfil.compras_anual)} compras + {brl(perfil.despesas_creditaveis_anual)} despesas "
                f"creditáveis) x {pct(aliq)}",
                base_credito * aliq,
                f"{lei}, art. 3º",
            )
            if credito > debito:
                res.alerta(f"Créditos de {nome} superam os débitos: saldo credor não entra no total.")
            res.tributos[nome] = max(ZERO, debito - credito)

    tributo_sobre_receita_local(perfil, res)
    res.tributos["INSS patronal"] = inss_patronal_regime_normal(perfil, res)

    tributos_dedutiveis = sum((v for k, v in res.tributos.items() if k not in ("CBS", "IBS")), ZERO)
    lucro_contabil = res.passo(
        "Lucro antes do IRPJ/CSLL",
        f"{brl(receita_lucro)} receita - {brl(perfil.compras_anual)} compras - "
        f"{brl(perfil.despesas_creditaveis_anual + perfil.outras_despesas_anual)} despesas - "
        f"{brl(perfil.folha_clt_anual + perfil.pro_labore_anual)} folha e pró-labore - "
        f"{brl(perfil.fgts_anual)} FGTS - {brl(tributos_dedutiveis)} tributos dedutíveis"
        + (f" + {brl(credito_ibs_cbs)} de crédito de CBS e IBS" if novo else ""),
        receita_lucro
        + credito_ibs_cbs
        - perfil.compras_anual
        - perfil.despesas_creditaveis_anual
        - perfil.outras_despesas_anual
        - perfil.folha_clt_anual
        - perfil.pro_labore_anual
        - perfil.fgts_anual
        - tributos_dedutiveis,
        "Lei 6.404/1976 (DRE)",
    )
    variacao = perfil.variacao_cambial_anual
    if variacao:
        lucro_contabil = res.passo(
            "Lucro com variação cambial",
            f"{brl(lucro_contabil)} + variação cambial líquida {brl(variacao)}",
            lucro_contabil + variacao,
            "Lei 9.718/1998, art. 9º; MP 2.158-35/2001, art. 30",
        )
    lucro_real = lucro_contabil + D(adicoes) - D(exclusoes)
    if adicoes or exclusoes:
        res.passo("Lucro real (LALUR)", f"{brl(lucro_contabil)} + {brl(adicoes)} - {brl(exclusoes)}", lucro_real)

    if lucro_real <= 0:
        res.alerta("Prejuízo fiscal: IRPJ/CSLL zerados; o prejuízo compensa até 30% de lucros futuros.")
        lucro_real = ZERO

    res.tributos["IRPJ"] = res.passo(
        "IRPJ",
        f"{brl(lucro_real)} x {pct(IRPJ, 0)} + {pct(IRPJ_ADICIONAL, 0)} sobre o que exceder "
        f"{brl(IRPJ_ADICIONAL_LIMITE_ANUAL)}",
        lucro_real * IRPJ + max(ZERO, lucro_real - IRPJ_ADICIONAL_LIMITE_ANUAL) * IRPJ_ADICIONAL,
        "Lei 9.249/1995, art. 3º; Lei 9.430/1996, art. 2º",
    )
    res.tributos["CSLL"] = res.passo(
        "CSLL", f"{brl(lucro_real)} x {pct(CSLL, 0)}", lucro_real * CSLL, "Lei 7.689/1988, art. 3º"
    )
    alerta_exportacao(perfil, res)
    if novo:
        consumo.alertas(perfil, res)
    if variacao:
        res.alerta(
            "Variação cambial entra no lucro do Lucro Real (ganho soma, perda deduz). A regra geral é o reconhecimento "
            "pelo regime de caixa, com opção irrevogável pela competência no ano; confirme a opção do cliente."
        )
    res.alerta(
        "Estimativa gerencial: considera todo o estoque comprado como vendido no ano e não detalha "
        "adições/exclusões do LALUR além das informadas."
    )
    return res
