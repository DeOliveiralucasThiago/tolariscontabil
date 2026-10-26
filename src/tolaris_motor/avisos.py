"""Avisos automáticos para a carteira do contador: fator R e proximidade dos limites de receita.

Funções puras: recebem os dados do cliente e devolvem ``Aviso`` com gravidade, valor potencial
em R$ por ano (quando dá para calcular) e base legal. As tabelas vêm dos mesmos JSON do motor,
então uma mudança de lei atualiza os avisos junto com os cálculos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from . import pessoa_fisica, simples, tabelas
from .autonomo import limite_mei
from .base import ZERO, D, Numero, arredondar, brl, pct
from .empresa import Atividade, PerfilEmpresa

GRAVIDADES = ("critico", "atencao", "oportunidade", "info")
"""Da mais urgente à menos urgente."""

LIMIAR_ATENCAO = D("0.80")
LIMIAR_CRITICO = D("0.95")
MARGEM_FATOR_R = D("0.03")
"""Fator R até 3 pontos acima do mínimo já merece atenção."""
TOLERANCIA_EXCESSO = D("0.20")

BASE_LEGAL_MEI = "LC 123/2006, art. 18-A, §§ 7º a 9º"
BASE_LEGAL_LIMITES = "LC 123/2006, art. 3º"
BASE_LEGAL_LC224 = "LC 224/2025"
BASE_LEGAL_PRESUMIDO = "Lei 9.718/1998, art. 14, I"


@dataclass(frozen=True)
class Aviso:
    codigo: str
    gravidade: str
    titulo: str
    detalhe: str
    valor: Decimal | None = None
    """Potencial em R$ por ano (economia a ganhar ou imposto a mais em risco), quando calculável."""
    base_legal: str = ""


def _das(anexo: str, receita: Decimal, data: date) -> Decimal:
    return receita * simples.aliquota_efetiva(anexo, receita, data)


# --- Fator R -------------------------------------------------------------------------------
def avaliar_fator_r(perfil: PerfilEmpresa) -> Aviso | None:
    """Fator R abaixo do mínimo (cliente no Anexo V) ou perto dele (risco de cair no Anexo V)."""
    if perfil.atividade is not Atividade.SERVICO_FATOR_R:
        return None
    data = date(perfil.ano, 1, 1)
    tab = tabelas.vigente("simples_nacional", data)
    receita = perfil.receita_bruta_anual
    if receita <= 0 or receita > D(tab["limite_receita_anual"]):
        return None
    minimo = D(tab["fator_r_minimo"])
    folha = simples.folha_fator_r(perfil)
    r = simples.fator_r(folha, receita)
    das_iii, das_v = _das("III", receita, data), _das("V", receita, data)

    if r >= minimo:
        margem = r - minimo
        if margem > MARGEM_FATOR_R:
            return None
        folha_sobrando = folha - receita * minimo
        return Aviso(
            codigo="fator_r_margem",
            gravidade="atencao",
            titulo=f"Fator R de {pct(r)}, perto do mínimo de {pct(minimo, 0)}",
            detalhe=(
                f"Sobram só {brl(folha_sobrando)} de folha por ano acima do mínimo. Se a receita subir ou a folha cair, "
                f"o cliente passa do Anexo III para o V e o DAS aumenta cerca de {brl(das_v - das_iii)} por ano "
                "(com a receita atual)."
            ),
            valor=arredondar(das_v - das_iii),
            base_legal=simples.BASE_LEGAL_FATOR_R,
        )

    extra_mensal = simples.pro_labore_minimo_fator_r(receita, folha, data)
    atual_mensal = perfil.pro_labore_anual / 12
    inss_extra = (
        pessoa_fisica.inss_contribuinte_individual(atual_mensal + extra_mensal, data)
        - pessoa_fisica.inss_contribuinte_individual(atual_mensal, data)
    ) * 12
    ganho = das_v - das_iii - inss_extra
    resumo = (
        f"Elevar o pró-labore em {brl(extra_mensal)} por mês leva o fator R a {pct(minimo, 0)} e o DAS cai de "
        f"{brl(das_v)} para {brl(das_iii)} por ano. O INSS do sócio sobre o acréscimo custa cerca de "
        f"{brl(inss_extra)} por ano (supondo um sócio, antes do IRPF)."
    )
    if ganho > 0:
        return Aviso(
            codigo="fator_r_abaixo",
            gravidade="oportunidade",
            titulo=f"Fator R de {pct(r)}: o cliente paga pelo Anexo V",
            detalhe=f"{resumo} Ganho líquido estimado: {brl(ganho)} por ano.",
            valor=arredondar(ganho),
            base_legal=simples.BASE_LEGAL_FATOR_R,
        )
    return Aviso(
        codigo="fator_r_abaixo",
        gravidade="info",
        titulo=f"Fator R de {pct(r)}: Anexo V, e aumentar o pró-labore não compensa",
        detalhe=f"{resumo} O custo do INSS supera a redução do DAS.",
        valor=ZERO,
        base_legal=simples.BASE_LEGAL_FATOR_R,
    )


# --- Limites de receita ------------------------------------------------------------------------
def _faixa_de_risco(razao: Decimal) -> str | None:
    if razao > 1:
        return "critico"
    if razao >= LIMIAR_CRITICO:
        return "critico"
    if razao >= LIMIAR_ATENCAO:
        return "atencao"
    return None


def _nota_limite_mei_futuro(data: date) -> str:
    """Quando o limite do MEI do ano seguinte é maior (LC 238/2026), avisa que a ampliação não alcança o ano em curso."""
    proximo, atual = limite_mei(date(data.year + 1, 1, 1)), limite_mei(data)
    if proximo <= atual:
        return ""
    return f" A LC 238/2026 sobe o limite para {brl(proximo)} em {data.year + 1}, mas isso não vale para {data.year}."


def avaliar_limites(rbt12: Numero, regime: str | None, data: date, fonte: str = "") -> list[Aviso]:
    """Avisos de limite para a receita dos últimos 12 meses (``rbt12``) conforme o regime atual do cliente."""
    rbt12 = D(rbt12)
    if rbt12 <= 0:
        return []
    de = f" ({fonte})" if fonte else ""
    avisos: list[Aviso] = []

    if regime == "mei":
        limite_anual = limite_mei(data)
        futuro = _nota_limite_mei_futuro(data)
        razao = rbt12 / limite_anual
        teto_tolerado = limite_anual * (1 + TOLERANCIA_EXCESSO)
        if rbt12 > teto_tolerado:
            avisos.append(Aviso(
                "mei_limite", "critico", f"Receita de {brl(rbt12)} passou de {brl(teto_tolerado)}: MEI desenquadrado",
                f"Acima de {brl(teto_tolerado)} (20% sobre o limite de {brl(limite_anual)}) o desenquadramento "
                f"vale desde 1º de janeiro{de}. É preciso migrar para o Simples Nacional.{futuro}", None, BASE_LEGAL_MEI))
        elif rbt12 > limite_anual:
            avisos.append(Aviso(
                "mei_limite", "critico", f"Receita de {brl(rbt12)} acima do limite do MEI ({brl(limite_anual)})",
                f"Excesso de até 20% (até {brl(teto_tolerado)}): o desenquadramento vale a partir de janeiro do ano "
                f"seguinte e o excesso é tributado pelas regras do Simples. Acima disso, é retroativo{de}.{futuro}",
                None, BASE_LEGAL_MEI))
        elif (g := _faixa_de_risco(razao)) is not None:
            avisos.append(Aviso(
                "mei_limite", g, f"Receita em {pct(razao, 0)} do limite do MEI",
                f"{brl(rbt12)} de {brl(limite_anual)}{de}. Planeje a migração para o Simples antes de passar do limite.{futuro}",
                None, BASE_LEGAL_MEI))

    elif regime == "simples":
        tab = tabelas.vigente("simples_nacional", data)
        sublimite, limite = D(tab["sublimite_icms_iss"]), D(tab["limite_receita_anual"])
        tolerado = limite * (1 + TOLERANCIA_EXCESSO)
        if rbt12 > limite:
            avisos.append(Aviso(
                "simples_limite", "critico", f"Receita de {brl(rbt12)} acima do limite do Simples ({brl(limite)})",
                f"Excesso de até 20% (até {brl(tolerado)}): a exclusão vale a partir de janeiro do ano seguinte; "
                f"acima disso, é retroativa{de}. Avalie o Lucro Presumido ou Real.", None, BASE_LEGAL_LIMITES))
        elif (g := _faixa_de_risco(rbt12 / limite)) is not None:
            avisos.append(Aviso(
                "simples_limite", g, f"Receita em {pct(rbt12 / limite, 0)} do limite do Simples",
                f"{brl(rbt12)} de {brl(limite)}{de}. Ao passar, o cliente é excluído do Simples; compare com o "
                "Lucro Presumido antes.", None, BASE_LEGAL_LIMITES))
        if rbt12 > sublimite:
            avisos.append(Aviso(
                "simples_sublimite", "atencao", f"Receita acima do sublimite de {brl(sublimite)}",
                f"ICMS e ISS passam a ser recolhidos fora do DAS{de}; o DAS fica menor e o custo total precisa ser "
                "reavaliado.", None, BASE_LEGAL_LIMITES))
        elif (g := _faixa_de_risco(rbt12 / sublimite)) is not None:
            avisos.append(Aviso(
                "simples_sublimite", "atencao" if g == "critico" else g,
                f"Receita em {pct(rbt12 / sublimite, 0)} do sublimite do Simples",
                f"{brl(rbt12)} de {brl(sublimite)}{de}. Acima do sublimite, ICMS e ISS saem do DAS.",
                None, BASE_LEGAL_LIMITES))

    elif regime == "presumido":
        tab = tabelas.vigente("lucro_presumido", data)
        lc224 = tab.get("lc224")
        if lc224:
            isenta = D(lc224["receita_anual_isenta"])
            acrescimo = pct(D(lc224["acrescimo_relativo"]), 0)
            if rbt12 > isenta:
                avisos.append(Aviso(
                    "presumido_lc224", "atencao", f"Receita acima de {brl(isenta)}: presunção com acréscimo de {acrescimo}",
                    f"A parcela da receita acima de {brl(isenta)} tem o percentual de presunção acrescido de {acrescimo} "
                    f"(IRPJ e CSLL){de}. Reavalie Lucro Real e Simples.", None, BASE_LEGAL_LC224))
            elif (g := _faixa_de_risco(rbt12 / isenta)) is not None:
                avisos.append(Aviso(
                    "presumido_lc224", "atencao", f"Receita em {pct(rbt12 / isenta, 0)} de {brl(isenta)}",
                    f"{brl(rbt12)}{de}. Acima de {brl(isenta)}, a presunção do Presumido ganha acréscimo de {acrescimo} "
                    "sobre o excedente.", None, BASE_LEGAL_LC224))
        limite = D(tab["limite_receita_anual"])
        if rbt12 > limite:
            avisos.append(Aviso(
                "presumido_limite", "critico", f"Receita acima do limite do Lucro Presumido ({brl(limite)})",
                f"Acima desse valor o Lucro Real é obrigatório{de}.", None, BASE_LEGAL_PRESUMIDO))
        elif (g := _faixa_de_risco(rbt12 / limite)) is not None:
            avisos.append(Aviso(
                "presumido_limite", g, f"Receita em {pct(rbt12 / limite, 0)} do limite do Lucro Presumido",
                f"{brl(rbt12)} de {brl(limite)}{de}. Acima do limite, o Lucro Real é obrigatório.",
                None, BASE_LEGAL_PRESUMIDO))

    return avisos
