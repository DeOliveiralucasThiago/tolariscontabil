"""Tabelas do Simples de 2027 a 2033 (Res. CGSN 190/2026): CBS e IBS na partilha do DAS."""

from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, recuperacao, simples, tabelas
from tolaris_motor.reforma_simples import EntradaSimplesReforma, simular

D = Decimal
ANEXOS = ("I", "II", "III", "IV", "V")
INICIOS = (2027, 2029, 2030, 2031, 2032, 2033)


def perfil(ano: int, **extra) -> PerfilEmpresa:
    base = dict(atividade=Atividade.SERVICO_ANEXO_III, receita_bruta_anual=600_000, folha_clt_anual=100_000, ano=ano)
    return PerfilEmpresa(**{**base, **extra})


@pytest.mark.parametrize("ano", INICIOS)
@pytest.mark.parametrize("anexo", ANEXOS)
def test_partilha_de_cada_faixa_soma_100_por_cento(ano, anexo):
    tab = tabelas.vigente("simples_nacional", date(ano, 1, 1))
    for i, f in enumerate(tab["anexos"][anexo]["faixas"], start=1):
        assert sum(D(v) for v in f["partilha"].values()) == pytest.approx(D(1), abs=D("0.0002")), (anexo, ano, i)


@pytest.mark.parametrize("ano", INICIOS)
@pytest.mark.parametrize("anexo", ANEXOS)
def test_cbs_mais_ibs_ocupam_a_fatia_de_pis_cofins_icms_e_iss(ano, anexo):
    # Res. CGSN 190/2026: em cada faixa, CBS + IBS = PIS + Cofins + ICMS + ISS da tabela de 2026 (6ª faixa: só os tributos que ela tem)
    antiga = tabelas.vigente("simples_nacional", date(2026, 1, 1))["anexos"][anexo]["faixas"]
    nova = tabelas.vigente("simples_nacional", date(ano, 1, 1))["anexos"][anexo]["faixas"]
    for i, (a, n) in enumerate(zip(antiga[:5], nova[:5]), start=1):
        antes = sum(D(a["partilha"].get(t, "0")) for t in ("pis", "cofins", "icms", "iss"))
        depois = sum(D(n["partilha"].get(t, "0")) for t in ("cbs", "ibs", "icms", "iss"))
        assert depois == pytest.approx(antes, abs=D("0.0002")), (anexo, ano, i)
        assert "pis" not in n["partilha"] and "cofins" not in n["partilha"]


def test_das_de_2027_igual_ao_de_2026_nas_cinco_primeiras_faixas():
    for anexo in ANEXOS:
        for rbt12 in (150_000, 300_000, 600_000, 1_500_000, 3_000_000):
            assert simples.aliquota_efetiva(anexo, rbt12, date(2027, 1, 1)) == simples.aliquota_efetiva(anexo, rbt12, date(2026, 1, 1))


def test_sexta_faixa_muda_em_2027_e_em_2029():
    # Anexo I: 6ª faixa de 18,90% em 2027 (19,00% antes); Anexo III: 32,90% em 2027-28 e 33,00% de 2029 em diante
    assert D(simples.faixa("I", 4_000_000, date(2026, 1, 1))[1]["aliquota"]) == D("0.19")
    assert D(simples.faixa("I", 4_000_000, date(2027, 1, 1))[1]["aliquota"]) == D("0.189")
    assert D(simples.faixa("III", 4_000_000, date(2028, 1, 1))[1]["aliquota"]) == D("0.329")
    assert D(simples.faixa("III", 4_000_000, date(2029, 1, 1))[1]["aliquota"]) == D("0.33")
    assert D(simples.faixa("III", 4_000_000, date(2033, 1, 1))[1]["aliquota"]) == D("0.33")


def test_partilha_de_2027_traz_cbs_e_ibs():
    f = simples.partilha("I", 150_000, date(2027, 1, 1))
    assert f["cbs"] == D("0.1533") and f["ibs"] == D("0.0017") and f["icms"] == D("0.34")
    assert "pis" not in f
    # Indústria: o IPI permanece até 2033
    assert simples.partilha("II", 150_000, date(2033, 1, 1))["ipi"] == D("0.075")


def test_iss_sai_do_das_em_2033():
    f = simples.partilha("III", 150_000, date(2033, 1, 1))
    assert "iss" not in f and f["ibs"] == D("0.335") and f["cbs"] == D("0.156")


@pytest.mark.parametrize("ano, teto", [(2027, "0.05"), (2028, "0.05"), (2029, "0.045"), (2030, "0.04"), (2031, "0.035"), (2032, "0.03")])
def test_teto_do_iss_cai_a_cada_ano(ano, teto):
    # Anexo III, 5ª faixa, RBT12 de R$ 3,0 mi: alíquota efetiva acima de 14,92537%, então o ISS fica no teto
    data = date(ano, 1, 1)
    aliq = simples.aliquota_efetiva("III", 3_000_000, data)
    assert aliq > D("0.1492537")
    f = simples.partilha("III", 3_000_000, data)
    assert aliq * f["iss"] == pytest.approx(D(teto), abs=D("0.000001"))
    assert sum(f.values()) == pytest.approx(D(1), abs=D("0.0000001"))
    assert f["ibs"] > 0  # o excesso do ISS também vai para o IBS


def test_excesso_do_iss_em_2027_segue_a_tabela_da_resolucao():
    # Res. CGSN 190, Anexo III, 5ª faixa com alíquota efetiva acima de 14,92537%: IRPJ 6,02%, CSLL 5,26%, CBS 23,20%, CPP 65,26%, IBS 0,26%
    aliq = simples.aliquota_efetiva("III", 3_000_000, date(2027, 1, 1))
    f = simples.partilha("III", 3_000_000, date(2027, 1, 1))
    resto = aliq - D("0.05")
    assert f["irpj"] * aliq == pytest.approx(resto * D("0.0602"), abs=D("0.00002"))
    assert f["cbs"] * aliq == pytest.approx(resto * D("0.2320"), abs=D("0.00002"))
    assert f["cpp"] * aliq == pytest.approx(resto * D("0.6526"), abs=D("0.00002"))
    assert f["ibs"] * aliq == pytest.approx(resto * D("0.0026"), abs=D("0.00002"))


def test_calculo_de_2027_mantem_o_das_e_avisa_da_tabela_nova():
    r26 = simples.calcular(perfil(2026))
    r27 = simples.calcular(perfil(2027))
    assert r27.tributos["DAS"] == r26.tributos["DAS"]
    assert any("Res. CGSN 190/2026" in a for a in r27.alertas)
    assert not any("Res. CGSN 190/2026" in a for a in r26.alertas)


def test_exportacao_em_2027_desconsidera_cbs_ibs_e_iss():
    r26 = simples.calcular(perfil(2026, receita_exterior_anual=300_000))
    r27 = simples.calcular(perfil(2027, receita_exterior_anual=300_000))
    # PIS+Cofins+ISS de 2026 equivalem a CBS+IBS+ISS de 2027: o DAS é o mesmo
    assert r27.tributos["DAS"] == pytest.approx(r26.tributos["DAS"], abs=D("1"))
    passo = next(p for p in r27.memoria if p.descricao.startswith("DAS - exportação"))
    assert "CBS/IBS/ISS" in passo.formula
    assert any("art. 18, §§ 14 e 14-A" in a for a in r27.alertas)


def test_exportacao_de_mercadorias_em_2027_desconsidera_icms_e_ipi():
    r = simples.calcular(perfil(2027, atividade=Atividade.INDUSTRIA, receita_exterior_anual=300_000))
    passo = next(p for p in r.memoria if p.descricao.startswith("DAS - exportação"))
    assert "CBS/IBS/ICMS/IPI" in passo.formula


def test_simples_na_reforma_usa_a_tabela_de_cada_ano():
    entrada = EntradaSimplesReforma(Atividade.COMERCIO, 600_000, D("0.5"), anos=list(range(2027, 2034)))
    cenarios = simular(entrada)
    assert [c.ano for c in cenarios] == list(range(2027, 2034))
    s_por_ano = {}
    for c in cenarios:
        passo = next(p for p in c.resultado.memoria if p.descricao.startswith("Alíquota da fatia"))
        s_por_ano[c.ano] = passo.valor
        assert "CBS" in passo.formula
    # Anexo I, 3ª faixa: CBS 15,33% + IBS 0,17% em 2027; CBS 15,50% + IBS 3,35% em 2029
    assert s_por_ano[2027] == D("0.1550")
    assert s_por_ano[2029] == D("0.1885")
    assert s_por_ano[2033] > s_por_ano[2030] > s_por_ano[2029]


def test_simples_na_reforma_avisa_da_sexta_faixa():
    entrada = EntradaSimplesReforma(Atividade.COMERCIO, 4_000_000, D("0.5"), anos=[2027])
    assert any("6ª faixa" in a for a in simular(entrada)[0].resultado.alertas)


def _meses(ano: int, n: int, receita: int, **ultimo) -> list[recuperacao.MesBase]:
    lista = []
    for i in range(n):
        indice = ano * 12 + i
        extra = ultimo if i == n - 1 else {}
        lista.append(recuperacao.MesBase(f"{indice // 12:04d}-{indice % 12 + 1:02d}", D(receita), **{k: D(v) for k, v in extra.items()}))
    return lista


def test_recuperacao_em_2027_nao_tem_pis_cofins_mas_mantem_icms():
    # 13 meses a partir de 2026-01: o último é 2027-01
    r = recuperacao.estimar(_meses(2026, 13, 100_000, mono_ncm=10_000, st_nota=20_000))
    jan = r.meses[-1]
    assert jan.competencia == "2027-01" and jan.calculado
    assert jan.pis_cofins == 0
    assert jan.icms > 0
    assert any("CBS e IBS no lugar de PIS e Cofins" in a for a in r.resultado.alertas)
