"""Tributos sobre o consumo do Lucro Presumido e do Lucro Real a partir de 2027: CBS e IBS no lugar de PIS e Cofins.

Usa o mesmo modelo do simulador da Reforma (``reforma``): as vendas sem tributos ficam iguais, CBS e IBS são calculados
"por fora" sobre elas, com crédito sobre as compras e despesas (também sem os tributos antigos), e ICMS e ISS seguem a regra
atual multiplicada pelo fator de transição do ano (100% até 2028, 90%, 80%, 70% e 60% de 2029 a 2032, extintos em 2033).
O IRPJ e a CSLL passam a incidir sobre a receita sem PIS/Cofins, CBS e IBS (``receita_base_irpj``).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from . import reforma, tabelas
from .base import ZERO, D, Resultado, brl, pct
from .empresa import Atividade, PerfilEmpresa, fracao_icms_iss

PRIMEIRO_ANO = 2027
BASE_LEGAL = "EC 132/2023, ADCT arts. 125 a 133; LC 214/2025 (alíquotas de referência ainda estimadas)"


def usa_ibs_cbs(ano: int) -> bool:
    return ano >= PRIMEIRO_ANO


def _pis_cofins_atual(nao_cumulativo: bool) -> Decimal:
    return reforma.PIS_COFINS_NAO_CUMULATIVO if nao_cumulativo else reforma.PIS_COFINS_CUMULATIVO


def _partes(perfil: PerfilEmpresa, nao_cumulativo: bool) -> list[tuple[Atividade, Decimal, Decimal, Decimal]]:
    """Por atividade, no mercado interno: (atividade, receita, ICMS/ISS nominal embutido, vendas sem tributos)."""
    internas = perfil.partes_internas
    servicos = sum((v for a, v in internas if not a.vende_mercadoria), ZERO)
    pis_cofins = _pis_cofins_atual(nao_cumulativo)
    partes = []
    for atividade, valor in internas:
        if atividade.vende_mercadoria:
            local = valor * perfil.aliquota_icms
        elif perfil.sociedade_profissionais:
            local = perfil.iss_fixo_anual * (valor / servicos if servicos else ZERO)  # ISS fixo repartido entre as atividades de serviço
        else:
            local = valor * perfil.aliquota_iss
        partes.append((atividade, valor, local, max(ZERO, valor * (1 - pis_cofins) - local)))
    return partes


def _entrada(perfil: PerfilEmpresa, nao_cumulativo: bool) -> reforma.EntradaReforma:
    partes = _partes(perfil, nao_cumulativo)
    base_total = sum((p[3] for p in partes), ZERO)
    reducao = perfil.reducao_ibs_cbs
    if perfil.tem_atividades_mistas and base_total > 0:
        # Em atividade mista a redução vale só para a atividade principal (as profissões e setores da lei são da atividade, não da empresa)
        base_principal = sum((p[3] for p in partes if p[0] is perfil.atividade), ZERO)
        reducao = reducao * base_principal / base_total
    return reforma.EntradaReforma(
        receita_bruta_anual=perfil.receita_interna_anual,
        vende_mercadoria=perfil.receita_mercadorias_anual > 0,
        pis_cofins_nao_cumulativo=nao_cumulativo,
        compras_anual=perfil.compras_anual,
        despesas_creditaveis_anual=perfil.despesas_creditaveis_anual,
        aliquota_icms=perfil.aliquota_icms,
        aliquota_icms_credito=perfil.aliquota_icms_credito,
        aliquota_iss=perfil.aliquota_iss,
        base_venda_anual=base_total,
        reducao_setorial=reducao,
        anos=[perfil.ano],
    )


def receita_base_irpj(perfil: PerfilEmpresa, nao_cumulativo: bool) -> Decimal:
    """Receita bruta sem o PIS/Cofins que deixa de existir e sem o ICMS/ISS que a transição já retirou do preço."""
    pis_cofins = _pis_cofins_atual(nao_cumulativo)
    fracao = fracao_icms_iss(perfil.ano)
    interna = sum((valor * (1 - pis_cofins) - local * (1 - fracao) for _, valor, local, _ in _partes(perfil, nao_cumulativo)), ZERO)
    return interna + perfil.receita_exterior_anual


@dataclass
class ConsumoIbsCbs:
    pago: Decimal
    """CBS + IBS a recolher no ano."""
    credito_aproveitado: Decimal
    """Crédito de CBS e IBS das compras e despesas que abateu o débito (reduz o custo no Lucro Real)."""


def lancar_ibs_cbs(perfil: PerfilEmpresa, res: Resultado, nao_cumulativo: bool) -> ConsumoIbsCbs:
    """Lança CBS e IBS (com a memória de cálculo) no resultado do Presumido ou do Real."""
    e = _entrada(perfil, nao_cumulativo)
    base_venda = reforma.base_venda_sem_tributos(e)
    ano = reforma._ano(e, perfil.ano, base_venda)
    cfg = tabelas.carregar("reforma_tributaria")["anos"][str(perfil.ano)]
    debitos = base_venda * sum((venda for _, venda, _ in reforma.aliquotas_novas(e, cfg)), ZERO)

    pago = ZERO
    for nome in ("CBS", "IBS"):
        if nome in ano.resultado.tributos:
            res.tributos[nome] = ano.resultado.tributos[nome]
            pago += ano.resultado.tributos[nome]
    res.memoria.extend(p for p in ano.resultado.memoria if p.descricao.startswith(("CBS", "IBS")))
    for a in ano.resultado.alertas:
        res.alerta(a)
    if base_venda:
        res.passo(
            "Vendas sem tributos sobre o consumo",
            f"{brl(perfil.receita_interna_anual)} sem o PIS/Cofins atual e o ICMS/ISS embutidos no preço",
            base_venda,
            BASE_LEGAL,
        )
    return ConsumoIbsCbs(pago, debitos - pago)


def alertas(perfil: PerfilEmpresa, res: Resultado) -> None:
    """Premissas que acompanham o Presumido e o Real a partir de 2027 (as alíquotas são estimativas)."""
    estimadas = tabelas.carregar("reforma_tributaria")["aliquotas_referencia_estimadas"]
    res.alerta(
        f"{perfil.ano}: o regime normal paga CBS e IBS (não cumulativos, com crédito sobre as compras) no lugar de PIS e Cofins. "
        f"Alíquotas de referência estimadas: CBS {pct(estimadas['cbs'], 1)} e IBS {pct(estimadas['ibs'], 1)} (a de 2027 depende de "
        "TCU e Senado). Modelo: vendas sem tributos mantidas, créditos integrais das compras informadas (fornecedores do Simples geram "
        "crédito menor) e Imposto Seletivo fora. ICMS e ISS seguem a transição do ADCT, art. 128."
    )
    res.alerta(
        "IRPJ e CSLL calculados sobre a receita sem PIS/Cofins, CBS e IBS. É uma tese (IBS e CBS não compõem a receita bruta, como o IPI "
        "destacado): a LC 214/2025, art. 12, § 2º, I, tira o IBS e a CBS só da base do próprio IBS e da CBS, e não há decisão judicial sobre o "
        "Lucro Presumido. Confirme com o contador."
    )
    if perfil.tem_atividades_mistas and perfil.reducao_ibs_cbs:
        res.alerta("Atividades mistas: a redução de IBS e CBS foi aplicada só à receita da atividade principal.")
    if perfil.reducao_ibs_cbs:
        res.alerta(
            f"Redução de {pct(perfil.reducao_ibs_cbs, 0)} nas alíquotas de IBS e CBS aplicada (LC 214/2025, art. 127 para as 18 profissões "
            "regulamentadas, art. 128 e seguintes para os demais setores); vale só para o que a lei lista e, para sociedades, se cumpridos "
            "os requisitos do art. 127, § 1º, II. Confirme o enquadramento."
        )
    elif perfil.sociedade_profissionais or perfil.servicos_hospitalares:
        res.alerta(
            "Sem redução de alíquota de IBS e CBS: as 18 profissões regulamentadas do art. 127 da LC 214/2025 (por exemplo advogados, contabilistas, "
            "engenheiros e administradores) têm 30% e os serviços de saúde do Anexo III (art. 130), 60%. Medicina humana não está na lista de 30%. Se o "
            "cliente se enquadra, informe a redução para não superestimar o custo."
        )
    if perfil.sociedade_profissionais:
        res.alerta(reforma.ALERTA_ISS_FIXO)
