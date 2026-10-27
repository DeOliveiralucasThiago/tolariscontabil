"""Segregações do art. 25, § 1º, da Res. CGSN 140/2018: locação de bens móveis, IPI com ISS, transporte intermunicipal e comunicação."""

from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, presumido, real, reforma_simples, simples

D = Decimal
ESPECIAIS = [Atividade.LOCACAO_BENS_MOVEIS, Atividade.INDUSTRIA_IPI_ISS, Atividade.TRANSPORTE_CARGAS_ICMS, Atividade.TRANSPORTE_PASSAGEIROS_ICMS, Atividade.COMUNICACAO_ICMS]
DATA = date(2026, 1, 1)
RBT12 = D(600_000)


def perfil(atividade, receita=600_000, **extra):
    return PerfilEmpresa(atividade, receita, folha_clt_anual=100_000, **extra)


def test_propriedades_das_atividades():
    assert all(a.tratamento_especial for a in ESPECIAIS)
    assert not any(a.tratamento_especial for a in (Atividade.COMERCIO, Atividade.SERVICO_FATOR_R))
    assert Atividade.TRANSPORTE_CARGAS_ICMS.sujeita_a_icms and not Atividade.TRANSPORTE_CARGAS_ICMS.sujeita_a_iss
    assert not Atividade.LOCACAO_BENS_MOVEIS.sujeita_a_icms and not Atividade.LOCACAO_BENS_MOVEIS.sujeita_a_iss
    assert Atividade.INDUSTRIA_IPI_ISS.sujeita_a_iss and not Atividade.INDUSTRIA_IPI_ISS.sujeita_a_icms
    assert Atividade.SERVICO_ANEXO_III.sujeita_a_iss and Atividade.COMERCIO.sujeita_a_icms
    assert not Atividade.TRANSPORTE_CARGAS_ICMS.vende_mercadoria


def test_locacao_de_bens_moveis_e_anexo_iii_sem_a_parcela_do_iss():
    aliq = simples.aliquota_efetiva("III", RBT12, DATA)
    iss = simples.partilha("III", RBT12, DATA)["iss"]
    r = simples.calcular(perfil(Atividade.LOCACAO_BENS_MOVEIS))
    assert r.tributos["DAS"] == pytest.approx(RBT12 * aliq * (1 - iss), abs=D("0.01"))
    assert r.tributos["DAS"] < simples.calcular(perfil(Atividade.SERVICO_ANEXO_III)).tributos["DAS"]
    assert any(p.descricao.startswith("Alíquota aplicada - Anexo III sem a parcela do ISS") for p in r.memoria)
    assert any("partilha ajustada" in a for a in r.alertas)


@pytest.mark.parametrize("atividade", [Atividade.TRANSPORTE_CARGAS_ICMS, Atividade.TRANSPORTE_PASSAGEIROS_ICMS, Atividade.COMUNICACAO_ICMS])
def test_transporte_intermunicipal_e_comunicacao_trocam_o_iss_pelo_icms_do_anexo_i(atividade):
    iii, i = simples.aliquota_efetiva("III", RBT12, DATA), simples.aliquota_efetiva("I", RBT12, DATA)
    iss, icms = simples.partilha("III", RBT12, DATA)["iss"], simples.partilha("I", RBT12, DATA)["icms"]
    esperado = RBT12 * (iii * (1 - iss) + i * icms)
    r = simples.calcular(perfil(atividade))
    assert r.tributos["DAS"] == pytest.approx(esperado, abs=D("0.01"))
    assert any("com a do ICMS do Anexo I" in p.descricao for p in r.memoria)


def test_industria_com_ipi_e_iss_troca_o_icms_do_anexo_ii_pelo_iss_do_anexo_iii():
    ii, iii = simples.aliquota_efetiva("II", RBT12, DATA), simples.aliquota_efetiva("III", RBT12, DATA)
    icms, iss = simples.partilha("II", RBT12, DATA)["icms"], simples.partilha("III", RBT12, DATA)["iss"]
    r = simples.calcular(perfil(Atividade.INDUSTRIA_IPI_ISS))
    assert r.tributos["DAS"] == pytest.approx(RBT12 * (ii * (1 - icms) + iii * iss), abs=D("0.01"))


def test_atividade_comum_nao_ganha_ajuste():
    r = simples.calcular(perfil(Atividade.SERVICO_ANEXO_III))
    assert r.tributos["DAS"] == pytest.approx(RBT12 * simples.aliquota_efetiva("III", RBT12, DATA), abs=D("0.01"))
    assert not any("partilha ajustada" in a for a in r.alertas)


def test_atividades_mistas_usam_a_faixa_da_receita_total_e_separam_o_ajuste():
    # transporte intermunicipal (R$ 600 mil) + serviço comum do Anexo III (R$ 600 mil): mesmo Anexo III, mas ajustes diferentes
    p = PerfilEmpresa(Atividade.TRANSPORTE_CARGAS_ICMS, 1_200_000, folha_clt_anual=100_000, receitas_outras_atividades={"servico_anexo_iii": 600_000})
    r = simples.calcular(p)
    total = D(1_200_000)
    iii, i = simples.aliquota_efetiva("III", total, DATA), simples.aliquota_efetiva("I", total, DATA)
    iss, icms = simples.partilha("III", total, DATA)["iss"], simples.partilha("I", total, DATA)["icms"]
    esperado = D(600_000) * (iii * (1 - iss) + i * icms) + D(600_000) * iii
    assert r.tributos["DAS"] == pytest.approx(esperado, abs=D("0.01"))
    assert sum(1 for x in r.memoria if x.descricao.startswith("DAS (")) == 2
    assert any("sem a parcela do ISS e com a do ICMS do Anexo I" in a for a in r.alertas)
    assert simples._partes_por_anexo(p) == [("III", D(1_200_000))]  # a receita por Anexo soma os dois ajustes


def test_tabela_de_2033_sem_icms_nem_iss_no_ajuste():
    p = PerfilEmpresa(Atividade.TRANSPORTE_CARGAS_ICMS, 600_000, folha_clt_anual=100_000, ano=2033)
    d = date(2033, 1, 1)
    assert simples.partilha("III", RBT12, d).get("iss", 0) == 0 and simples.partilha("I", RBT12, d).get("icms", 0) == 0
    assert simples.calcular(p).tributos["DAS"] == pytest.approx(RBT12 * simples.aliquota_efetiva("III", RBT12, d), abs=D("0.01"))


def test_locacao_nao_paga_iss_nem_icms_no_presumido_e_no_real():
    for calc in (presumido.calcular, real.calcular):
        r = calc(perfil(Atividade.LOCACAO_BENS_MOVEIS))
        assert "ISS" not in r.tributos and "ICMS" not in r.tributos
        assert any("Súmula Vinculante 31" in a for a in r.alertas)
    assert presumido.calcular(perfil(Atividade.LOCACAO_BENS_MOVEIS)).tributos["IRPJ"] == pytest.approx(D(600_000) * D("0.32") * D("0.15") + max(D(0), D(600_000) * D("0.32") - 240_000) * D("0.10"), abs=D("0.01"))


def test_transporte_paga_icms_e_nao_iss_com_a_presuncao_de_cada_tipo():
    carga = presumido.calcular(perfil(Atividade.TRANSPORTE_CARGAS_ICMS))
    passageiros = presumido.calcular(perfil(Atividade.TRANSPORTE_PASSAGEIROS_ICMS))
    assert "ICMS" in carga.tributos and "ISS" not in carga.tributos
    assert carga.tributos["IRPJ"] < passageiros.tributos["IRPJ"]  # 8% x 16% de presunção
    assert carga.tributos["CSLL"] == passageiros.tributos["CSLL"]  # a CSLL é 12% nos dois
    assert any("simplificada" in a for a in carga.alertas)


def test_presumido_de_2027_com_atividade_especial():
    r = presumido.calcular(perfil(Atividade.LOCACAO_BENS_MOVEIS, ano=2027))
    assert r.tributos["CBS"] > 0 and "ISS" not in r.tributos
    t = presumido.calcular(perfil(Atividade.TRANSPORTE_CARGAS_ICMS, ano=2027))
    assert t.tributos["CBS"] > 0 and t.tributos["ICMS"] > 0


def test_simples_na_reforma_avisa_da_partilha_ajustada():
    e = reforma_simples.EntradaSimplesReforma(Atividade.LOCACAO_BENS_MOVEIS, 600_000, D("0.5"), anos=[2027])
    assert any("partilha do Anexo sem o ajuste" in a for a in reforma_simples.simular(e)[0].resultado.alertas)
    comum = reforma_simples.EntradaSimplesReforma(Atividade.SERVICO_ANEXO_III, 600_000, D("0.5"), anos=[2027])
    assert not any("partilha do Anexo sem o ajuste" in a for a in reforma_simples.simular(comum)[0].resultado.alertas)
