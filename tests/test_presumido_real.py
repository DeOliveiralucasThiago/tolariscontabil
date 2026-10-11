from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, comparar, presumido, real, simulacao_expressa

D = Decimal


def servico_600k(**kw):
    base = dict(
        atividade=Atividade.SERVICO_FATOR_R,
        receita_bruta_anual=600_000,
        folha_clt_anual=96_000,
        pro_labore_anual=60_000,
        ano=2026,
    )
    base.update(kw)
    return PerfilEmpresa(**base)


def test_presumido_servicos_sem_adicional():
    r = presumido.calcular(servico_600k())
    # Trimestre: 150.000 x 32% = 48.000 (abaixo de 60.000, sem adicional)
    assert r.tributos["IRPJ"] == D("28800")  # 48.000 x 15% x 4
    assert r.tributos["CSLL"] == D("17280")  # 48.000 x 9% x 4
    assert r.tributos["PIS"] == D("3900")
    assert r.tributos["Cofins"] == D("18000")
    assert r.tributos["ISS"] == D("30000")
    # 96.000 x 27,8% + 60.000 x 20%
    assert r.tributos["INSS patronal"] == D("38688")


def test_presumido_com_adicional_de_irpj():
    r = presumido.calcular(servico_600k(receita_bruta_anual=1_200_000))
    # Trimestre: 300.000 x 32% = 96.000 -> 14.400 + (96.000 - 60.000) x 10% = 18.000
    assert r.tributos["IRPJ"] == D("72000")


def test_presumido_comercio_presuncoes_e_icms_com_credito():
    p = PerfilEmpresa(Atividade.COMERCIO, 2_000_000, compras_anual=1_200_000, ano=2026)
    r = presumido.calcular(p)
    # IRPJ: 500.000 x 8% = 40.000/tri -> 6.000 x 4
    assert r.tributos["IRPJ"] == D("24000")
    # CSLL: 500.000 x 12% = 60.000/tri -> 5.400 x 4
    assert r.tributos["CSLL"] == D("21600")
    # ICMS: 2.000.000 x 18% - 1.200.000 x 18% = 144.000
    assert r.tributos["ICMS"] == D("144000")


def test_presumido_lc224_irpj_o_ano_todo_e_csll_a_partir_de_abril():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_III, 8_000_000, ano=2026)
    r = presumido.calcular(p)
    # Trimestre: receita 2.000.000; limite 1.250.000; excedente 750.000
    # Base IRPJ: 640.000 + 750.000 x 32% x 10% = 664.000
    # IRPJ/tri: 99.600 + (664.000 - 60.000) x 10% = 160.000 -> x4 = 640.000
    assert r.tributos["IRPJ"] == D("640000")
    # CSLL: 1º tri 640.000 x 9% = 57.600; 2º-4º tri 664.000 x 9% = 59.760
    assert r.tributos["CSLL"] == D("57600") + 3 * D("59760")
    assert any("LC 224" in a for a in r.alertas)


def test_presumido_2025_sem_lc224():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_III, 8_000_000, ano=2025)
    r = presumido.calcular(p)
    # 640.000/tri: 96.000 + 58.000 = 154.000 x 4
    assert r.tributos["IRPJ"] == D("616000")


def test_presumido_acima_de_78_milhoes():
    assert not presumido.calcular(PerfilEmpresa(Atividade.COMERCIO, 80_000_000)).aplicavel


def test_real_pis_cofins_nao_cumulativo_e_irpj():
    p = PerfilEmpresa(
        Atividade.COMERCIO,
        2_000_000,
        compras_anual=1_000_000,
        despesas_creditaveis_anual=100_000,
        outras_despesas_anual=200_000,
        folha_clt_anual=200_000,
        ano=2026,
    )
    r = real.calcular(p)
    assert r.tributos["PIS"] == D("14850")  # (2.000.000 - 1.100.000) x 1,65%
    assert r.tributos["Cofins"] == D("68400")  # 900.000 x 7,6%
    assert r.tributos["ICMS"] == D("180000")
    assert r.tributos["INSS patronal"] == D("55600")
    # Lucro: 2.000.000 - 1.000.000 - 300.000 - 200.000 - 16.000 FGTS - 318.850 tributos = 165.150
    assert r.tributos["IRPJ"] == D("24772.50")  # 165.150 x 15%, sem adicional
    assert r.tributos["CSLL"] == D("14863.50")


def test_real_prejuizo_zera_irpj_csll():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_III, 100_000, outras_despesas_anual=200_000)
    r = real.calcular(p)
    assert r.tributos["IRPJ"] == 0 and r.tributos["CSLL"] == 0
    assert any("Prejuízo" in a for a in r.alertas)


def test_real_adicional_acima_de_240_mil():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_III, 1_000_000, aliquota_iss=0)
    r = real.calcular(p)
    lucro = D(1_000_000) - D("92500")  # receita - PIS/Cofins
    assert r.tributos["IRPJ"] == lucro * D("0.15") + (lucro - 240_000) * D("0.10")


def test_comparativo_ordena_e_calcula_economia():
    c = comparar(servico_600k())
    totais = [r.total for r in c.aplicaveis]
    assert totais == sorted(totais)
    assert c.melhor.titulo == "Simples Nacional"
    assert c.economia_vs_pior == c.aplicaveis[-1].total - c.melhor.total


def test_simulacao_expressa_tres_entradas():
    c = simulacao_expressa(50_000, 8_000, "servico_fator_r", pro_labore_mensal=5_000)
    assert c.perfil.receita_bruta_anual == D(600_000)
    assert c.melhor.titulo == "Simples Nacional"
    assert c.alertas


def test_valores_negativos_rejeitados():
    with pytest.raises(ValueError):
        PerfilEmpresa(Atividade.COMERCIO, -1)
