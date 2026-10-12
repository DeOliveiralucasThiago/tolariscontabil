from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import autonomo, pessoa_fisica as pf

D = Decimal


def comparar(**kw):
    base = dict(receita_mensal=6000, atividade="servico_fator_r")
    base.update(kw)
    return autonomo.comparar(autonomo.EntradaAutonomo(**base))


def opcao(c, nome):
    return next(o for o in c.opcoes if o.nome.startswith(nome))


def test_autonomo_inss_20_e_carne_leao_com_reducao():
    o = opcao(comparar(), "Autônomo")
    assert o.resultado.tributos["INSS (20%)"] == D("1200")
    # Base 6.000 - 1.200 = 4.800 -> 4.800 x 27,5% - 908,73 = 411,27; redução 978,62 - 0,133145 x 6.000 = 179,75
    assert o.resultado.tributos["IRPF (carnê-leão)"] == D("231.52")
    assert o.liquido_mensal == D("6000") - D("1431.52")


def test_autonomo_inss_limitado_ao_teto():
    o = opcao(comparar(receita_mensal=20000), "Autônomo")
    assert o.resultado.tributos["INSS (20%)"] == D("1695.11")  # 8.475,55 x 20%


def test_mei_valor_2026_e_limite():
    o = opcao(comparar(mei_permitido=True), "MEI")
    assert o.aplicavel and o.tributos_mensais == D("86.05")  # 81,05 INSS + 5,00 ISS
    assert not opcao(comparar(mei_permitido=True, receita_mensal=7000), "MEI").aplicavel
    assert not opcao(comparar(mei_permitido=False), "MEI").aplicavel


def test_simples_escolhe_pro_labore_do_fator_r():
    o = opcao(comparar(receita_mensal=15000, contabilidade_mensal=400), "Simples")
    # Pró-labore para 28%: 4.200,01; Anexo III 6% -> DAS 900; INSS 11% = 462,00; IRPF zero
    assert "Anexo III" in o.detalhe and "4.200,01" in o.detalhe
    assert o.tributos_mensais == D("1362.00")
    assert o.liquido_mensal == D("15000") - D("1362.00") - D("400")


def test_presumido_servicos():
    o = opcao(comparar(receita_mensal=15000, aliquota_iss="0.02"), "Lucro Presumido")
    # 180.000/ano: IRPJ 15% x 32% = 4,8%; CSLL 2,88%; PIS/Cofins 3,65%; ISS 2%; CPP 20% x pró-labore
    esperado_empresa = D(15000) * (D("0.048") + D("0.0288") + D("0.0365") + D("0.02")) + D("1621") * D("0.2")
    socio = D("178.31")  # 11% de 1.621
    assert o.tributos_mensais == pytest.approx(esperado_empresa + socio, abs=D("0.01"))


def test_melhor_e_ganho():
    c = comparar(receita_mensal=15000, despesas_mensais=1000, contabilidade_mensal=400)
    assert c.melhor.nome == "Simples Nacional"
    assert c.ganho_vs_autonomo_anual > 0
    assert any("Livro-caixa" in a for a in opcao(c, "Autônomo").resultado.alertas)


def test_alerta_sem_contabilidade():
    assert any("Honorários" in a for a in comparar().alertas)


def test_salario_liquido():
    r = pf.salario_liquido(5900, date(2026, 1, 1))
    assert r.tributos == {"INSS": D("627.51"), "IRRF": D("348.14")}
    assert r.memoria[-1].valor == D("4924.35")
