"""Limite do MEI por ano (LC 238/2026): R$ 81 mil até 2026, R$ 110 mil em 2027 e R$ 140 mil a partir de 2028."""

from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import autonomo, avisos, projecao as pj

D = Decimal


@pytest.mark.parametrize("ano, limite", [(2018, 81_000), (2026, 81_000), (2027, 110_000), (2028, 140_000), (2035, 140_000)])
def test_limite_do_mei_por_ano(ano, limite):
    assert autonomo.limite_mei(date(ano, 1, 1)) == D(limite)
    assert autonomo.limite_mei(date(ano, 12, 31)) == D(limite)


def _mei(rbt12, ano):
    return {a.codigo: a for a in avisos.avaliar_limites(rbt12, "mei", date(ano, 1, 1))}


def test_receita_de_100_mil_passa_do_limite_em_2026_mas_nao_em_2027():
    # 2026: acima de R$ 97.200 (81.000 + 20%), desenquadramento retroativo
    a26 = _mei(100_000, 2026)["mei_limite"]
    assert a26.gravidade == "critico" and "MEI desenquadrado" in a26.titulo and "R$ 97.200,00" in a26.titulo
    # 2027: 91% do limite de R$ 110.000, só perto do limite
    a27 = _mei(100_000, 2027)["mei_limite"]
    assert a27.gravidade == "atencao" and "91% do limite do MEI" in a27.titulo and "R$ 110.000,00" in a27.detalhe
    # 2028: 71% de R$ 140.000, sem aviso
    assert _mei(100_000, 2028) == {}


def test_aviso_de_2026_explica_que_o_limite_novo_nao_vale_para_o_ano():
    detalhe = _mei(85_000, 2026)["mei_limite"].detalhe
    assert "LC 238/2026 sobe o limite para R$ 110.000,00 em 2027, mas isso não vale para 2026" in detalhe
    assert "LC 238/2026" in _mei(100_000, 2026)["mei_limite"].detalhe
    assert "LC 238/2026" in _mei(70_000, 2026)["mei_limite"].detalhe
    # em 2027 o limite de 2028 é maior; em 2028 não há mais ampliação
    assert "R$ 140.000,00 em 2028" in _mei(100_000, 2027)["mei_limite"].detalhe
    assert "LC 238/2026" not in _mei(120_000, 2028)["mei_limite"].detalhe


def test_limite_da_projecao_acompanha_os_degraus_do_mei():
    lim = pj.limites_do_regime("mei", date(2026, 6, 1))[0]
    assert lim.valor == D(81_000)
    assert [lim.valor_em(c) for c in ("2026-12", "2027-01", "2027-12", "2028-01")] == [D(81_000), D(110_000), D(110_000), D(140_000)]
    # outros regimes não têm degraus
    assert pj.limites_do_regime("simples", date(2026, 1, 1))[0].valor_em("2030-01") == pj.limites_do_regime("simples", date(2026, 1, 1))[0].valor


def test_projecao_do_mei_cruza_o_limite_de_2027_e_nao_o_de_2026():
    # receita mensal subindo R$ 250 por mês, de R$ 5.000 (RBT12 de R$ 76.500 em dez/2026): em fev/2027 passaria de R$ 81 mil,
    # mas o limite de 2027 é de R$ 110 mil, então o cruzamento é o de R$ 110 mil e vem bem depois
    receitas = {f"2026-{m:02d}": D(5_000 + 250 * (m - 1)) for m in range(1, 13)}
    proj = pj.projetar(receitas)
    cruz = pj.cruzamentos(proj, pj.limites_do_regime("mei", date(2026, 12, 15)))
    assert len(cruz) == 1 and cruz[0].limite == D(110_000)
    assert proj.rbt12_atual == D(76_500) and proj.pontos[1].rbt12 > D(81_000)   # passaria de R$ 81 mil já em fev/2027
    assert cruz[0].em_meses >= 8


def test_comparativo_autonomo_aceita_mei_com_receita_de_96_mil_em_2027():
    e26 = autonomo.EntradaAutonomo(8_000, mei_permitido=True, data=date(2026, 1, 1))
    e27 = autonomo.EntradaAutonomo(8_000, mei_permitido=True, data=date(2027, 1, 1))
    mei26 = next(o for o in autonomo.comparar(e26).opcoes if o.nome == "MEI")
    mei27 = next(o for o in autonomo.comparar(e27).opcoes if o.nome == "MEI")
    assert not mei26.aplicavel and mei27.aplicavel   # R$ 96.000 por ano: acima de R$ 81 mil, abaixo de R$ 110 mil
    assert any("R$ 81.000,00" in a for a in mei26.resultado.alertas)
