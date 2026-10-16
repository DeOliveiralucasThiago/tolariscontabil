"""Projeção da receita e cruzamento dos limites de enquadramento."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import projecao as pj


def serie(inicio: str, valores: list[int]) -> dict[str, Decimal]:
    return {pj.proximo_mes(inicio, i): Decimal(v) for i, v in enumerate(valores)}


def test_receita_constante_nao_tem_tendencia():
    p = pj.projetar(serie("2025-01", [100_000] * 12))
    assert p.meses_base == 12 and p.rbt12_atual == 1_200_000 and p.tendencia_mensal == 0
    assert p.confianca == "media"  # 12 meses, mas sem tendência (r² zero): não é "alta"
    assert all(x.receita == 100_000 and x.rbt12 == 1_200_000 for x in p.pontos)
    assert p.pontos[0].competencia == "2026-01" and p.pontos[-1].competencia == "2026-12"


def test_crescimento_linear_perfeito():
    # 100 mil crescendo 5 mil por mês: ao fim de 12 meses, 155 mil
    p = pj.projetar(serie("2025-01", [100_000 + 5_000 * i for i in range(12)]))
    assert p.tendencia_mensal == 5_000 and p.r2 == 1 and p.confianca == "alta"
    assert p.rbt12_atual == sum(100_000 + 5_000 * i for i in range(12))
    assert p.pontos[0].receita == 160_000 and p.pontos[11].receita == 215_000
    # o RBT12 do mês seguinte troca janeiro/25 (100 mil) por jan/26 (160 mil)
    assert p.pontos[0].rbt12 == p.rbt12_atual - 100_000 + 160_000


def test_queda_nao_projeta_receita_negativa():
    p = pj.projetar(serie("2025-01", [100_000 - 9_000 * i for i in range(12)]))
    assert p.tendencia_mensal == -9_000
    assert min(x.receita for x in p.pontos) == 0
    assert all(x.rbt12 >= 0 for x in p.pontos)


def test_poucos_meses_nao_projeta():
    assert pj.projetar(serie("2025-01", [100_000] * 5)) is None
    assert pj.projetar({}) is None


def test_meses_faltando_na_janela_usam_a_media_no_rbt12():
    s = serie("2025-01", [100_000] * 12)
    del s["2025-03"], s["2025-04"]
    p = pj.projetar(s)
    assert p.meses_base == 10 and p.rbt12_atual == 1_200_000  # 10 conhecidos + 2 pela média


def test_so_olha_os_ultimos_12_meses():
    s = serie("2023-01", [900_000] * 12 + [50_000] * 12)  # dois anos atrás era outro negócio
    p = pj.projetar(s)
    assert p.meses_base == 12 and p.media_mensal == 50_000 and p.rbt12_atual == 600_000


def test_confianca_media_por_quantidade_de_meses():
    p = pj.projetar(serie("2025-01", [100_000, 130_000, 90_000, 140_000, 95_000, 120_000, 110_000, 135_000, 100_000]))
    assert p.meses_base == 9 and p.confianca == "media"


def test_limites_por_regime():
    d = date(2026, 1, 1)
    assert [l.codigo for l in pj.limites_do_regime("mei", d)] == ["mei_limite"]
    assert pj.limites_do_regime("mei", d)[0].valor == 81_000
    s = {l.codigo: l.valor for l in pj.limites_do_regime("simples", d)}
    assert s == {"simples_sublimite": 3_600_000, "simples_limite": 4_800_000}
    assert pj.limites_do_regime("presumido", d)[0].valor == 78_000_000
    assert pj.limites_do_regime(None, d) == [] and pj.limites_do_regime("real", d) == []


def test_cruzamento_do_limite_do_simples():
    # RBT12 de 4,2 mi crescendo: cruza 4,8 mi em alguns meses
    p = pj.projetar(serie("2025-01", [300_000 + 8_000 * i for i in range(12)]))
    achados = {c.codigo: c for c in pj.cruzamentos(p, pj.limites_do_regime("simples", date(2026, 1, 1)))}
    assert set(achados) == {"simples_limite"}  # o sublimite (3,6 mi) já foi passado: não é "cruzamento"
    c = achados["simples_limite"]
    assert c.limite == 4_800_000 and 1 <= c.em_meses <= 12
    k = c.em_meses
    assert p.pontos[k - 1].rbt12 > 4_800_000 and (k == 1 or p.pontos[k - 2].rbt12 <= 4_800_000)
    assert c.competencia == p.pontos[k - 1].competencia


def test_limite_ja_ultrapassado_nao_vira_cruzamento():
    p = pj.projetar(serie("2025-01", [400_000] * 12))  # RBT12 = 4,8 mi exatos... acima do sublimite, no limite
    achados = pj.cruzamentos(p, pj.limites_do_regime("simples", date(2026, 1, 1)))
    assert [c.codigo for c in achados] == []  # sublimite já passou; limite não é ultrapassado com receita estável


def test_mei_cruza_o_limite_pelo_ritmo():
    p = pj.projetar(serie("2025-01", [4_000 + 200 * i for i in range(12)]))
    assert p.rbt12_atual < 81_000
    c = pj.cruzamentos(p, pj.limites_do_regime("mei", date(2026, 1, 1)))
    assert len(c) == 1 and c[0].codigo == "mei_limite"


def test_nada_cruza_com_receita_estavel_abaixo():
    p = pj.projetar(serie("2025-01", [50_000] * 12))
    assert pj.cruzamentos(p, pj.limites_do_regime("simples", date(2026, 1, 1))) == []
