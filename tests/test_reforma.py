from decimal import Decimal

import pytest

from tolaris_motor import reforma

D = Decimal


def comercio(**kw):
    base = dict(receita_bruta_anual=1_000_000, vende_mercadoria=True, compras_anual=600_000)
    base.update(kw)
    return reforma.EntradaReforma(**base)


def por_ano(entrada):
    return {a.ano: a for a in reforma.simular(entrada)}


def test_base_de_venda_desembute_tributos_atuais():
    # 1.000.000 x (1 - 3,65% - 18%)
    assert reforma.base_venda_sem_tributos(comercio()) == D("783500")
    # Compras: 600.000 x (1 - 18% - 9,25%)
    assert reforma.base_credito_sem_tributos(comercio()) == D("436500")


def test_2025_e_2026_iguais_ano_teste_nao_soma():
    anos = por_ano(comercio())
    assert anos[2025].total == anos[2026].total == D("108500")  # 36.500 PIS/Cofins + 72.000 ICMS
    assert "CBS" not in anos[2026].resultado.tributos
    assert any("ano-teste" in p.descricao for p in anos[2026].resultado.memoria)


def test_2027_cbs_cheia_menos_0_1pp_e_fim_do_pis_cofins():
    a = por_ano(comercio())[2027].resultado.tributos
    assert "PIS/Cofins" not in a
    assert a["ICMS"] == D("72000")
    # CBS 8,7% e IBS 0,1% sobre 783.500, crédito sobre 436.500
    assert a["CBS"] == D("783500") * D("0.087") - D("436500") * D("0.087")
    assert a["IBS"] == (D("783500") - D("436500")) * D("0.001")


def test_2029_a_2032_icms_cai_e_ibs_sobe():
    anos = por_ano(comercio())
    for ano, fator in ((2029, D("0.9")), (2030, D("0.8")), (2031, D("0.7")), (2032, D("0.6"))):
        t = anos[ano].resultado.tributos
        assert t["ICMS"] == D("72000") * fator
        assert t["IBS"] == D("347000") * D("0.177") * (1 - fator)


def test_2033_somente_ibs_cbs():
    t = por_ano(comercio())[2033].resultado.tributos
    assert set(t) == {"CBS", "IBS"}
    assert sum(t.values()) == D("347000") * D("0.265")


def test_reducao_setorial_aplica_na_venda_nao_no_credito():
    e = reforma.EntradaReforma(600_000, vende_mercadoria=False, despesas_creditaveis_anual=60_000, reducao_setorial="0.3")
    t = por_ano(e)[2033].resultado.tributos
    base = D(600_000) * (1 - D("0.0365") - D("0.05"))
    credito = D(60_000) * (1 - D("0.0925"))
    assert t["CBS"] == base * D("0.088") * D("0.7") - credito * D("0.088")


def test_saldo_credor_gera_alerta_e_nao_negativo():
    e = comercio(compras_anual=2_000_000)
    a = por_ano(e)[2033]
    assert a.total == 0
    assert any("saldo credor" in x for x in a.resultado.alertas)


def test_aliquotas_de_referencia_customizadas():
    e = comercio(cbs_referencia="0.0921", ibs_referencia="0.187")
    assert sum(por_ano(e)[2033].resultado.tributos.values()) == D("347000") * D("0.2791")


def test_reducao_setorial_invalida():
    with pytest.raises(ValueError):
        comercio(reducao_setorial=2)
