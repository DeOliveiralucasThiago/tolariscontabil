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


def faixa(anexo: str, rbt12: Numero, data: date | None = None, extrapolar: bool = False) -> tuple[int, dict]:
    """Retorna (número da faixa 1..6, dados da faixa) para a receita bruta dos últimos 12 meses.

    ``extrapolar`` usa a última faixa quando o RBT12 passa do teto (só acontece com receita de exportação,
    que tem limite próprio além dos R$ 4,8 mi do mercado interno).
    """
    rbt12 = D(rbt12)
    tab = _tabela(data or date.today())
    faixas = tab["anexos"][anexo]["faixas"]
    for i, f in enumerate(faixas, start=1):
        if rbt12 <= D(f["ate"]):
            return i, f
    if extrapolar:
        return len(faixas), faixas[-1]
    raise ValueError(f"RBT12 de {brl(rbt12)} excede o limite do Simples Nacional")


def aliquota_efetiva(anexo: str, rbt12: Numero, data: date | None = None, extrapolar: bool = False) -> Decimal:
    """(RBT12 x alíquota nominal - parcela a deduzir) / RBT12.

    Para RBT12 zero (empresa em início de atividade) aplica-se a alíquota nominal da 1ª faixa.
    """
    rbt12 = D(rbt12)
    _, f = faixa(anexo, rbt12, data, extrapolar)
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


BASE_LEGAL_EXPORTACAO = "Res. CGSN 140/2018, art. 25, §§ 3º, 4º e 4º-A; LC 116/2003, art. 2º, I; LC 123/2006, art. 18"
TRIBUTOS_DESCONSIDERADOS_EXPORTACAO = {
    "servicos": ("pis", "cofins", "iss"),
    "mercadorias": ("pis", "cofins", "icms", "ipi"),
}


def alerta_exportacao(perfil: PerfilEmpresa, res: Resultado) -> None:
    """Avisos que acompanham qualquer cálculo com receita do exterior (iguais nos três regimes)."""
    if perfil.receita_exterior_anual:
        if perfil.atividade.vende_mercadoria:
            res.alerta(
                f"Receita de exportação de mercadorias ({brl(perfil.receita_exterior_anual)}): tratada sem ICMS, IPI e "
                "PIS/Cofins. Guarde a declaração de exportação (DU-E) e o contrato de câmbio."
            )
        else:
            res.alerta(
                f"Receita de exportação de serviços ({brl(perfil.receita_exterior_anual)}): tratada sem ISS e sem "
                "PIS/Cofins. Só vale se o serviço foi prestado a residente no exterior, o resultado se verifica no "
                "exterior e o pagamento representa ingresso de divisas (Res. CGSN 140/2018, art. 25, §4º; "
                "LC 116/2003, art. 2º, parágrafo único). Guarde contrato, nota fiscal e contrato de câmbio."
            )
    if perfil.variacao_cambial_anual:
        res.alerta(
            f"Variação cambial líquida de {brl(perfil.variacao_cambial_anual)} informada: o tratamento depende do regime "
            "(veja os alertas de cada um)."
        )


def calcular(perfil: PerfilEmpresa) -> Resultado:
    """DAS anual estimado supondo faturamento mensal constante (RBT12 = receita anual)."""
    res = Resultado("Simples Nacional")
    data = date(perfil.ano, 1, 1)
    tab = _tabela(data)
    receita = perfil.receita_bruta_anual
    exterior = perfil.receita_exterior_anual
    interna = perfil.receita_interna_anual
    limite = D(tab["limite_receita_anual"])

    # Mercado interno e exportação têm, cada um, o limite de R$ 4,8 mi (Res. CGSN 140/2018, art. 2º, §1º)
    if interna > limite or exterior > limite:
        res.aplicavel = False
        if exterior == 0:
            res.alerta(f"Receita acima de {brl(limite)}: empresa não pode optar pelo Simples Nacional.")
        elif interna > limite:
            res.alerta(f"Receita do mercado interno acima de {brl(limite)}: empresa não pode optar pelo Simples Nacional.")
        else:
            res.alerta(f"Receita de exportação acima de {brl(limite)}: empresa não pode optar pelo Simples Nacional.")
        return res

    extrapolar = receita > limite
    anexo = anexo_da_atividade(perfil, res)
    n, f = faixa(anexo, receita, data, extrapolar)
    aliq = aliquota_efetiva(anexo, receita, data, extrapolar)
    res.passo(
        f"Alíquota efetiva - Anexo {anexo}, {n}ª faixa",
        f"({brl(receita)} x {pct(D(f['aliquota']))} - {brl(f['deduzir'])}) / {brl(receita)} = {pct(aliq, 4)}",
        aliq,
        BASE_LEGAL_ALIQUOTA,
    )
    if exterior == 0:
        res.tributos["DAS"] = res.passo(
            "DAS anual", f"{brl(receita)} x {pct(aliq, 4)}", receita * aliq, "LC 123/2006, art. 13"
        )
    else:
        fracoes = partilha(anexo, receita, data, extrapolar)
        tipo = "mercadorias" if perfil.atividade.vende_mercadoria else "servicos"
        desconsiderados = TRIBUTOS_DESCONSIDERADOS_EXPORTACAO[tipo]
        fracao_excluida = sum((fracoes.get(k, ZERO) for k in desconsiderados), ZERO)
        das_interno = res.passo(
            "DAS - mercado interno", f"{brl(interna)} x {pct(aliq, 4)}", interna * aliq, "LC 123/2006, art. 13"
        )
        das_exterior = res.passo(
            "DAS - exportação",
            f"{brl(exterior)} x {pct(aliq, 4)} x (1 - {pct(fracao_excluida, 2)} de {'/'.join(t.upper() for t in desconsiderados)} "
            "na partilha da faixa)",
            exterior * aliq * (1 - fracao_excluida),
            BASE_LEGAL_EXPORTACAO,
        )
        res.tributos["DAS"] = res.passo("DAS anual", f"{brl(das_interno)} + {brl(das_exterior)}", das_interno + das_exterior)
        if extrapolar:
            res.alerta(
                f"Receita total de {brl(receita)} passa de {brl(limite)} por causa da exportação: usada a última faixa "
                "do Anexo (aproximação). Confira a apuração no PGDAS-D."
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

    if interna > D(tab["sublimite_icms_iss"]):
        res.alerta(
            f"Receita acima do sublimite de {brl(tab['sublimite_icms_iss'])}: ICMS/ISS passam a ser "
            "recolhidos fora do DAS. Este cálculo usa a alíquota cheia do DAS (aproximação)."
        )
    alerta_exportacao(perfil, res)
    if perfil.variacao_cambial_anual:
        res.alerta(
            "Simples: a variação cambial não entra neste cálculo do DAS. Confirme com o contador se ela integra a "
            "receita bruta (depende de ser variação ligada a receita de exportação ou receita financeira)."
        )
    if exterior:
        res.alerta(
            "A Resolução CGSN 190/2026 alterou o art. 25 da Resolução CGSN 140/2018: confira a redação consolidada "
            "sobre a qualificação da operação como exportação antes de segregar a receita no PGDAS-D."
        )
    res.alerta("Estimativa com faturamento mensal constante; o DAS real varia mês a mês com o RBT12.")
    return res


TRIBUTOS_FEDERAIS = ("irpj", "csll", "cofins", "pis", "cpp", "ipi")


def partilha(anexo: str, rbt12: Numero, data: date | None = None, extrapolar: bool = False) -> dict[str, Decimal]:
    """Fração do DAS que cabe a cada tributo na faixa do RBT12.

    Aplica o teto de 5% de ISS efetivo: o excesso vai, proporcionalmente, para os
    tributos federais da mesma faixa (LC 123/2006, Anexo III, nota da 5ª faixa).
    """
    data = data or date.today()
    _, f = faixa(anexo, rbt12, data, extrapolar)
    fracoes = {k: D(v) for k, v in f["partilha"].items()}
    teto_iss = D(_tabela(data)["iss_efetivo_maximo"])
    aliq = aliquota_efetiva(anexo, rbt12, data, extrapolar)
    iss = fracoes.get("iss", ZERO)
    if aliq > 0 and aliq * iss > teto_iss:
        nova = teto_iss / aliq
        excesso = iss - nova
        federais = {k: v for k, v in fracoes.items() if k in TRIBUTOS_FEDERAIS}
        soma = sum(federais.values(), ZERO)
        for k, v in federais.items():
            fracoes[k] = v + excesso * v / soma
        fracoes["iss"] = nova
    return fracoes
