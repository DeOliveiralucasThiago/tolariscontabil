"""Receitas de mais de uma atividade: cada uma no seu Anexo do Simples, presunção própria no Presumido, ICMS e ISS por parte."""

from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, presumido, real, simples

D = Decimal


def mista(ano: int = 2026, **extra) -> PerfilEmpresa:
    """Comércio de R$ 1,2 mi + serviços do fator R de R$ 0,6 mi (fator R de 17,7%: Anexo V)."""
    base = dict(
        atividade=Atividade.COMERCIO, receita_bruta_anual=1_800_000, folha_clt_anual=240_000, pro_labore_anual=60_000,
        compras_anual=700_000, receitas_outras_atividades={"servico_fator_r": 600_000}, ano=ano,
    )
    return PerfilEmpresa(**{**base, **extra})


def test_partes_da_atividade_principal_e_das_outras():
    p = mista()
    assert p.partes_atividade == [(Atividade.COMERCIO, D(1_200_000)), (Atividade.SERVICO_FATOR_R, D(600_000))]
    assert p.tem_atividades_mistas
    assert p.receita_mercadorias_anual == D(1_200_000) and p.receita_servicos_anual == D(600_000)


def test_simples_segrega_cada_atividade_no_seu_anexo_com_a_faixa_da_receita_total():
    r = simples.calcular(mista())
    # RBT12 de R$ 1,8 mi: 4ª faixa do Anexo I (9,45%) e do Anexo V (19,55%)
    assert r.tributos["DAS"] == pytest.approx(D(1_200_000) * D("0.0945") + D(600_000) * D("0.1955"), abs=D("0.01"))
    descricoes = [p.descricao for p in r.memoria]
    assert "DAS (Anexo I, R$ 1.200.000,00)" in descricoes or any(d.startswith("DAS (Anexo I") for d in descricoes)
    assert any(d.startswith("DAS (Anexo V") for d in descricoes)
    assert any("Receita segregada por atividade" in a and "exerce de fato" in a for a in r.alertas)


def test_fator_r_da_atividade_mista_usa_a_folha_e_a_receita_totais():
    alto = simples.calcular(mista(folha_clt_anual=420_000))  # folha total / RBT12 passa de 28%: serviços no Anexo III
    assert any(p.descricao.startswith("DAS (Anexo III") for p in alto.memoria)
    assert not any(p.descricao.startswith("DAS (Anexo V") for p in alto.memoria)


def test_atividades_no_mesmo_anexo_somam_numa_parte_so():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_III, 600_000, receitas_outras_atividades={"servico_fator_r": 100_000}, folha_clt_anual=300_000)
    r = simples.calcular(p)
    assert len([x for x in r.memoria if x.descricao.startswith("DAS")]) == 1


def test_receita_anexo_iii_antiga_equivale_a_atividade_servico_anexo_iii():
    antigo = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, pro_labore_anual=36_000, receita_anexo_iii_anual=300_000)
    novo = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, pro_labore_anual=36_000, receitas_outras_atividades={"servico_anexo_iii": 300_000})
    assert simples.calcular(antigo).tributos["DAS"] == simples.calcular(novo).tributos["DAS"]
    assert antigo.partes_atividade == novo.partes_atividade


def test_anexo_iv_com_outra_atividade_estima_a_cpp_na_proporcao_da_receita():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_IV, 600_000, pro_labore_anual=36_000, folha_clt_anual=120_000,
                      receitas_outras_atividades={"comercio": 300_000})
    so_iv = PerfilEmpresa(Atividade.SERVICO_ANEXO_IV, 600_000, pro_labore_anual=36_000, folha_clt_anual=120_000)
    r, r_iv = simples.calcular(p), simples.calcular(so_iv)
    chave = "INSS patronal (fora do DAS)"
    assert r.tributos[chave] == pytest.approx(r_iv.tributos[chave] / 2, abs=D("0.01"))
    assert any("IN RFB 2.110/2022" in a and "todos os empregados como atuando nas duas atividades" in a for a in r.alertas)
    assert not any("IN RFB 2.110/2022" in a for a in r_iv.alertas)


def test_cpp_do_anexo_iv_usa_a_divisao_da_folha_por_atividade():
    base = dict(atividade=Atividade.SERVICO_ANEXO_IV, receita_bruta_anual=600_000, folha_clt_anual=120_000,
                receitas_outras_atividades={"comercio": 300_000})  # metade da receita no Anexo IV
    chave = "INSS patronal (fora do DAS)"
    cheia = 120_000 * (D("0.20") + D("0.02"))
    # 50% da folha só do Anexo IV, 25% só das outras, 25% nas duas atividades: 0,50 + 0,25 x 1/2
    r = simples.calcular(PerfilEmpresa(**base, folha_so_anexo_iv_pct="0.5", folha_so_outros_anexos_pct="0.25"))
    assert r.tributos[chave] == pytest.approx(cheia * (D("0.5") + D("0.25") * D("0.5")), abs=D("0.01"))
    assert any("divisão da folha informada" in a for a in r.alertas)
    # folha só nas outras atividades: nenhuma CPP fora do DAS
    r = simples.calcular(PerfilEmpresa(**base, folha_so_outros_anexos_pct=1))
    assert r.tributos[chave] == 0
    with pytest.raises(ValueError, match="não pode passar de 100%"):
        PerfilEmpresa(**base, folha_so_anexo_iv_pct="0.7", folha_so_outros_anexos_pct="0.5")


def test_exportacao_de_atividade_mista_usa_os_tributos_de_cada_anexo():
    r = simples.calcular(mista(receita_exterior_anual=300_000))
    assert any(p.descricao.startswith("DAS - exportação (Anexo I") and "ICMS" in p.formula for p in r.memoria)
    assert any(p.descricao.startswith("DAS - exportação (Anexo V") and "ISS" in p.formula and "ICMS" not in p.formula for p in r.memoria)
    assert any("repartida entre as atividades" in a for a in r.alertas)


def test_presumido_usa_a_presuncao_de_cada_atividade():
    r = presumido.calcular(mista())
    # IRPJ: 1,2 mi x 8% + 0,6 mi x 32% = R$ 288.000 de base; 15% + adicional de 10% acima de R$ 240.000/ano
    base = D(1_200_000) * D("0.08") + D(600_000) * D("0.32")
    assert r.tributos["IRPJ"] == pytest.approx(base * D("0.15") + (base - 240_000) * D("0.10"), abs=D("0.01"))
    # CSLL: 1,2 mi x 12% + 0,6 mi x 32%
    assert r.tributos["CSLL"] == pytest.approx((D(1_200_000) * D("0.12") + D(600_000) * D("0.32")) * D("0.09"), abs=D("0.01"))
    assert any(p.descricao.startswith("Percentuais de presunção (atividades mistas") for p in r.memoria)


def test_icms_so_sobre_mercadorias_e_iss_so_sobre_servicos():
    for calc in (presumido.calcular, real.calcular):
        t = calc(mista()).tributos
        # compras de R$ 700.000 geram crédito de ICMS de 18%
        assert t["ICMS"] == pytest.approx(D(1_200_000) * D("0.18") - D(700_000) * D("0.18"), abs=D("0.01"))
        assert t["ISS"] == pytest.approx(D(600_000) * D("0.05"), abs=D("0.01"))


def test_presumido_de_2027_com_atividade_mista_tem_cbs_ibs_e_icms_iss_por_parte():
    r = presumido.calcular(mista(2027))
    assert "PIS" not in r.tributos and r.tributos["CBS"] > 0 and r.tributos["IBS"] > 0
    assert r.tributos["ICMS"] > 0 and r.tributos["ISS"] > 0
    # vendas sem tributos: comércio 1,2 mi x (1 - 3,65% - 18%) + serviços 0,6 mi x (1 - 3,65% - 5%)
    base = D(1_200_000) * (1 - D("0.0365") - D("0.18")) + D(600_000) * (1 - D("0.0365") - D("0.05"))
    credito = (D(700_000) * (1 - D("0.0925") - D("0.18"))) * (D("0.088") - D("0.001"))
    assert r.tributos["CBS"] == pytest.approx(base * (D("0.088") - D("0.001")) - credito, abs=D("0.5"))


def test_reducao_de_ibs_cbs_vale_so_para_a_atividade_principal_na_mista():
    cheia = presumido.calcular(mista(2027, atividade=Atividade.SERVICO_FATOR_R, receitas_outras_atividades={"comercio": 600_000}))
    reduzida = presumido.calcular(
        mista(2027, atividade=Atividade.SERVICO_FATOR_R, receitas_outras_atividades={"comercio": 600_000}, reducao_ibs_cbs="0.3")
    )
    pc = D("0.0365")
    base_serv, base_merc = D(1_200_000) * (1 - pc - D("0.05")), D(600_000) * (1 - pc - D("0.18"))
    aliq = D("0.088") - D("0.001")
    credito = D(700_000) * (1 - D("0.0925") - D("0.18")) * aliq
    parte_principal = base_serv / (base_serv + base_merc)
    assert reduzida.tributos["CBS"] == pytest.approx((base_serv + base_merc) * (1 - D("0.3") * parte_principal) * aliq - credito, abs=D("0.5"))
    assert cheia.tributos["CBS"] == pytest.approx((base_serv + base_merc) * aliq - credito, abs=D("0.5"))
    assert any("só à receita da atividade principal" in a for a in reduzida.alertas)


def test_atividade_unica_nao_muda():
    p = PerfilEmpresa(Atividade.COMERCIO, 1_200_000, compras_anual=700_000)
    assert not p.tem_atividades_mistas and p.partes_atividade == [(Atividade.COMERCIO, D(1_200_000))]
    assert "ISS" not in presumido.calcular(p).tributos


@pytest.mark.parametrize(
    "outras, msg",
    [
        ({"comercio": 100}, "própria atividade principal"),
        ({"servico_fator_r": -1}, "negativa"),
        ({"servico_fator_r": 1_300_000}, "não pode passar da receita bruta"),
        ({"padaria": 100}, "is not a valid"),
    ],
)
def test_validacoes(outras, msg):
    with pytest.raises(ValueError, match=msg):
        PerfilEmpresa(Atividade.COMERCIO, 1_200_000, receitas_outras_atividades=outras)


def test_enquadramento_de_empresa_mista_com_servico_do_fator_r():
    from tolaris_motor import enquadramento

    cenarios = enquadramento.analisar(mista())
    assert [c.chave for c in cenarios] == ["atual", "fator_r", "anexo_iii_25", "anexo_iii_50", "anexo_iii_100"]
    assert cenarios[0].anexos_simples == ["I", "V"]
    todo = cenarios[-1]
    # 100% da receita de serviços (R$ 600 mil) passa para o Anexo III; o comércio continua no Anexo I
    assert todo.perfil.receitas_outras_atividades == {Atividade.SERVICO_ANEXO_III: D(600_000)}
    assert todo.anexos_simples == ["I", "III"]
    assert todo.perfil.receita_bruta_anual == D(1_800_000)
    assert "de serviços do fator R" in todo.descricao
    assert todo.comparativo.resultados[0].tributos["DAS"] < cenarios[0].comparativo.resultados[0].tributos["DAS"]


def test_enquadramento_sem_servico_do_fator_r_so_traz_o_cenario_atual():
    from tolaris_motor import enquadramento

    p = PerfilEmpresa(Atividade.COMERCIO, 1_200_000, receitas_outras_atividades={"servico_anexo_iii": 200_000})
    assert [c.chave for c in enquadramento.analisar(p)] == ["atual"]
