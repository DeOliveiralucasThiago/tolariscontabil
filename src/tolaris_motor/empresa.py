"""Perfil da empresa (entrada comum aos regimes) e encargos sobre a folha."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .base import ZERO, D, Numero, Resultado, brl, pct


class Atividade(str, Enum):
    COMERCIO = "comercio"
    INDUSTRIA = "industria"
    SERVICO_ANEXO_III = "servico_anexo_iii"
    """Serviços sempre no Anexo III (ex.: academias, agências de viagem, escritórios contábeis)."""
    SERVICO_ANEXO_IV = "servico_anexo_iv"
    """Construção civil, vigilância, limpeza, advocacia: CPP recolhida fora do DAS."""
    SERVICO_FATOR_R = "servico_fator_r"
    """Serviços intelectuais/técnicos: Anexo III se fator R >= 28%, senão Anexo V."""

    @property
    def vende_mercadoria(self) -> bool:
        return self in (Atividade.COMERCIO, Atividade.INDUSTRIA)


PRESUNCAO_PADRAO = {
    Atividade.COMERCIO: "comercio",
    Atividade.INDUSTRIA: "industria",
    Atividade.SERVICO_ANEXO_III: "servicos_gerais",
    Atividade.SERVICO_ANEXO_IV: "servicos_gerais",
    Atividade.SERVICO_FATOR_R: "servicos_gerais",
}

ALIQUOTA_FGTS = D("0.08")
ALIQUOTA_CPP = D("0.20")


@dataclass
class PerfilEmpresa:
    """Dados anuais da empresa. Valores em R$ por ano-calendário.

    - ``folha_clt_anual``: salários brutos de empregados (sem encargos).
    - ``pro_labore_anual``: retiradas de pró-labore dos sócios.
    - ``compras_anual``: mercadorias e insumos (custo; gera crédito de ICMS e de
      PIS/Cofins não cumulativos). Assume-se que tudo o que é comprado é vendido
      no ano (sem variação de estoque).
    - ``despesas_creditaveis_anual``: despesas que dão crédito de PIS/Cofins no
      Lucro Real (energia, aluguel pago a PJ, depreciação etc.).
    - ``outras_despesas_anual``: demais despesas dedutíveis, sem crédito.
    """

    atividade: Atividade
    receita_bruta_anual: Numero
    folha_clt_anual: Numero = 0
    pro_labore_anual: Numero = 0
    compras_anual: Numero = 0
    despesas_creditaveis_anual: Numero = 0
    outras_despesas_anual: Numero = 0
    aliquota_iss: Numero = "0.05"
    aliquota_icms: Numero = "0.18"
    aliquota_icms_credito: Numero | None = None
    rat: Numero = "0.02"
    """RAT/SAT ajustado pelo FAP (1% a 3% x FAP). Padrão 2%."""
    terceiros: Numero = "0.058"
    """Outras entidades (Sistema S, salário-educação, INCRA). Padrão 5,8%."""
    presuncao: str | None = None
    """Chave de ``lucro_presumido.json/presuncoes``; padrão conforme a atividade."""
    folha_fator_r_anual: Numero | None = None
    """Folha para o fator R, se o contador já tiver o valor apurado."""
    receita_exterior_anual: Numero = 0
    """Parte de ``receita_bruta_anual`` que é exportação (de serviços ou de mercadorias), já em reais."""
    variacao_cambial_anual: Numero = 0
    """Variação cambial líquida do ano (ativa - passiva), em reais; negativa quando houve perda."""
    receita_anexo_iii_anual: Numero = 0
    """Parte de ``receita_bruta_anual`` de uma atividade que tributa direto no Anexo III (CNAE realmente exercido),
    para empresa cuja atividade principal é do fator R. Só afeta o Simples Nacional."""
    sociedade_profissionais: bool = False
    """Sociedade uniprofissional (advocacia, contabilidade, medicina etc.) que paga ISS fixo por profissional no Lucro Presumido e no
    Lucro Real. No Simples Nacional o ISS segue a receita, dentro do DAS."""
    profissionais: int = 0
    """Quantidade de profissionais habilitados da sociedade, para o ISS fixo."""
    iss_fixo_por_profissional_anual: Numero = 0
    """ISS fixo anual de cada profissional, conforme a lei do município (Decreto-Lei 406/1968, art. 9º, §§ 1º e 3º)."""
    iss_fixo_no_simples: bool = False
    """Escritório de serviços contábeis que recolhe o ISS em valor fixo ao Município também como optante do Simples (LC 123/2006,
    art. 18, § 22-A; Res. CGSN 140/2018, art. 34): o DAS (Anexo III) deixa de incluir a parcela do ISS. Exige ``sociedade_profissionais``."""
    servicos_hospitalares: bool = False
    """Serviços hospitalares (e afins) com a presunção reduzida do Lucro Presumido: IRPJ 8% e CSLL 12%."""
    ano: int = 2026

    def __post_init__(self) -> None:
        self.atividade = Atividade(self.atividade)
        for campo in (
            "receita_bruta_anual",
            "folha_clt_anual",
            "pro_labore_anual",
            "compras_anual",
            "despesas_creditaveis_anual",
            "outras_despesas_anual",
            "aliquota_iss",
            "aliquota_icms",
            "rat",
            "terceiros",
        ):
            valor = D(getattr(self, campo))
            if valor < 0:
                raise ValueError(f"{campo} não pode ser negativo")
            setattr(self, campo, valor)
        self.aliquota_icms_credito = (
            self.aliquota_icms if self.aliquota_icms_credito is None else D(self.aliquota_icms_credito)
        )
        if self.folha_fator_r_anual is not None:
            self.folha_fator_r_anual = D(self.folha_fator_r_anual)
        self.receita_exterior_anual = D(self.receita_exterior_anual)
        self.variacao_cambial_anual = D(self.variacao_cambial_anual)
        if self.receita_exterior_anual < 0:
            raise ValueError("receita_exterior_anual não pode ser negativo")
        if self.receita_exterior_anual > self.receita_bruta_anual:
            raise ValueError("receita_exterior_anual não pode passar da receita bruta anual")
        self.receita_anexo_iii_anual = D(self.receita_anexo_iii_anual)
        if self.receita_anexo_iii_anual < 0:
            raise ValueError("receita_anexo_iii_anual não pode ser negativo")
        if self.receita_anexo_iii_anual > self.receita_bruta_anual:
            raise ValueError("receita_anexo_iii_anual não pode passar da receita bruta anual")
        if self.receita_anexo_iii_anual and self.atividade is not Atividade.SERVICO_FATOR_R:
            raise ValueError("A receita separada do Anexo III só se aplica a quem tem atividade principal do fator R")
        self.iss_fixo_por_profissional_anual = D(self.iss_fixo_por_profissional_anual)
        if self.iss_fixo_por_profissional_anual < 0 or self.profissionais < 0:
            raise ValueError("profissionais e iss_fixo_por_profissional_anual não podem ser negativos")
        if self.sociedade_profissionais:
            if self.atividade.vende_mercadoria:
                raise ValueError("ISS fixo de sociedade de profissionais só se aplica a serviços")
            if self.profissionais < 1 or self.iss_fixo_por_profissional_anual <= 0:
                raise ValueError("Informe a quantidade de profissionais e o ISS fixo anual de cada um")
        if self.iss_fixo_no_simples and not (self.sociedade_profissionais and self.atividade is Atividade.SERVICO_ANEXO_III):
            raise ValueError("O ISS fixo no Simples é do escritório de serviços contábeis (Anexo III) e exige a sociedade de profissionais com ISS fixo")
        if self.servicos_hospitalares and self.atividade.vende_mercadoria:
            raise ValueError("A presunção de serviços hospitalares só se aplica a serviços")
        if self.presuncao is None:
            self.presuncao = "servicos_hospitalares" if self.servicos_hospitalares else PRESUNCAO_PADRAO[self.atividade]

    @property
    def fgts_anual(self) -> Decimal:
        return self.folha_clt_anual * ALIQUOTA_FGTS

    @property
    def iss_fixo_anual(self) -> Decimal:
        """ISS fixo anual total da sociedade de profissionais (zero quando não se aplica)."""
        if not self.sociedade_profissionais:
            return ZERO
        return Decimal(self.profissionais) * self.iss_fixo_por_profissional_anual

    @property
    def receita_interna_anual(self) -> Decimal:
        """Receita do mercado interno: a que paga ISS/ICMS e PIS/Cofins."""
        return self.receita_bruta_anual - self.receita_exterior_anual


def icms_liquido(perfil: PerfilEmpresa, res: Resultado) -> Decimal:
    """ICMS não cumulativo (débito nas saídas - crédito nas compras), igual no Presumido e no Real."""
    debito = res.passo(
        "ICMS - débito nas vendas",
        f"{brl(perfil.receita_interna_anual)} x {pct(perfil.aliquota_icms)}",
        perfil.receita_interna_anual * perfil.aliquota_icms,
        "LC 87/1996 e legislação estadual (exportação: CF, art. 155, §2º, X, a)" if perfil.receita_exterior_anual else "LC 87/1996 e legislação estadual",
    )
    credito = res.passo(
        "ICMS - crédito nas compras",
        f"{brl(perfil.compras_anual)} x {pct(perfil.aliquota_icms_credito)}",
        perfil.compras_anual * perfil.aliquota_icms_credito,
        "LC 87/1996, art. 20 (não cumulatividade)",
    )
    if credito > debito:
        res.alerta("Créditos de ICMS superam os débitos: saldo credor acumulado não entra no total.")
    return res.passo("ICMS a recolher", "máx(0; débito - crédito)", max(ZERO, debito - credito))


def tributo_sobre_receita_local(perfil: PerfilEmpresa, res: Resultado) -> None:
    """Lança ICMS (mercadorias) ou ISS (serviços) no resultado do regime normal."""
    if perfil.atividade.vende_mercadoria:
        res.tributos["ICMS"] = icms_liquido(perfil, res)
    elif perfil.sociedade_profissionais:
        res.tributos["ISS"] = res.passo(
            "ISS fixo da sociedade de profissionais",
            f"{perfil.profissionais} profissional(is) x {brl(perfil.iss_fixo_por_profissional_anual)}/ano",
            perfil.iss_fixo_anual,
            "Decreto-Lei 406/1968, art. 9º, §§ 1º e 3º, e lei municipal",
        )
        res.alerta(
            "ISS fixo: vale para a sociedade uniprofissional que atende às condições da lei do município (profissionais habilitados, "
            "responsabilidade pessoal e sem caráter empresarial), e o valor anual por profissional é o do município. Confirme o enquadramento "
            "e o valor com a prefeitura. O ISS fixo é devido mesmo que a receita varie."
        )
    else:
        res.tributos["ISS"] = res.passo(
            "ISS",
            f"{brl(perfil.receita_interna_anual)} x {pct(perfil.aliquota_iss)}",
            perfil.receita_interna_anual * perfil.aliquota_iss,
            "LC 116/2003, art. 2º, I (exportação não paga ISS) e lei municipal" if perfil.receita_exterior_anual else "LC 116/2003 e lei municipal",
        )


def inss_patronal_regime_normal(perfil: PerfilEmpresa, res: Resultado) -> Decimal:
    """CPP + RAT + terceiros sobre a folha CLT e CPP de 20% sobre o pró-labore."""
    aliq_folha = ALIQUOTA_CPP + perfil.rat + perfil.terceiros
    sobre_folha = res.passo(
        "INSS patronal sobre a folha CLT",
        f"{brl(perfil.folha_clt_anual)} x ({pct(ALIQUOTA_CPP)} CPP + {pct(perfil.rat)} RAT + "
        f"{pct(perfil.terceiros)} terceiros)",
        perfil.folha_clt_anual * aliq_folha,
        "Lei 8.212/1991, art. 22, I e II",
    )
    sobre_pl = res.passo(
        "INSS patronal sobre o pró-labore",
        f"{brl(perfil.pro_labore_anual)} x {pct(ALIQUOTA_CPP)}",
        perfil.pro_labore_anual * ALIQUOTA_CPP,
        "Lei 8.212/1991, art. 22, III",
    )
    return sobre_folha + sobre_pl
