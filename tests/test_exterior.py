"""Receita do exterior (exportação) e variação cambial nos três regimes."""

from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, presumido, real, simples
from tolaris_motor.comparativo import comparar

D = Decimal
HOJE = date(2026, 1, 1)


def perfil(**extra) -> PerfilEmpresa:
    base = dict(atividade=Atividade.SERVICO_FATOR_R, receita_bruta_anual=600_000, folha_clt_anual=0,
                pro_labore_anual=240_000, outras_despesas_anual=60_000)
    return PerfilEmpresa(**{**base, **extra})


def test_validacoes_do_perfil():
    with pytest.raises(ValueError, match="passar da receita"):
        perfil(receita_exterior_anual=700_000)
    with pytest.raises(ValueError, match="negativo"):
        perfil(receita_exterior_anual=-1)
    assert perfil(variacao_cambial_anual=-5_000).variacao_cambial_anual == D(-5_000)  # perda é permitida
    p = perfil(receita_exterior_anual=250_000)
    assert p.receita_interna_anual == D(350_000)


def test_sem_exterior_nada_muda():
    p = perfil()
    assert simples.calcular(p).tributos["DAS"] == simples.calcular(perfil(receita_exterior_anual=0)).tributos["DAS"]
    assert not any("exportação" in a for a in simples.calcular(p).alertas)


def test_simples_servico_exportado_sem_iss_pis_cofins():
    # Fator R = 40% (>= 28%): Anexo III. Cada mercado tem a sua alíquota, pelo RBT12 do próprio mercado (art. 3º, § 15)
    todos = simples.calcular(perfil())
    parcial = simples.calcular(perfil(receita_exterior_anual=300_000))
    tudo = simples.calcular(perfil(receita_exterior_anual=600_000))
    aliq600 = simples.aliquota_efetiva("III", 600_000, HOJE)
    aliq300 = simples.aliquota_efetiva("III", 300_000, HOJE)
    exc600 = sum(simples.partilha("III", 600_000, HOJE)[k] for k in ("pis", "cofins", "iss"))
    exc300 = sum(simples.partilha("III", 300_000, HOJE)[k] for k in ("pis", "cofins", "iss"))
    assert 0 < exc600 < 1 and 0 < exc300 < 1
    assert todos.tributos["DAS"] == D(600_000) * aliq600
    assert tudo.tributos["DAS"] == D(600_000) * aliq600 * (1 - exc600)  # só exportação: o RBT12 de exportação é o total
    assert parcial.tributos["DAS"] == D(300_000) * aliq300 + D(300_000) * aliq300 * (1 - exc300)
    assert tudo.tributos["DAS"] < parcial.tributos["DAS"] < todos.tributos["DAS"]
    # com os dois mercados, cada alíquota usa o RBT12 do mercado (R$ 300.000), não o total (R$ 600.000)
    efetivas = [p for p in parcial.memoria if p.descricao.startswith("Alíquota efetiva")]
    assert len(efetivas) == 2 and all("300.000,00" in p.formula for p in efetivas)
    assert {p.descricao.split(", ")[-1] for p in efetivas} == {"mercado interno", "exportação"}
    assert any("exportação de serviços" in a and "ingresso de divisas" in a for a in parcial.alertas)
    assert any("Res. CGSN 190/2026" in a and "§ 4º-B" in a for a in parcial.alertas)


def test_simples_mercadoria_exportada_sem_icms_ipi_pis_cofins():
    p = PerfilEmpresa(atividade=Atividade.COMERCIO, receita_bruta_anual=1_000_000, receita_exterior_anual=400_000, compras_anual=500_000)
    r = simples.calcular(p)
    aliq_int = simples.aliquota_efetiva("I", 600_000, HOJE)
    aliq_exp = simples.aliquota_efetiva("I", 400_000, HOJE)
    fr = simples.partilha("I", 400_000, HOJE)
    excluida = fr["pis"] + fr["cofins"] + fr["icms"] + fr.get("ipi", D(0))
    assert r.tributos["DAS"] == D(600_000) * aliq_int + D(400_000) * aliq_exp * (1 - excluida)
    assert any("exportação de mercadorias" in a for a in r.alertas)


def test_simples_limites_separados_para_interno_e_exportacao():
    # R$ 4,8 mi no mercado interno + R$ 3 mi de exportação: cada mercado cabe no seu limite e usa a sua faixa
    r = simples.calcular(perfil(receita_bruta_anual=7_800_000, receita_exterior_anual=3_000_000, pro_labore_anual=2_000_000))
    assert r.aplicavel and not any("última faixa" in a for a in r.alertas)
    # fator R = 2.000.000 / 7.800.000 = 25,6% (sobre a receita total): Anexo V
    interna = simples.aliquota_efetiva("V", 4_800_000, HOJE)
    exportacao = simples.aliquota_efetiva("V", 3_000_000, HOJE)
    exc = sum(simples.partilha("V", 3_000_000, HOJE)[k] for k in ("pis", "cofins", "iss"))
    assert r.tributos["DAS"] == D(4_800_000) * interna + D(3_000_000) * exportacao * (1 - exc)
    # interno acima do limite
    assert not simples.calcular(perfil(receita_bruta_anual=5_000_000, receita_exterior_anual=100_000)).aplicavel
    # exportação acima do limite
    ex = simples.calcular(perfil(receita_bruta_anual=6_000_000, receita_exterior_anual=5_000_000))
    assert not ex.aplicavel and any("exportação acima" in a for a in ex.alertas)
    # sem exportação, a mensagem antiga continua
    assert "empresa não pode optar pelo Simples" in simples.calcular(perfil(receita_bruta_anual=5_000_000)).alertas[0]


def test_sublimite_so_conta_o_mercado_interno():
    # 3,5 mi no interno + 1 mi de exportação: total 4,5 mi, mas o interno está abaixo do sublimite de 3,6 mi
    r = simples.calcular(perfil(receita_bruta_anual=4_500_000, receita_exterior_anual=1_000_000, pro_labore_anual=1_500_000))
    assert not any("sublimite" in a for a in r.alertas)
    r2 = simples.calcular(perfil(receita_bruta_anual=4_500_000, receita_exterior_anual=500_000, pro_labore_anual=1_500_000))
    assert any("sublimite" in a for a in r2.alertas)


def test_presumido_servico_exportado_sem_pis_cofins_iss_mas_com_irpj_csll():
    cheio = presumido.calcular(perfil())
    ext = presumido.calcular(perfil(receita_exterior_anual=600_000))
    assert ext.tributos["PIS"] == 0 and ext.tributos["Cofins"] == 0 and ext.tributos["ISS"] == 0
    assert ext.tributos["IRPJ"] == cheio.tributos["IRPJ"] and ext.tributos["CSLL"] == cheio.tributos["CSLL"]
    assert cheio.tributos["PIS"] == D(600_000) * D("0.0065")
    meio = presumido.calcular(perfil(receita_exterior_anual=300_000))
    assert meio.tributos["PIS"] == D(300_000) * D("0.0065") and meio.tributos["ISS"] == D(300_000) * D("0.05")
    assert ext.total < meio.total < cheio.total


def test_presumido_variacao_cambial_ativa_soma_na_base():
    base = presumido.calcular(perfil(receita_exterior_anual=600_000))
    com = presumido.calcular(perfil(receita_exterior_anual=600_000, variacao_cambial_anual=40_000))
    # 40.000 a mais na base de IRPJ (15% + adicional de 10% se passar de 60 mil/trimestre) e de CSLL (9%)
    assert com.tributos["CSLL"] - base.tributos["CSLL"] == D(40_000) * D("0.09")
    assert com.tributos["IRPJ"] > base.tributos["IRPJ"]
    assert com.tributos["PIS"] == base.tributos["PIS"]  # receita financeira fora do PIS/Cofins
    assert any("Variação cambial ativa somada" in a for a in com.alertas)


def test_presumido_variacao_cambial_passiva_nao_abate():
    base = presumido.calcular(perfil(receita_exterior_anual=600_000))
    perda = presumido.calcular(perfil(receita_exterior_anual=600_000, variacao_cambial_anual=-40_000))
    assert perda.tributos["IRPJ"] == base.tributos["IRPJ"] and perda.tributos["CSLL"] == base.tributos["CSLL"]
    assert any("não reduz a base" in a for a in perda.alertas)


def test_real_exportacao_tira_debito_de_pis_cofins_e_mantem_credito():
    p = perfil(receita_bruta_anual=2_000_000, compras_anual=500_000, despesas_creditaveis_anual=100_000, pro_labore_anual=200_000)
    p_ext = perfil(receita_bruta_anual=2_000_000, receita_exterior_anual=1_500_000, compras_anual=500_000,
                   despesas_creditaveis_anual=100_000, pro_labore_anual=200_000)
    a, b = real.calcular(p), real.calcular(p_ext)
    assert b.tributos["PIS"] < a.tributos["PIS"] and b.tributos["Cofins"] < a.tributos["Cofins"]
    assert b.tributos["ISS"] == D(500_000) * D("0.05")
    # com 100% exportado, os débitos zeram e os créditos viram saldo (não entra no total)
    t = real.calcular(perfil(receita_bruta_anual=2_000_000, receita_exterior_anual=2_000_000, compras_anual=500_000, pro_labore_anual=200_000))
    assert t.tributos["PIS"] == 0 and t.tributos["Cofins"] == 0
    assert any("Créditos de PIS superam" in x for x in t.alertas)


def test_real_variacao_cambial_entra_no_lucro():
    p = dict(receita_bruta_anual=1_000_000, receita_exterior_anual=1_000_000, outras_despesas_anual=200_000, pro_labore_anual=100_000)
    sem = real.calcular(perfil(**p))
    ganho = real.calcular(perfil(**p, variacao_cambial_anual=50_000))
    perda = real.calcular(perfil(**p, variacao_cambial_anual=-50_000))
    assert ganho.tributos["CSLL"] - sem.tributos["CSLL"] == D(50_000) * D("0.09")
    assert sem.tributos["CSLL"] - perda.tributos["CSLL"] == D(50_000) * D("0.09")
    assert any("Variação cambial entra no lucro" in a for a in ganho.alertas)


def test_icms_so_sobre_vendas_internas_e_credito_mantido():
    p = PerfilEmpresa(atividade=Atividade.INDUSTRIA, receita_bruta_anual=1_000_000, receita_exterior_anual=400_000,
                      compras_anual=300_000, aliquota_icms="0.18")
    r = presumido.calcular(p)
    # débito 600.000 x 18% = 108.000; crédito 300.000 x 18% = 54.000
    assert r.tributos["ICMS"] == D(54_000)


def test_comparativo_com_exterior_recomenda_pelo_total():
    c = comparar(perfil(receita_exterior_anual=600_000))
    # Presumido já não paga PIS/Cofins/ISS; o Simples também desconta; o ranking deve ser coerente
    assert [r.titulo for r in c.aplicaveis][0] in ("Simples Nacional", "Lucro Presumido")
    assert all(r.total >= 0 for r in c.resultados)
