"""Simples Nacional na Reforma: recolher IBS/CBS dentro do DAS ou "por fora" (regime regular)?

A partir de 2027 a empresa do Simples pode recolher IBS/CBS pelo regime regular
(LC 214/2025; LC 123/2006 alterada). A escolha mexe em duas coisas:

- **Clientes empresas (B2B)** só se creditam do IBS/CBS que a empresa pagou. Dentro do DAS,
  o crédito é pequeno (a fatia do DAS que corresponde a esses tributos). Por fora, o crédito
  é integral, o que torna a empresa mais competitiva com quem compra para revender/produzir.
- **Consumidor final (B2C)** não toma crédito: por fora, o IBS/CBS cheio pesa no preço.

Modelo (comparação por real de venda, preços ajustados para o cliente pagar o mesmo custo
líquido nos dois cenários):

- Dentro do DAS: empresa fica com ``1 - e`` (``e`` = alíquota efetiva do DAS). O cliente B2B
  credita ``e * s`` (``s`` = fatia do DAS dos tributos substituídos por IBS/CBS).
- Por fora, venda B2B: para o cliente ter o mesmo custo líquido, o preço sem tributo cai para
  ``1 - e*s``; a empresa paga o DAS sem a fatia ``s`` e repassa o IBS/CBS (neutro).
- Por fora, venda B2C: o consumidor paga o mesmo preço final, então a base cai para
  ``1 / (1 + a)`` (``a`` = IBS/CBS da venda).
- Por fora, a empresa ainda se credita do IBS/CBS das compras.

Em 2027 só a CBS substitui PIS/Cofins (``s`` = PIS + Cofins); em 2033 IBS + CBS substituem
PIS, Cofins, ICMS, ISS e IPI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import simples, tabelas
from .base import ZERO, D, Numero, Resultado, brl, pct
from .empresa import Atividade, PerfilEmpresa

BASE_LEGAL = "LC 214/2025; LC 123/2006 (opção pelo regime regular de IBS/CBS)"
SUBSTITUIDOS = {
    2027: ("pis", "cofins"),
    2033: ("pis", "cofins", "icms", "iss"),
}
"""Tributos que o IBS/CBS substituem dentro do DAS. Conferido com os Anexos I a V da Res. CGSN 190/2026: em cada faixa, CBS + IBS
somam o que PIS, Cofins, ICMS e ISS somavam hoje. O IPI **não** sai: o Anexo II segue com 7,5% de IPI em 2033."""

PRAZOS_OPCAO_2027 = (
    "Prazos de 2026 (Res. CGSN 186/2026, alterada pela 194/2026): a opção pelo regime regular de IBS/CBS para janeiro a junho de "
    "2027 vai de 01/09 a 30/10/2026 e pode ser cancelada, em caráter irretratável, de 03/11 a 20/12/2026; as parcelas de IBS e CBS "
    "deixam de ser devidas no DAS. Empresas inscritas no CNPJ depois de 16/10 (Simples) ou de 31/10 (regime regular) seguem regra "
    "própria."
)


@dataclass
class EntradaSimplesReforma:
    atividade: Atividade
    receita_bruta_anual: Numero
    percentual_b2b: Numero
    """Fração das vendas feitas a empresas que tomam crédito (0 a 1)."""
    compras_creditaveis_anual: Numero = 0
    """Compras de fornecedores do regime regular (geram crédito integral por fora)."""
    folha_fator_r_anual: Numero | None = None
    reducao_setorial: Numero = 0
    cbs_referencia: Numero | None = None
    ibs_referencia: Numero | None = None
    anos: list[int] = field(default_factory=lambda: [2027, 2033])

    def __post_init__(self) -> None:
        estimadas = tabelas.carregar("reforma_tributaria")["aliquotas_referencia_estimadas"]
        self.atividade = Atividade(self.atividade)
        self.receita_bruta_anual = D(self.receita_bruta_anual)
        self.percentual_b2b = D(self.percentual_b2b)
        self.compras_creditaveis_anual = D(self.compras_creditaveis_anual)
        self.reducao_setorial = D(self.reducao_setorial)
        self.cbs_referencia = D(self.cbs_referencia if self.cbs_referencia is not None else estimadas["cbs"])
        self.ibs_referencia = D(self.ibs_referencia if self.ibs_referencia is not None else estimadas["ibs"])
        if not 0 <= self.percentual_b2b <= 1:
            raise ValueError("percentual_b2b deve estar entre 0 e 1")
        if not 0 <= self.reducao_setorial <= 1:
            raise ValueError("reducao_setorial deve estar entre 0 e 1")
        if self.receita_bruta_anual <= 0:
            raise ValueError("receita_bruta_anual deve ser positiva")
        for ano in self.anos:
            if ano not in SUBSTITUIDOS:
                raise ValueError("Anos disponíveis: 2027 e 2033")


@dataclass
class CenarioAno:
    ano: int
    dentro_do_das: Decimal
    """Receita líquida de tributos da empresa recolhendo tudo no DAS (R$/ano)."""
    por_fora: Decimal
    """Receita líquida recolhendo IBS/CBS pelo regime regular (R$/ano)."""
    equilibrio_b2b: Decimal | None
    """% de vendas B2B a partir do qual recolher por fora compensa (None se nunca/sempre)."""
    credito_cliente_dentro: Decimal
    """Crédito que cada R$ 100 vendidos a empresas geram ao cliente, dentro do DAS."""
    credito_cliente_fora: Decimal
    resultado: Resultado

    @property
    def diferenca(self) -> Decimal:
        return self.por_fora - self.dentro_do_das

    @property
    def recomendacao(self) -> str:
        return "Recolher IBS/CBS por fora (regime regular)" if self.diferenca > 0 else "Manter IBS/CBS dentro do DAS"


def _aliquota_venda(e: EntradaSimplesReforma, ano: int) -> tuple[Decimal, Decimal]:
    """(alíquota IBS+CBS na venda com redução setorial, alíquota cheia para crédito nas compras)."""
    cfg = tabelas.carregar("reforma_tributaria")["anos"][str(ano)]
    cbs = e.cbs_referencia - D(cfg["cbs_reducao_pp"])
    ibs = D(cfg["ibs_fixo"]) + e.ibs_referencia * D(cfg["ibs_fracao"])
    cheia = cbs + ibs
    return cheia * (1 - e.reducao_setorial), cheia


def _por_real(e_das: Decimal, s: Decimal, a: Decimal, beta: Decimal) -> tuple[Decimal, Decimal]:
    """Receita líquida por R$ 1 de venda (preço do cenário dentro do DAS): (dentro, por fora sem créditos)."""
    dentro = 1 - e_das
    b2b = (1 - e_das * s) * (1 - e_das * (1 - s))
    b2c = (1 - e_das * (1 - s)) / (1 + a)
    return dentro, beta * b2b + (1 - beta) * b2c


def simular(e: EntradaSimplesReforma) -> list[CenarioAno]:
    perfil = PerfilEmpresa(
        e.atividade,
        e.receita_bruta_anual,
        folha_fator_r_anual=e.folha_fator_r_anual,
        ano=2026,
    )
    data = date(2026, 1, 1)
    anexo = simples.anexo_da_atividade(perfil)
    e_das = simples.aliquota_efetiva(anexo, e.receita_bruta_anual, data)
    fracoes = simples.partilha(anexo, e.receita_bruta_anual, data)
    receita = e.receita_bruta_anual
    cenarios = []

    for ano in e.anos:
        res = Resultado(f"Simples na Reforma — {ano}")
        s = sum((fracoes.get(t, ZERO) for t in SUBSTITUIDOS[ano]), ZERO)
        a, a_cheia = _aliquota_venda(e, ano)
        res.passo(
            f"Anexo {anexo}: alíquota efetiva do DAS",
            f"RBT12 {brl(receita)}",
            e_das,
            simples.BASE_LEGAL_ALIQUOTA,
        )
        res.passo(
            "Alíquota da fatia do DAS substituída por IBS/CBS",
            " + ".join(f"{t.upper()} {pct(fracoes.get(t, ZERO))}" for t in SUBSTITUIDOS[ano] if fracoes.get(t))
            + f" = {pct(s)} do DAS",
            s,
            "LC 123/2006, tabelas de partilha",
        )
        res.passo("Alíquota de IBS/CBS na venda (por fora)", f"com redução setorial de {pct(e.reducao_setorial, 0)}", a, BASE_LEGAL)

        dentro_unit, fora_unit = _por_real(e_das, s, a, e.percentual_b2b)
        dentro = res.passo(
            "Receita líquida — tudo no DAS",
            f"{brl(receita)} x (1 - {pct(e_das)})",
            receita * dentro_unit,
            BASE_LEGAL,
        )
        creditos = e.compras_creditaveis_anual * a_cheia
        res.passo(
            "Crédito de IBS/CBS nas compras (só por fora)",
            f"{brl(e.compras_creditaveis_anual)} x {pct(a_cheia)}",
            creditos,
            BASE_LEGAL,
        )
        fora = res.passo(
            "Receita líquida — IBS/CBS por fora",
            f"{brl(receita)} x [{pct(e.percentual_b2b, 0)} B2B x (1 - e·s)(1 - e·(1-s)) + "
            f"{pct(1 - e.percentual_b2b, 0)} B2C x (1 - e·(1-s)) / (1 + {pct(a)})] + créditos",
            receita * fora_unit + creditos,
            BASE_LEGAL,
        )
        res.tributos["Receita líquida — dentro do DAS"] = dentro
        res.tributos["Receita líquida — por fora"] = fora

        # Ponto de equilíbrio: fora(beta) = dentro, linear em beta
        _, fora_0 = _por_real(e_das, s, a, ZERO)
        _, fora_1 = _por_real(e_das, s, a, D(1))
        cred_unit = creditos / receita
        f0, f1 = fora_0 + cred_unit, fora_1 + cred_unit
        if f1 == f0:
            equilibrio = None
        else:
            beta = (dentro_unit - f0) / (f1 - f0)
            equilibrio = beta if 0 <= beta <= 1 else None
            if beta < 0:
                res.alerta(f"{ano}: recolher por fora compensa mesmo sem vendas a empresas (créditos nas compras altos).")
            elif beta > 1:
                res.alerta(f"{ano}: mesmo vendendo só para empresas, manter no DAS rende mais nestas premissas.")

        if fracoes.get("icms", ZERO) == 0 and fracoes.get("iss", ZERO) == 0 and ano == 2033:
            res.alerta("Receita na 6ª faixa: ICMS/ISS já são recolhidos fora do DAS; a fatia substituída fica subestimada.")
        res.alerta(
            "A fatia de IBS/CBS do DAS foi conferida com os Anexos da Res. CGSN 190/2026 (vigência a partir de 01/01/2027): CBS + IBS "
            "somam o que PIS, Cofins, ICMS e ISS somam hoje, exceto o IPI da indústria, que permanece. A 6ª faixa tem alíquota nominal "
            "um pouco menor em 2027 (Anexo I: 18,90%) e o teto de ISS cai a 4% em 2030; o cálculo usa a tabela de 2026."
        )
        res.alerta(PRAZOS_OPCAO_2027)
        cenarios.append(
            CenarioAno(
                ano=ano,
                dentro_do_das=dentro,
                por_fora=fora,
                equilibrio_b2b=equilibrio,
                credito_cliente_dentro=100 * e_das * s,
                credito_cliente_fora=100 * a,
                resultado=res,
            )
        )
    return cenarios


def curva_b2b(e: EntradaSimplesReforma, ano: int, pontos: int = 11) -> list[tuple[Decimal, Decimal]]:
    """Diferença (por fora - dentro) em R$/ano para % B2B de 0 a 100%."""
    curva = []
    for i in range(pontos):
        beta = D(i) / (pontos - 1)
        copia = EntradaSimplesReforma(
            e.atividade, e.receita_bruta_anual, beta, e.compras_creditaveis_anual, e.folha_fator_r_anual,
            e.reducao_setorial, e.cbs_referencia, e.ibs_referencia, [ano],
        )
        c = simular(copia)[0]
        curva.append((beta, c.diferenca))
    return curva
