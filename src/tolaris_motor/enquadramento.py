"""Enquadramento no Simples: caminhos para sair do Anexo V (ou chegar ao Anexo III) e o que cada um muda no imposto.

Para uma empresa de serviços do fator R, o Anexo V (a partir de 15,5%) é o resultado de uma folha abaixo de 28% da receita.
Há dois caminhos legítimos para o Anexo III (a partir de 6%): elevar a folha (pró-labore) até o fator R chegar a 28%, ou exercer
de fato uma atividade que tributa direto no Anexo III e ter o CNAE dela no cadastro. O motor só calcula o efeito de cada
caminho; se o segundo é possível depende do que a empresa realmente faz, o que é decisão do contador.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from . import pessoa_fisica, simples
from .base import ZERO, D, Numero, brl
from .comparativo import Comparativo, comparar
from .empresa import Atividade, PerfilEmpresa

PERCENTUAIS_PADRAO = (Decimal("0.25"), Decimal("0.50"), Decimal("1"))
"""Parcelas da receita em atividade do Anexo III simuladas quando o contador não informa a sua."""


@dataclass
class Cenario:
    chave: str
    descricao: str
    perfil: PerfilEmpresa
    comparativo: Comparativo
    custo_extra_anual: Decimal = ZERO
    """Custo que o regime não mostra (INSS de 11% do sócio sobre o pró-labore adicional)."""
    observacao: str = ""
    anexos_simples: list[str] = field(default_factory=list)

    @property
    def melhor_total(self) -> Decimal:
        return self.comparativo.melhor.total + self.custo_extra_anual


def _anexos_usados(c: Comparativo) -> list[str]:
    simples_res = next(r for r in c.resultados if r.titulo.startswith("Simples"))
    if not simples_res.aplicavel:
        return []
    achados = [m.group(1) for p in simples_res.memoria if (m := re.match(r"Alíquota efetiva - Anexo (\w+),", p.descricao))]
    return list(dict.fromkeys(achados))


def _cenario(chave: str, descricao: str, perfil: PerfilEmpresa, custo: Decimal = ZERO, obs: str = "") -> Cenario:
    c = comparar(perfil)
    return Cenario(chave, descricao, perfil, c, custo, obs, _anexos_usados(c))


def analisar(perfil: PerfilEmpresa, percentual_personalizado: Numero | None = None) -> list[Cenario]:
    """Cenário atual e as alternativas. ``perfil`` deve descrever a empresa como ela é hoje."""
    data = date(perfil.ano, 1, 1)
    base = replace(perfil, receita_anexo_iii_anual=ZERO)
    cenarios = [_cenario("atual", "Como está hoje", base)]
    if base.atividade is not Atividade.SERVICO_FATOR_R:
        return cenarios

    minimo = D(simples._tabela(data)["fator_r_minimo"])
    folha = simples.folha_fator_r(base)
    r_atual = simples.fator_r(folha, base.receita_bruta_anual)
    if r_atual >= minimo:
        cenarios[0].observacao = "O fator R já chega a 28%: a atividade já tributa no Anexo III."
        return cenarios

    # Caminho 1: pró-labore até o fator R chegar a 28%
    falta_anual = max(ZERO, base.receita_bruta_anual * minimo - folha)
    extra_mensal = falta_anual / 12
    pro_labore_novo = base.pro_labore_anual + falta_anual
    perfil_fr = replace(
        base,
        pro_labore_anual=pro_labore_novo,
        folha_fator_r_anual=(base.folha_fator_r_anual + falta_anual) if base.folha_fator_r_anual is not None else None,
    )
    inss_antes = pessoa_fisica.inss_contribuinte_individual(base.pro_labore_anual / 12, data)
    inss_depois = pessoa_fisica.inss_contribuinte_individual(pro_labore_novo / 12, data)
    custo = (inss_depois - inss_antes) * 12
    cenarios.append(
        _cenario(
            "fator_r",
            f"Pró-labore +{brl(extra_mensal)}/mês (fator R de 28%)",
            perfil_fr,
            custo,
            f"Soma o INSS de 11% do sócio sobre o pró-labore a mais ({brl(custo)}/ano). O IRRF do sócio não entra; "
            "a retirada total pode continuar a mesma, só a parte em lucros diminui.",
        )
    )

    # Caminho 2: parte da receita em atividade do Anexo III
    percentuais = list(PERCENTUAIS_PADRAO)
    if percentual_personalizado is not None:
        p = D(percentual_personalizado)
        if 0 < p <= 1 and p not in percentuais:
            percentuais.append(p)
    for p in sorted(percentuais):
        parte = (base.receita_bruta_anual * p).quantize(Decimal("0.01"))
        cenarios.append(
            _cenario(
                f"anexo_iii_{int(p * 100)}",
                f"{int(p * 100)}% da receita em atividade do Anexo III ({brl(parte)})",
                replace(base, receita_anexo_iii_anual=parte),
                ZERO,
                "Só vale se a empresa passar a exercer essa atividade de verdade e emitir nota com ela.",
            )
        )
    return cenarios


def recomendado(cenarios: list[Cenario]) -> Cenario:
    """Cenário de menor custo total (imposto do melhor regime + custo extra)."""
    return min(cenarios, key=lambda c: c.melhor_total)
