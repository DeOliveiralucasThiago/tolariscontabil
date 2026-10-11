"""Tipos básicos do motor: dinheiro em Decimal, memória de cálculo e resultado.

Todo valor monetário trafega como ``Decimal`` com precisão total; o arredondamento
para centavos acontece só na apresentação (``brl``) ou quando a lei manda
(ex.: contribuição do INSS por faixa).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Union

Numero = Union[Decimal, int, float, str]

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")


def D(valor: Numero) -> Decimal:
    """Converte para Decimal sem herdar o erro binário de floats (usa ``str``)."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def brl(valor: Numero) -> str:
    """Formata no padrão brasileiro: ``R$ 1.234,56``."""
    v = arredondar(D(valor))
    sinal = "-" if v < 0 else ""
    inteiro, centavos = f"{abs(v):.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{centavos}"


def pct(valor: Numero, casas: int = 2) -> str:
    """Formata fração como percentual brasileiro: ``0.0997`` -> ``9,97%``."""
    v = D(valor) * 100
    return f"{v:.{casas}f}".replace(".", ",") + "%"


@dataclass(frozen=True)
class Passo:
    """Uma linha da memória de cálculo: o que foi feito, como e com base em quê."""

    descricao: str
    formula: str
    valor: Decimal
    base_legal: str = ""


@dataclass
class Resultado:
    """Saída padrão de um cálculo: total, quebra por tributo, memória e alertas."""

    titulo: str
    tributos: dict[str, Decimal] = field(default_factory=dict)
    memoria: list[Passo] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    aplicavel: bool = True

    @property
    def total(self) -> Decimal:
        return sum(self.tributos.values(), ZERO)

    def passo(self, descricao: str, formula: str, valor: Decimal, base_legal: str = "") -> Decimal:
        self.memoria.append(Passo(descricao, formula, valor, base_legal))
        return valor

    def alerta(self, mensagem: str) -> None:
        if mensagem not in self.alertas:
            self.alertas.append(mensagem)

    def resumo(self) -> str:
        linhas = [self.titulo]
        if not self.aplicavel:
            linhas.append("  (não aplicável)")
        for nome, valor in self.tributos.items():
            linhas.append(f"  {nome:<28} {brl(valor):>18}")
        linhas.append(f"  {'TOTAL':<28} {brl(self.total):>18}")
        for a in self.alertas:
            linhas.append(f"  ! {a}")
        return "\n".join(linhas)
