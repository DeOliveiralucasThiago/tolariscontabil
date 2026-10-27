"""Reforma Tributária para sociedades uniprofissionais: ISS fixo na transição e redução de 30% (LC 214/2025, art. 127)."""

from decimal import Decimal

import pytest

from tolaris_motor import reforma

D = Decimal


def sim(**extra):
    base = dict(receita_bruta_anual=600_000, vende_mercadoria=False, reducao_setorial="0.3", iss_fixo_anual=3_000, anos=list(range(2026, 2034)))
    return {a.ano: a for a in reforma.simular(reforma.EntradaReforma(**{**base, **extra}))}


@pytest.mark.parametrize("ano, fracao", [(2026, "1"), (2027, "1"), (2028, "1"), (2029, "0.9"), (2030, "0.8"), (2031, "0.7"), (2032, "0.6"), (2033, "0")])
def test_iss_fixo_cai_com_a_transicao_e_some_em_2033(ano, fracao):
    t = sim()[ano].resultado.tributos
    assert t.get("ISS", D(0)) == D(3_000) * D(fracao)


def test_iss_fixo_nao_depende_da_receita_nem_da_aliquota_do_municipio():
    a = sim(aliquota_iss="0.02")[2027].resultado.tributos["ISS"]
    b = sim(receita_bruta_anual=900_000)[2027].resultado.tributos["ISS"]
    assert a == b == D(3_000)


def test_base_de_venda_usa_o_iss_fixo_como_fracao_da_receita():
    e = reforma.EntradaReforma(600_000, False, iss_fixo_anual=3_000)
    assert reforma.aliquota_iss_efetiva(e) == D("0.005")
    assert reforma.base_venda_sem_tributos(e) == D(600_000) * (1 - D("0.0365") - D("0.005"))


def test_carga_sobe_muito_em_2033_com_o_fim_do_iss_fixo():
    anos = sim()
    assert anos[2033].carga_sobre_base > anos[2026].carga_sobre_base * 3
    assert anos[2033].total > anos[2032].total > anos[2029].total > anos[2027].total


def test_reducao_de_30_por_cento_reduz_cbs_e_ibs():
    cheia = sim(reducao_setorial="0")[2030].resultado.tributos
    reduzida = sim()[2030].resultado.tributos
    assert reduzida["CBS"] == pytest.approx(cheia["CBS"] * D("0.7"), abs=D("0.01"))
    assert reduzida["IBS"] == pytest.approx(cheia["IBS"] * D("0.7"), abs=D("0.01"))


def test_alerta_diz_que_a_lei_nao_tem_regra_propria_para_o_iss_fixo():
    alerta = " ".join(sim()[2026].resultado.alertas)
    assert "não traz regra própria" in alerta and "art. 8º-B" in alerta and "art. 543" in alerta


def test_sem_iss_fixo_nao_ha_o_alerta():
    assert not any("ISS fixo" in a for a in sim(iss_fixo_anual=0)[2026].resultado.alertas)


def test_iss_fixo_so_vale_para_servicos():
    with pytest.raises(ValueError, match="só se aplica a serviços"):
        reforma.EntradaReforma(600_000, True, iss_fixo_anual=3_000)
