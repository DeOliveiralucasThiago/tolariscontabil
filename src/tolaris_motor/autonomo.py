"""Vale abrir CNPJ? Autônomo (carnê-leão) × MEI × Simples Nacional × Lucro Presumido.

Valores mensais, receita constante. Para as opções com CNPJ, o sócio retira pró-labore
(INSS 11% + IRPF) e o restante como lucro isento (até R$ 50 mil/mês por empresa).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import pessoa_fisica as pf
from . import presumido, simples, tabelas
from .base import ZERO, D, Numero, Resultado, arredondar, brl, pct
from .empresa import Atividade, PerfilEmpresa

def limite_mei(data: date) -> Decimal:
    """Limite anual de receita do MEI na data: R$ 81.000 até 2026, R$ 110.000 em 2027 e R$ 140.000 a partir de 2028."""
    return D(tabelas.vigente("mei", data)["limite_receita_anual"])


MEI_INSS = D("0.05")
MEI_ISS = D("5.00")
MEI_ICMS = D("1.00")
INSS_AUTONOMO = D("0.20")


@dataclass
class EntradaAutonomo:
    receita_mensal: Numero
    atividade: Atividade = Atividade.SERVICO_FATOR_R
    despesas_mensais: Numero = 0
    """Despesas da atividade (livro-caixa do autônomo; custo dedutível na empresa)."""
    dependentes: int = 0
    iss_fixo_autonomo_mensal: Numero = 0
    """ISS do autônomo (em geral valor fixo anual definido pelo município), rateado por mês."""
    aliquota_iss: Numero = "0.05"
    mei_permitido: bool = False
    """A ocupação consta da lista do MEI (Resolução CGSN 140/2018, Anexo XI)?"""
    contabilidade_mensal: Numero = 0
    """Honorários contábeis para manter o CNPJ (Simples/Presumido)."""
    data: date = field(default_factory=lambda: date(2026, 1, 1))

    def __post_init__(self) -> None:
        self.atividade = Atividade(self.atividade)
        for campo in ("receita_mensal", "despesas_mensais", "iss_fixo_autonomo_mensal", "aliquota_iss", "contabilidade_mensal"):
            valor = D(getattr(self, campo))
            if valor < 0:
                raise ValueError(f"{campo} não pode ser negativo")
            setattr(self, campo, valor)
        if self.receita_mensal <= 0:
            raise ValueError("receita_mensal deve ser positiva")


@dataclass
class OpcaoAutonomo:
    nome: str
    aplicavel: bool
    tributos_mensais: Decimal
    custos_mensais: Decimal
    liquido_mensal: Decimal
    resultado: Resultado
    detalhe: str = ""

    @property
    def custo_total_mensal(self) -> Decimal:
        return self.tributos_mensais + self.custos_mensais


def _liquido(e: EntradaAutonomo, tributos: Decimal, custos: Decimal) -> Decimal:
    return e.receita_mensal - e.despesas_mensais - tributos - custos


def _autonomo(e: EntradaAutonomo) -> OpcaoAutonomo:
    res = Resultado("Autônomo (pessoa física)")
    teto = D(tabelas.vigente("inss", e.data)["teto"])
    inss = res.passo(
        "INSS contribuinte individual",
        f"20% x mín({brl(e.receita_mensal)}; teto {brl(teto)})",
        arredondar(min(e.receita_mensal, teto) * INSS_AUTONOMO),
        "Lei 8.212/1991, art. 21",
    )
    ir = pf.irpf_mensal(e.receita_mensal, e.data, inss=inss, dependentes=e.dependentes, outras_deducoes=e.despesas_mensais)
    res.memoria.extend(ir.memoria)
    res.tributos["INSS (20%)"] = inss
    res.tributos["IRPF (carnê-leão)"] = ir.tributos["IRPF"]
    if e.iss_fixo_autonomo_mensal:
        res.tributos["ISS do autônomo"] = res.passo("ISS fixo do autônomo", "valor municipal", e.iss_fixo_autonomo_mensal)
    if e.despesas_mensais:
        res.alerta("Livro-caixa só é dedutível para quem recebe de pessoas físicas e escritura as despesas; "
                   "substitui o desconto simplificado quando for maior.")
    res.alerta("Quem presta serviço a empresas tem 11% de INSS retido e a empresa paga mais 20% (custo para o cliente).")
    total = res.total
    return OpcaoAutonomo(res.titulo, True, total, ZERO, _liquido(e, total, ZERO), res)


def _mei(e: EntradaAutonomo) -> OpcaoAutonomo:
    res = Resultado("MEI")
    anual = e.receita_mensal * 12
    sm = pf.salario_minimo(e.data)
    limite = limite_mei(e.data)
    aplicavel = e.mei_permitido and anual <= limite
    if not e.mei_permitido:
        res.alerta("Ocupação fora da lista do MEI (profissões intelectuais regulamentadas, em regra, não podem).")
    if anual > limite:
        res.alerta(f"Receita anual de {brl(anual)} acima do limite do MEI ({brl(limite)}).")
    if not aplicavel:
        res.aplicavel = False
        return OpcaoAutonomo(res.titulo, False, ZERO, ZERO, ZERO, res)
    res.tributos["DAS-MEI (INSS)"] = res.passo("INSS do MEI", f"5% x salário mínimo {brl(sm)}", arredondar(sm * MEI_INSS), "LC 123/2006, art. 18-A")
    if e.atividade.vende_mercadoria:
        res.tributos["DAS-MEI (ICMS)"] = res.passo("ICMS fixo", "valor fixo mensal", MEI_ICMS, "LC 123/2006, art. 18-A, §3º")
    else:
        res.tributos["DAS-MEI (ISS)"] = res.passo("ISS fixo", "valor fixo mensal", MEI_ISS, "LC 123/2006, art. 18-A, §3º")
    res.alerta("O lucro do MEI acima da parcela isenta (receita x 32% em serviços, 8% em comércio, ou o lucro "
               "escriturado) entra na declaração anual de IRPF.")
    total = res.total
    return OpcaoAutonomo(res.titulo, True, total, ZERO, _liquido(e, total, ZERO), res)


def _socio(res: Resultado, pro_labore: Decimal, data: date) -> None:
    inss = pf.inss_contribuinte_individual(pro_labore, data)
    res.tributos["INSS sobre pró-labore (11%)"] = res.passo(
        "INSS do sócio", f"{brl(pro_labore)} x 11%", inss, "Lei 8.212/1991, art. 21"
    )
    ir = pf.irpf_mensal(pro_labore, data, inss=inss)
    res.tributos["IRPF sobre pró-labore"] = ir.tributos["IRPF"]


def _perfil(e: EntradaAutonomo, pro_labore: Decimal) -> PerfilEmpresa:
    return PerfilEmpresa(
        e.atividade,
        e.receita_mensal * 12,
        pro_labore_anual=pro_labore * 12,
        outras_despesas_anual=e.despesas_mensais * 12,
        aliquota_iss=e.aliquota_iss,
        ano=e.data.year,
    )


def _simples(e: EntradaAutonomo) -> OpcaoAutonomo:
    sm = pf.salario_minimo(e.data)
    candidatos = [sm]
    if e.atividade is Atividade.SERVICO_FATOR_R:
        # Pró-labore que leva o fator R a 28% (folha = pró-labore, sem empregados)
        minimo = D(tabelas.vigente("simples_nacional", e.data)["fator_r_minimo"])
        candidatos.append(max(sm, arredondar(e.receita_mensal * minimo + D("0.01"))))
    melhor: OpcaoAutonomo | None = None
    for pl in candidatos:
        perfil = _perfil(e, pl)
        calc = simples.calcular(perfil)
        if not calc.aplicavel:
            return OpcaoAutonomo("Simples Nacional", False, ZERO, ZERO, ZERO, calc)
        res = Resultado("Simples Nacional")
        anexo = simples.anexo_da_atividade(perfil)
        res.memoria.extend(calc.memoria)
        for nome, valor in calc.tributos.items():
            res.tributos[nome] = res.passo(f"{nome} mensal", f"{brl(valor)} / 12", valor / 12)
        _socio(res, pl, e.data)
        res.alertas.extend(a for a in calc.alertas if not a.startswith("Fator R abaixo"))
        total = res.total
        opcao = OpcaoAutonomo(
            "Simples Nacional", True, total, e.contabilidade_mensal,
            _liquido(e, total, e.contabilidade_mensal), res,
            detalhe=f"Anexo {anexo}, pró-labore de {brl(pl)}",
        )
        if melhor is None or opcao.liquido_mensal > melhor.liquido_mensal:
            melhor = opcao
    assert melhor is not None
    if len(candidatos) > 1:
        melhor.resultado.alerta(f"Comparados pró-labore mínimo e pró-labore para fator R de 28%; escolhido: {melhor.detalhe}.")
    return melhor


def _presumido(e: EntradaAutonomo) -> OpcaoAutonomo:
    sm = pf.salario_minimo(e.data)
    calc = presumido.calcular(_perfil(e, sm))
    res = Resultado("Lucro Presumido")
    if not calc.aplicavel:
        return OpcaoAutonomo(res.titulo, False, ZERO, ZERO, ZERO, calc)
    res.memoria.extend(calc.memoria)
    for nome, valor in calc.tributos.items():
        res.tributos[nome] = res.passo(f"{nome} mensal", f"{brl(valor)} / 12", valor / 12)
    _socio(res, sm, e.data)
    total = res.total
    return OpcaoAutonomo(
        res.titulo, True, total, e.contabilidade_mensal, _liquido(e, total, e.contabilidade_mensal), res,
        detalhe=f"pró-labore de {brl(sm)}",
    )


@dataclass
class ComparativoAutonomo:
    entrada: EntradaAutonomo
    opcoes: list[OpcaoAutonomo]
    alertas: list[str] = field(default_factory=list)

    @property
    def aplicaveis(self) -> list[OpcaoAutonomo]:
        return sorted((o for o in self.opcoes if o.aplicavel), key=lambda o: -o.liquido_mensal)

    @property
    def melhor(self) -> OpcaoAutonomo:
        return self.aplicaveis[0]

    @property
    def ganho_vs_autonomo_anual(self) -> Decimal:
        autonomo = next(o for o in self.opcoes if o.nome.startswith("Autônomo"))
        return (self.melhor.liquido_mensal - autonomo.liquido_mensal) * 12


def comparar(e: EntradaAutonomo) -> ComparativoAutonomo:
    c = ComparativoAutonomo(e, [_autonomo(e), _mei(e), _simples(e), _presumido(e)])
    if e.contabilidade_mensal == 0:
        c.alertas.append("Honorários contábeis não informados: inclua o custo de manter o CNPJ para comparar de forma justa.")
    if e.receita_mensal - e.despesas_mensais > D("50000"):
        c.alertas.append("Lucro distribuído acima de R$ 50 mil/mês por empresa tem retenção de 10% (Lei 15.270/2025).")
    c.alertas.append(
        f"Valores mensais com receita constante; aposentadoria: autônomo contribui sobre até {pct(INSS_AUTONOMO, 0)} da "
        "remuneração, sócio sobre o pró-labore e MEI sobre um salário mínimo."
    )
    return c
