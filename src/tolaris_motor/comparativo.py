"""Comparativo entre regimes e simulação expressa (as "3 perguntas" da prospecção)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import presumido, real, simples
from .base import D, Numero, Resultado, brl
from .empresa import Atividade, PerfilEmpresa


@dataclass
class Comparativo:
    perfil: PerfilEmpresa
    resultados: list[Resultado]
    alertas: list[str] = field(default_factory=list)

    @property
    def aplicaveis(self) -> list[Resultado]:
        return sorted((r for r in self.resultados if r.aplicavel), key=lambda r: r.total)

    @property
    def melhor(self) -> Resultado:
        return self.aplicaveis[0]

    @property
    def economia_vs_segundo(self) -> Decimal:
        a = self.aplicaveis
        return a[1].total - a[0].total if len(a) > 1 else D(0)

    @property
    def economia_vs_pior(self) -> Decimal:
        a = self.aplicaveis
        return a[-1].total - a[0].total

    def resumo(self) -> str:
        linhas = [r.resumo() for r in self.resultados]
        linhas.append(
            f"\nMelhor regime: {self.melhor.titulo} — economia de {brl(self.economia_vs_segundo)}/ano "
            f"sobre a 2ª opção e de {brl(self.economia_vs_pior)}/ano sobre a pior."
        )
        linhas.extend(f"! {a}" for a in self.alertas)
        return "\n\n".join(linhas)


def comparar(perfil: PerfilEmpresa) -> Comparativo:
    return Comparativo(perfil, [simples.calcular(perfil), presumido.calcular(perfil), real.calcular(perfil)])


def simulacao_expressa(
    faturamento_mensal: Numero,
    folha_mensal: Numero,
    atividade: Atividade | str,
    pro_labore_mensal: Numero = 0,
    margem_lucro: Numero = "0.20",
    ano: int = 2026,
) -> Comparativo:
    """Previsão rápida com faturamento, folha e atividade.

    ``folha_mensal`` são salários de empregados (sem pró-labore, que pode vir separado).
    O Lucro Real depende do lucro, então supõe-se que folha, encargos (35,8% CLT; 20% pró-labore)
    e demais custos somem ``(1 - margem_lucro)`` da receita, antes dos tributos sobre vendas.
    O custo restante vira compras (comércio/indústria) ou despesas sem crédito (serviços).
    É uma premissa forte e aparece nos alertas.
    """
    receita = D(faturamento_mensal) * 12
    folha = D(folha_mensal) * 12
    pl = D(pro_labore_mensal) * 12
    atividade = Atividade(atividade)
    custo_restante = max(D(0), receita * (1 - D(margem_lucro)) - folha * D("1.358") - pl * D("1.2"))
    perfil = PerfilEmpresa(
        atividade=atividade,
        receita_bruta_anual=receita,
        folha_clt_anual=folha,
        pro_labore_anual=pl,
        compras_anual=custo_restante if atividade.vende_mercadoria else 0,
        outras_despesas_anual=0 if atividade.vende_mercadoria else custo_restante,
        ano=ano,
    )
    comp = comparar(perfil)
    comp.alertas.append(
        f"Simulação expressa: Lucro Real estimado com margem de {D(margem_lucro) * 100:.0f}% e custos "
        "não detalhados; use o planejamento completo antes de recomendar Lucro Real."
    )
    return comp
