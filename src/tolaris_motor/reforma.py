"""Simulador da transição da Reforma Tributária (2025-2033) para empresas do regime regular.

Modelo (premissas também registradas na memória de cálculo):

- O valor das vendas SEM tributos sobre consumo é mantido constante em todos os anos
  (``base_venda`` = receita bruta atual menos PIS/Cofins, ICMS e ISS embutidos no preço).
- IBS e CBS são calculados "por fora" sobre essa base, com crédito sobre as compras
  e despesas informadas (crédito amplo), também desembutidas dos tributos atuais
  (``tributos_embutidos_compras``). ``fracao_credito_compras`` < 1 representa
  fornecedores que geram crédito parcial (ex.: optantes do Simples que recolhem IBS/CBS no DAS).
- Os tributos antigos seguem a regra atual, multiplicados pelo fator de transição do ano.
- 2026 é ano-teste: CBS 0,9% e IBS 0,1% são dispensados para quem cumpre as obrigações
  acessórias (LC 214/2025, art. 348), então aparecem só como informação.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import tabelas
from .base import ZERO, D, Numero, Resultado, brl, pct

PIS_COFINS_CUMULATIVO = D("0.0365")
PIS_COFINS_NAO_CUMULATIVO = D("0.0925")
BASE_LEGAL = "EC 132/2023 (ADCT, arts. 125 a 133); LC 214/2025"
ALERTA_ISS_FIXO = (
    "ISS fixo da sociedade uniprofissional na transição: a LC 214/2025 (lida na versão atualizada até a LC 227/2026) não traz regra própria para o ISS "
    "fixo. O Tolaris aplica a ele a redução gradual do ISS de 2029 a 2032 (LC 116/2003, art. 8º-B, incluído pelo art. 508 da LC 214, cujo § 1º reduz os "
    "benefícios na mesma proporção das alíquotas) e o zera em 2033, quando o Decreto-Lei 406/1968 é revogado (LC 214, art. 543, I). É uma leitura, não "
    "uma regra expressa: confirme com o contador e com a lei do município."
)


@dataclass
class EntradaReforma:
    receita_bruta_anual: Numero
    vende_mercadoria: bool
    pis_cofins_nao_cumulativo: bool = False
    """True para Lucro Real; False para Lucro Presumido."""
    compras_anual: Numero = 0
    """Bens e serviços adquiridos que geram crédito (mercadorias, insumos)."""
    despesas_creditaveis_anual: Numero = 0
    """Outras aquisições de PJ: no modelo novo quase tudo dá crédito (energia, aluguel, serviços...)."""
    aliquota_icms: Numero = "0.18"
    aliquota_icms_credito: Numero | None = None
    aliquota_iss: Numero = "0.05"
    aliquota_ipi: Numero = 0
    iss_fixo_anual: Numero = 0
    """ISS fixo anual total da sociedade uniprofissional (DL 406/1968, art. 9º, §§ 1º e 3º); substitui ``aliquota_iss`` nos serviços."""
    reducao_setorial: Numero = 0
    """0 (padrão), 0.3 (profissões regulamentadas), 0.6 (saúde, educação...) ou 1 (alíquota zero)."""
    fracao_credito_compras: Numero = 1
    tributos_embutidos_compras: Numero | None = None
    """Fração de tributos atuais embutida no preço das compras, removida para achar a base de
    crédito do IBS/CBS. Padrão: ICMS de crédito + 9,25% (mercadorias) ou 9,25% (serviços)."""
    cbs_referencia: Numero | None = None
    ibs_referencia: Numero | None = None
    anos: list[int] = field(default_factory=lambda: list(range(2025, 2034)))

    def __post_init__(self) -> None:
        estimadas = tabelas.carregar("reforma_tributaria")["aliquotas_referencia_estimadas"]
        self.receita_bruta_anual = D(self.receita_bruta_anual)
        self.compras_anual = D(self.compras_anual)
        self.despesas_creditaveis_anual = D(self.despesas_creditaveis_anual)
        self.aliquota_icms = D(self.aliquota_icms)
        self.aliquota_icms_credito = (
            self.aliquota_icms if self.aliquota_icms_credito is None else D(self.aliquota_icms_credito)
        )
        self.aliquota_iss = D(self.aliquota_iss)
        self.aliquota_ipi = D(self.aliquota_ipi)
        self.iss_fixo_anual = D(self.iss_fixo_anual)
        if self.iss_fixo_anual < 0:
            raise ValueError("iss_fixo_anual não pode ser negativo")
        if self.iss_fixo_anual and self.vende_mercadoria:
            raise ValueError("O ISS fixo de sociedade uniprofissional só se aplica a serviços")
        self.reducao_setorial = D(self.reducao_setorial)
        self.fracao_credito_compras = D(self.fracao_credito_compras)
        if self.tributos_embutidos_compras is None:
            embutido = PIS_COFINS_NAO_CUMULATIVO
            if self.vende_mercadoria:
                embutido += self.aliquota_icms_credito
            self.tributos_embutidos_compras = embutido
        self.tributos_embutidos_compras = D(self.tributos_embutidos_compras)
        self.cbs_referencia = D(self.cbs_referencia if self.cbs_referencia is not None else estimadas["cbs"])
        self.ibs_referencia = D(self.ibs_referencia if self.ibs_referencia is not None else estimadas["ibs"])
        if not (0 <= self.reducao_setorial <= 1):
            raise ValueError("reducao_setorial deve estar entre 0 e 1")


@dataclass
class AnoReforma:
    ano: int
    resultado: Resultado
    base_venda: Decimal

    @property
    def total(self) -> Decimal:
        return self.resultado.total

    @property
    def carga_sobre_base(self) -> Decimal:
        return self.total / self.base_venda if self.base_venda else ZERO


def base_venda_sem_tributos(e: EntradaReforma) -> Decimal:
    """Receita bruta menos PIS/Cofins e ICMS/ISS embutidos (alíquotas nominais)."""
    pis_cofins = PIS_COFINS_NAO_CUMULATIVO if e.pis_cofins_nao_cumulativo else PIS_COFINS_CUMULATIVO
    local = e.aliquota_icms if e.vende_mercadoria else aliquota_iss_efetiva(e)
    return e.receita_bruta_anual * (1 - pis_cofins - local)


def aliquota_iss_efetiva(e: EntradaReforma) -> Decimal:
    """ISS como fração da receita: a alíquota do município ou, no ISS fixo, o valor fixo dividido pela receita."""
    if e.iss_fixo_anual and e.receita_bruta_anual > 0:
        return e.iss_fixo_anual / e.receita_bruta_anual
    return e.aliquota_iss


def base_credito_sem_tributos(e: EntradaReforma) -> Decimal:
    """Compras e despesas creditáveis sem os tributos atuais, ajustadas pela fração de crédito."""
    aquisicoes = e.compras_anual + e.despesas_creditaveis_anual
    return aquisicoes * (1 - e.tributos_embutidos_compras) * e.fracao_credito_compras


def aliquotas_novas(e: EntradaReforma, cfg: dict) -> list[tuple[str, Decimal, Decimal]]:
    """CBS e IBS do ano: (nome, alíquota de venda já com a redução setorial, alíquota de crédito)."""
    fator_setor = 1 - e.reducao_setorial
    novos: list[tuple[str, Decimal, Decimal]] = []
    if cfg["cbs"] == "fixo":
        novos.append(("CBS", D(cfg["cbs_fixo"]) * fator_setor, D(cfg["cbs_fixo"])))
    elif cfg["cbs"] == "ref":
        cheia = e.cbs_referencia - D(cfg["cbs_reducao_pp"])
        novos.append(("CBS", cheia * fator_setor, cheia))
    ibs_cheia = D(cfg["ibs_fixo"]) + e.ibs_referencia * D(cfg["ibs_fracao"])
    if ibs_cheia:
        novos.append(("IBS", ibs_cheia * fator_setor, ibs_cheia))
    return novos


def _ano(e: EntradaReforma, ano: int, base_venda: Decimal) -> AnoReforma:
    cfg = tabelas.carregar("reforma_tributaria")["anos"][str(ano)]
    res = Resultado(f"Tributos sobre consumo em {ano}")
    receita = e.receita_bruta_anual
    base_credito = base_credito_sem_tributos(e)

    f_pc = D(cfg["pis_cofins"])
    if f_pc:
        if e.pis_cofins_nao_cumulativo:
            debito = receita * PIS_COFINS_NAO_CUMULATIVO
            credito = (e.compras_anual + e.despesas_creditaveis_anual) * PIS_COFINS_NAO_CUMULATIVO
            valor = max(ZERO, debito - credito) * f_pc
            formula = f"máx(0; ({brl(receita)} - {brl(e.compras_anual + e.despesas_creditaveis_anual)}) x 9,25%)"
        else:
            valor = receita * PIS_COFINS_CUMULATIVO * f_pc
            formula = f"{brl(receita)} x 3,65%"
        res.tributos["PIS/Cofins"] = res.passo("PIS/Cofins", formula, valor)

    f_ipi = D(cfg["ipi"])
    if f_ipi and e.aliquota_ipi:
        res.tributos["IPI"] = res.passo("IPI", f"{brl(receita)} x {pct(e.aliquota_ipi)}", receita * e.aliquota_ipi)

    f_local = D(cfg["icms_iss"])
    if f_local:
        if e.vende_mercadoria:
            liquido = max(ZERO, receita * e.aliquota_icms - e.compras_anual * e.aliquota_icms_credito)
            res.tributos["ICMS"] = res.passo(
                "ICMS",
                f"(débito {brl(receita * e.aliquota_icms)} - crédito "
                f"{brl(e.compras_anual * e.aliquota_icms_credito)}) x {pct(f_local, 0)} da alíquota",
                liquido * f_local,
                "EC 132/2023, ADCT art. 128",
            )
        elif e.iss_fixo_anual:
            res.tributos["ISS"] = res.passo(
                "ISS fixo da sociedade uniprofissional",
                f"{brl(e.iss_fixo_anual)} x {pct(f_local, 0)} (redução gradual do ISS)",
                e.iss_fixo_anual * f_local,
                "DL 406/1968, art. 9º; LC 116/2003, art. 8º-B (LC 214/2025, art. 508); EC 132/2023, ADCT art. 128",
            )
        else:
            res.tributos["ISS"] = res.passo(
                "ISS",
                f"{brl(receita)} x {pct(e.aliquota_iss)} x {pct(f_local, 0)} da alíquota",
                receita * e.aliquota_iss * f_local,
                "EC 132/2023, ADCT art. 128; LC 116/2003, art. 8º-B",
            )

    novos = aliquotas_novas(e, cfg)

    for nome, aliq_venda, aliq_credito in novos:
        debito = base_venda * aliq_venda
        credito = base_credito * aliq_credito
        valor = max(ZERO, debito - credito)
        formula = (
            f"{brl(base_venda)} x {pct(aliq_venda, 3)} - crédito {brl(base_credito)} x {pct(aliq_credito, 3)}"
        )
        if credito > debito:
            res.alerta(f"{nome}: créditos superam débitos em {brl(credito - debito)} (saldo credor ressarcível).")
        if cfg["compensavel"]:
            res.passo(f"{nome} (ano-teste, dispensado/compensável — não somado)", formula, valor, "LC 214/2025, art. 348")
        else:
            res.tributos[nome] = res.passo(nome, formula, valor, BASE_LEGAL)

    return AnoReforma(ano, res, base_venda)


def simular(e: EntradaReforma) -> list[AnoReforma]:
    base_venda = base_venda_sem_tributos(e)
    anos = [_ano(e, ano, base_venda) for ano in e.anos]
    if anos:
        anos[0].resultado.alerta(
            f"Premissas: vendas sem tributos mantidas em {brl(base_venda)}/ano e aquisições com crédito "
            f"em {brl(base_credito_sem_tributos(e))}/ano; alíquotas de "
            f"referência CBS {pct(e.cbs_referencia, 1)} e IBS {pct(e.ibs_referencia, 1)} (estimativas — "
            "a de 2027 depende de TCU/Senado); Imposto Seletivo não incluído."
        )
        if e.iss_fixo_anual:
            anos[0].resultado.alerta(ALERTA_ISS_FIXO)
    return anos


def tabela_resumo(anos: list[AnoReforma]) -> str:
    linhas = [f"{'Ano':<6}{'Total':>18}{'Carga s/ base':>16}"]
    for a in anos:
        linhas.append(f"{a.ano:<6}{brl(a.total):>18}{pct(a.carga_sobre_base):>16}")
    return "\n".join(linhas)
