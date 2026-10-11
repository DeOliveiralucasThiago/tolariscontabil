"""Pessoa física: INSS do segurado, IRPF mensal (com a redução da Lei 15.270/2025),
tributação de dividendos e comparativo pró-labore x distribuição de lucros."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from . import tabelas
from .base import ZERO, D, Numero, Resultado, arredondar, brl, pct
from .empresa import ALIQUOTA_CPP


def _inss(data: date) -> dict:
    return tabelas.vigente("inss", data)


def salario_minimo(data: date) -> Decimal:
    return D(_inss(data)["salario_minimo"])


def inss_empregado(salario: Numero, data: date) -> Decimal:
    """Contribuição progressiva do empregado (EC 103/2019): cada faixa com sua alíquota."""
    salario = D(salario)
    total, anterior = ZERO, ZERO
    for f in _inss(data)["empregado"]:
        teto_faixa = D(f["ate"])
        if salario > anterior:
            total += (min(salario, teto_faixa) - anterior) * D(f["aliquota"])
        anterior = teto_faixa
    return arredondar(total)


def inss_contribuinte_individual(remuneracao: Numero, data: date, aliquota: Numero | None = None) -> Decimal:
    """Sócio com pró-labore: 11% limitado ao teto (a empresa recolhe os 20% patronais)."""
    tab = _inss(data)
    aliq = D(aliquota) if aliquota is not None else D(tab["contribuinte_individual_aliquota"])
    return arredondar(min(D(remuneracao), D(tab["teto"])) * aliq)


def irpf_mensal(
    rendimento_tributavel: Numero,
    data: date,
    inss: Numero = 0,
    dependentes: int = 0,
    pensao_alimenticia: Numero = 0,
    outras_deducoes: Numero = 0,
) -> Resultado:
    """IRRF/carnê-leão mensal. Usa a dedução mais vantajosa entre as legais e o desconto
    simplificado, e aplica a redução da Lei 15.270/2025 quando vigente."""
    tab = tabelas.vigente("irpf", data)
    rend = D(rendimento_tributavel)
    res = Resultado(f"IRPF mensal ({tab['ato']})")

    legais = (
        D(inss)
        + dependentes * D(tab["deducao_dependente_mensal"])
        + D(pensao_alimenticia)
        + D(outras_deducoes)
    )
    simplificado = D(tab["desconto_simplificado_mensal"])
    deducao = max(legais, simplificado)
    res.passo(
        "Dedução aplicada",
        f"maior entre deduções legais {brl(legais)} e desconto simplificado {brl(simplificado)}",
        deducao,
        "Lei 9.250/1995, art. 4º; Lei 15.191/2025",
    )
    base = res.passo("Base de cálculo", f"{brl(rend)} - {brl(deducao)}", max(ZERO, rend - deducao))

    imposto = ZERO
    for f in tab["faixas_mensais"]:
        if f["ate"] is None or base <= D(f["ate"]):
            imposto = max(ZERO, base * D(f["aliquota"]) - D(f["deduzir"]))
            res.passo(
                "Imposto pela tabela progressiva",
                f"{brl(base)} x {pct(D(f['aliquota']), 1)} - {brl(f['deduzir'])}",
                imposto,
                tab["ato"],
            )
            break

    red = tab.get("reducao_mensal")
    if red and imposto > 0:
        if rend <= D(red["isencao_ate"]):
            reducao = min(imposto, D(red["reducao_maxima"]))
            formula = f"rendimentos até {brl(red['isencao_ate'])}: redução até {brl(red['reducao_maxima'])}"
        elif rend <= D(red["reducao_parcial_ate"]):
            reducao = min(imposto, max(ZERO, D(red["constante"]) - D(red["coeficiente"]) * rend))
            formula = f"{brl(red['constante'])} - {red['coeficiente']} x {brl(rend)}"
        else:
            reducao = ZERO
            formula = f"rendimentos acima de {brl(red['reducao_parcial_ate'])}: sem redução"
        res.passo("Redução Lei 15.270/2025", formula, reducao, "Lei 15.270/2025")
        imposto -= reducao

    res.tributos["IRPF"] = arredondar(imposto)
    return res


def irpfm_aliquota(renda_anual: Numero) -> Decimal:
    """Alíquota do imposto mínimo (IRPFM): 0% em R$ 600 mil subindo linearmente até 10% em R$ 1,2 mi."""
    div = tabelas.carregar("irpf")["dividendos"]
    renda, minimo, maximo = D(renda_anual), D(div["irpfm_renda_minima_anual"]), D(div["irpfm_renda_aliquota_maxima"])
    if renda <= minimo:
        return ZERO
    if renda >= maximo:
        return D(div["irpfm_aliquota_maxima"])
    return (renda - minimo) / (maximo - minimo) * D(div["irpfm_aliquota_maxima"])


def retencao_dividendos(valor_mensal_mesma_fonte: Numero, data: date) -> Decimal:
    """IRRF de 10% sobre o TOTAL pago no mês por uma mesma empresa quando passa de R$ 50 mil."""
    div = tabelas.carregar("irpf")["dividendos"]
    valor = D(valor_mensal_mesma_fonte)
    if data < date.fromisoformat(div["inicio"]) or valor <= D(div["limite_mensal_por_fonte"]):
        return ZERO
    return arredondar(valor * D(div["aliquota_retencao"]))


@dataclass
class CenarioRetirada:
    descricao: str
    pro_labore: Decimal
    dividendos: Decimal
    resultado: Resultado

    @property
    def custo_mensal(self) -> Decimal:
        return self.resultado.total


def _cenario(
    descricao: str,
    pro_labore: Decimal,
    dividendos: Decimal,
    data: date,
    regime: str,
    aliquota_irpj_csll_real: Decimal,
) -> CenarioRetirada:
    res = Resultado(descricao)
    inss = inss_contribuinte_individual(pro_labore, data)
    res.tributos["INSS do sócio (11%)"] = res.passo(
        "INSS do sócio", f"{brl(pro_labore)} x 11% (limitado ao teto)", inss, "Lei 8.212/1991, art. 21 e 30, §4º"
    )
    ir = irpf_mensal(pro_labore, data, inss=inss)
    res.memoria.extend(ir.memoria)
    res.tributos["IRPF sobre pró-labore"] = ir.tributos["IRPF"]

    if regime in ("presumido", "real", "simples_anexo_iv"):
        res.tributos["INSS patronal (20%)"] = res.passo(
            "CPP patronal sobre pró-labore", f"{brl(pro_labore)} x 20%", pro_labore * ALIQUOTA_CPP,
            "Lei 8.212/1991, art. 22, III",
        )
    if regime == "real":
        custo_dedutivel = pro_labore * (1 + ALIQUOTA_CPP)
        res.tributos["Economia de IRPJ/CSLL (Lucro Real)"] = -res.passo(
            "Pró-labore e CPP reduzem o lucro real",
            f"{brl(custo_dedutivel)} x {pct(aliquota_irpj_csll_real, 0)}",
            custo_dedutivel * aliquota_irpj_csll_real,
            "RIR/2018 (Decreto 9.580/2018)",
        )
    ret = retencao_dividendos(dividendos, data)
    if ret:
        res.tributos["IRRF 10% sobre dividendos"] = res.passo(
            "Retenção sobre dividendos", f"{brl(dividendos)} x 10% (total do mês > R$ 50 mil)", ret,
            "Lei 9.249/1995, art. 6º-A (Lei 15.270/2025)",
        )
    return CenarioRetirada(descricao, pro_labore, dividendos, res)


def comparar_pro_labore_dividendos(
    retirada_mensal: Numero,
    data: date,
    regime: str = "presumido",
    pro_labore_otimizado: Numero | None = None,
    aliquota_irpj_csll_real: Numero = "0.34",
) -> tuple[CenarioRetirada, CenarioRetirada]:
    """Compara 100% pró-labore com pró-labore mínimo + dividendos.

    ``regime``: "simples" (CPP dentro do DAS, anexos I, II, III e V), "simples_anexo_iv",
    "presumido" ou "real". No Lucro Real, o pró-labore reduz o IRPJ/CSLL (economia negativa no custo).
    """
    retirada = D(retirada_mensal)
    minimo = salario_minimo(data)
    pl = D(pro_labore_otimizado) if pro_labore_otimizado is not None else minimo
    if pl > retirada:
        raise ValueError("Pró-labore otimizado maior que a retirada total")
    aliq_real = D(aliquota_irpj_csll_real)

    a = _cenario("100% pró-labore", retirada, ZERO, data, regime, aliq_real)
    b = _cenario(f"Pró-labore de {brl(pl)} + dividendos", pl, retirada - pl, data, regime, aliq_real)

    if pl < minimo:
        b.resultado.alerta(f"Pró-labore abaixo do salário mínimo ({brl(minimo)}).")
    for c in (a, b):
        if c.dividendos:
            c.resultado.alerta(
                "Dividendos pressupõem lucro contábil apurado (ou presumido menos tributos, sem escrituração) "
                "e distribuição aprovada."
            )
    if retirada * 12 > D(tabelas.carregar("irpf")["dividendos"]["irpfm_renda_minima_anual"]):
        aliq = irpfm_aliquota(retirada * 12)
        b.resultado.alerta(
            f"Renda anual acima de R$ 600 mil: sujeito ao IRPFM (alíquota mínima estimada de {pct(aliq)} "
            "sobre a renda total, abatido o IR já pago e o redutor de carga da PJ). Não incluído no custo mensal."
        )
    if regime == "simples":
        b.resultado.alerta(
            "No Simples com fator R, reduzir o pró-labore pode levar a empresa do Anexo III para o V: "
            "verifique com simples.pro_labore_minimo_fator_r()."
        )
    return a, b
