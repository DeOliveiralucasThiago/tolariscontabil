"""Projeção da receita e dos limites de enquadramento (MEI, Simples, Presumido).

Funções puras sobre a receita mensal já realizada. A projeção é uma tendência linear dos últimos meses, não uma
previsão: ela serve para avisar com antecedência "no ritmo atual, o limite é ultrapassado em tal mês", e vem sempre
com um grau de confiança.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import tabelas
from .autonomo import limite_mei
from .base import ZERO, D

MIN_MESES = 6
"""Menos meses que isso e a tendência não é confiável: não projeta."""
JANELA = 12
HORIZONTE = 12


def proximo_mes(comp: str, n: int = 1) -> str:
    indice = int(comp[:4]) * 12 + int(comp[5:7]) - 1 + n
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _indice(comp: str) -> int:
    return int(comp[:4]) * 12 + int(comp[5:7]) - 1


@dataclass(frozen=True)
class PontoProjetado:
    competencia: str
    receita: Decimal
    rbt12: Decimal


@dataclass(frozen=True)
class Projecao:
    ultimo_mes: str
    meses_base: int
    """Meses com receita conhecida na janela de 12 meses que termina no último mês."""
    rbt12_atual: Decimal
    media_mensal: Decimal
    tendencia_mensal: Decimal
    """Quanto a receita mensal cresce (ou cai) por mês, em R$, pela reta ajustada."""
    r2: Decimal
    confianca: str
    """alta, media ou baixa."""
    pontos: list[PontoProjetado] = field(default_factory=list)


@dataclass(frozen=True)
class Limite:
    codigo: str
    rotulo: str
    valor: Decimal
    degraus: tuple[tuple[str, Decimal], ...] = ()
    """Limite que muda no tempo: pares (competência de início AAAA-MM, valor). Vazio quando o ``valor`` vale sempre."""

    def valor_em(self, competencia: str) -> Decimal:
        """Limite vigente na competência (o MEI sobe de R$ 81 mil para R$ 110 mil em 2027 e R$ 140 mil em 2028)."""
        vigente = self.valor
        for inicio, valor in self.degraus:
            if inicio <= competencia:
                vigente = valor
        return vigente


@dataclass(frozen=True)
class Cruzamento:
    codigo: str
    rotulo: str
    limite: Decimal
    competencia: str
    em_meses: int
    """Meses a partir do último mês conhecido."""


def _reta(xs: list[int], ys: list[Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    """Mínimos quadrados: (inclinação, intercepto, r²)."""
    n = len(xs)
    mx, my = D(sum(xs)) / n, sum(ys, ZERO) / n
    sxx = sum((D(x) - mx) ** 2 for x in xs)
    sxy = sum((D(x) - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0:
        return ZERO, my, ZERO
    b = sxy / sxx
    a = my - b * mx
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else ZERO
    return b, a, r2


def projetar(receitas: dict[str, Decimal], horizonte: int = HORIZONTE) -> Projecao | None:
    """Projeta os próximos ``horizonte`` meses a partir da receita mensal conhecida (competência AAAA-MM -> R$).

    Meses sem informação dentro da janela são tratados como desconhecidos (não como zero) e, para fechar os 12
    meses do RBT12, recebem a média dos meses conhecidos.
    """
    if not receitas:
        return None
    ultimo = max(receitas)
    janela = [proximo_mes(ultimo, -n) for n in range(JANELA - 1, -1, -1)]
    conhecidos = {c: D(receitas[c]) for c in janela if c in receitas}
    if len(conhecidos) < MIN_MESES:
        return None
    base = _indice(janela[0])
    xs = [_indice(c) - base for c in conhecidos]
    ys = list(conhecidos.values())
    b, a, r2 = _reta(xs, ys)
    media = sum(ys, ZERO) / len(ys)
    completos = {c: conhecidos.get(c, media) for c in janela}
    valores = [completos[c] for c in janela]
    rbt12_atual = sum(valores, ZERO)

    pontos: list[PontoProjetado] = []
    ultimo_x = _indice(ultimo) - base
    deslizante = list(valores)
    for k in range(1, horizonte + 1):
        v = max(ZERO, a + b * (ultimo_x + k))
        deslizante = deslizante[1:] + [v]
        pontos.append(PontoProjetado(proximo_mes(ultimo, k), v, sum(deslizante, ZERO)))

    if len(conhecidos) >= 12 and r2 >= D("0.5"):
        confianca = "alta"
    elif len(conhecidos) >= 9 or r2 >= D("0.3"):
        confianca = "media"
    else:
        confianca = "baixa"
    return Projecao(ultimo, len(conhecidos), rbt12_atual, media, b, r2, confianca, pontos)


def limites_do_regime(regime: str | None, data: date) -> list[Limite]:
    if regime == "mei":
        degraus = tuple((v["inicio"][:7], D(v["limite_receita_anual"])) for v in tabelas.carregar("mei")["vigencias"])
        return [Limite("mei_limite", "limite do MEI", limite_mei(data), degraus)]
    if regime == "simples":
        t = tabelas.vigente("simples_nacional", data)
        return [
            Limite("simples_sublimite", "sublimite do Simples", D(t["sublimite_icms_iss"])),
            Limite("simples_limite", "limite do Simples", D(t["limite_receita_anual"])),
        ]
    if regime == "presumido":
        t = tabelas.vigente("lucro_presumido", data)
        return [Limite("presumido_limite", "limite do Lucro Presumido", D(t["limite_receita_anual"]))]
    return []


def cruzamentos(proj: Projecao, limites: list[Limite]) -> list[Cruzamento]:
    """Limites ainda não ultrapassados que o RBT12 projetado ultrapassa dentro do horizonte."""
    achados = []
    for lim in limites:
        if proj.rbt12_atual > lim.valor:
            continue  # já passou: é assunto dos avisos de limite atuais
        for k, p in enumerate(proj.pontos, start=1):
            vigente = lim.valor_em(p.competencia)
            if p.rbt12 > vigente:
                achados.append(Cruzamento(lim.codigo, lim.rotulo, vigente, p.competencia, k))
                break
    return achados
