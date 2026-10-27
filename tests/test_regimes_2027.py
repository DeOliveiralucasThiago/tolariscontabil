"""Lucro Presumido e Lucro Real a partir de 2027: CBS e IBS no lugar de PIS e Cofins, ICMS/ISS em transição."""

from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, comparativo, presumido, real

D = Decimal
CBS_2027 = D("0.088") - D("0.001")  # alíquota de referência estimada menos 0,1 ponto do ano de transição
IBS_2027 = D("0.001")


def perfil(ano: int, **extra) -> PerfilEmpresa:
    base = dict(atividade=Atividade.SERVICO_ANEXO_III, receita_bruta_anual=600_000, folha_clt_anual=100_000, ano=ano)
    return PerfilEmpresa(**{**base, **extra})


def test_2026_continua_com_pis_e_cofins():
    for calc in (presumido.calcular, real.calcular):
        r = calc(perfil(2026))
        assert "PIS" in r.tributos and "Cofins" in r.tributos
        assert "CBS" not in r.tributos and "IBS" not in r.tributos


@pytest.mark.parametrize("calc", [presumido.calcular, real.calcular])
def test_2027_troca_pis_cofins_por_cbs_e_ibs(calc):
    r = calc(perfil(2027))
    assert "PIS" not in r.tributos and "Cofins" not in r.tributos
    assert r.tributos["CBS"] > 0 and r.tributos["IBS"] > 0
    assert any("CBS e IBS" in a and "alíquotas de referência" in a.lower() for a in r.alertas)


def test_presumido_servico_2027_cbs_e_ibs_sobre_vendas_sem_tributos():
    # Serviço sem compras: base = 600.000 x (1 - 3,65% de PIS/Cofins - 5% de ISS); sem crédito
    base = D(600_000) * (1 - D("0.0365") - D("0.05"))
    r = presumido.calcular(perfil(2027))
    assert r.tributos["CBS"] == pytest.approx(base * CBS_2027, abs=D("0.01"))
    assert r.tributos["IBS"] == pytest.approx(base * IBS_2027, abs=D("0.01"))
    assert r.tributos["ISS"] == D(600_000) * D("0.05")


def test_presumido_2027_irpj_e_csll_sobre_receita_sem_pis_cofins():
    antes = presumido.calcular(perfil(2026))
    depois = presumido.calcular(perfil(2027))
    # a receita da base cai 3,65% (PIS/Cofins que saiu do preço): IRPJ e CSLL caem na mesma proporção
    fator = 1 - D("0.0365")
    assert depois.tributos["CSLL"] == pytest.approx(antes.tributos["CSLL"] * fator, abs=D("0.01"))
    assert any(p.descricao == "Receita para IRPJ e CSLL" for p in depois.memoria)


def test_cbs_ibs_pagos_a_mais_que_pis_cofins_no_presumido_de_servicos():
    # Serviços no Presumido: PIS/Cofins cumulativos (3,65%) viram CBS/IBS não cumulativos (8,8%) com pouco crédito
    r26, r27 = presumido.calcular(perfil(2026)), presumido.calcular(perfil(2027))
    assert r27.total > r26.total


def test_real_comercio_2027_credito_de_cbs_ibs_reduz_o_pagamento():
    sem = real.calcular(perfil(2027, atividade=Atividade.COMERCIO, folha_clt_anual=50_000))
    com = real.calcular(perfil(2027, atividade=Atividade.COMERCIO, folha_clt_anual=50_000, compras_anual=300_000))
    assert com.tributos["CBS"] < sem.tributos["CBS"]
    # o crédito aproveitado abate o custo: o lucro e o IRPJ não podem subir por causa do crédito
    assert com.tributos["IRPJ"] <= sem.tributos["IRPJ"]


def test_real_nao_deduz_cbs_ibs_no_lucro():
    r = real.calcular(perfil(2027))
    lucro = next(p for p in r.memoria if p.descricao == "Lucro antes do IRPJ/CSLL")
    deduz = sum(v for k, v in r.tributos.items() if k in ("ISS", "INSS patronal"))
    esperado = D(600_000) * (1 - D("0.0925")) - D(100_000) * D("1.08") - deduz
    assert lucro.valor == pytest.approx(esperado, abs=D("0.01"))


@pytest.mark.parametrize("ano, fracao", [(2027, "1"), (2028, "1"), (2029, "0.9"), (2030, "0.8"), (2031, "0.7"), (2032, "0.6"), (2033, "0")])
def test_iss_em_transicao(ano, fracao):
    r = presumido.calcular(perfil(ano))
    assert r.tributos["ISS"] == pytest.approx(D(30_000) * D(fracao), abs=D("0.01"))


def test_icms_em_transicao_no_comercio():
    cheio = presumido.calcular(perfil(2028, atividade=Atividade.COMERCIO, compras_anual=200_000)).tributos["ICMS"]
    r2030 = presumido.calcular(perfil(2030, atividade=Atividade.COMERCIO, compras_anual=200_000)).tributos["ICMS"]
    r2033 = presumido.calcular(perfil(2033, atividade=Atividade.COMERCIO, compras_anual=200_000)).tributos["ICMS"]
    assert r2030 == pytest.approx(cheio * D("0.8"), abs=D("0.01"))
    assert r2033 == 0


def test_ibs_cresce_enquanto_icms_iss_diminuem():
    ibs = [presumido.calcular(perfil(a)).tributos["IBS"] for a in range(2027, 2034)]
    assert ibs == sorted(ibs) and ibs[-1] > ibs[0] * 10


@pytest.mark.parametrize("reducao", ["0.3", "0.6"])
def test_reducao_de_aliquota_de_ibs_e_cbs(reducao):
    cheia = presumido.calcular(perfil(2027))
    reduzida = presumido.calcular(perfil(2027, reducao_ibs_cbs=reducao))
    for t in ("CBS", "IBS"):
        assert reduzida.tributos[t] == pytest.approx(cheia.tributos[t] * (1 - D(reducao)), abs=D("0.01"))
    assert any("Redução de" in a for a in reduzida.alertas)


def test_reducao_invalida_e_rejeitada():
    with pytest.raises(ValueError, match="reducao_ibs_cbs"):
        perfil(2027, reducao_ibs_cbs="0.5")


def test_sociedade_de_profissionais_sem_reducao_recebe_aviso():
    r = presumido.calcular(
        perfil(2027, sociedade_profissionais=True, profissionais=2, iss_fixo_por_profissional_anual=1500)
    )
    assert any("Sem redução de alíquota" in a for a in r.alertas)
    assert any("não traz regra própria para o ISS" in a for a in r.alertas)
    assert r.tributos["ISS"] == D(3000)


def test_exportacao_nao_paga_cbs_nem_ibs_sobre_a_parte_do_exterior():
    so_interno = presumido.calcular(perfil(2027, receita_bruta_anual=300_000))
    com_exportacao = presumido.calcular(perfil(2027, receita_bruta_anual=600_000, receita_exterior_anual=300_000))
    assert com_exportacao.tributos["CBS"] == pytest.approx(so_interno.tributos["CBS"], abs=D("0.01"))


def test_saldo_credor_de_cbs_avisa_no_real():
    r = real.calcular(perfil(2027, atividade=Atividade.COMERCIO, receita_bruta_anual=100_000, compras_anual=400_000))
    assert r.tributos["CBS"] == 0
    assert any("créditos superam débitos" in a for a in r.alertas)


def test_comparativo_de_2027_traz_os_tres_regimes():
    c = comparativo.simulacao_expressa(50_000, 10_000, "servico_fator_r", 5_000, ano=2027)
    nomes = {r.titulo: r for r in c.resultados}
    assert "CBS" in nomes["Lucro Presumido"].tributos and "CBS" in nomes["Lucro Real"].tributos
    assert "DAS" in nomes["Simples Nacional"].tributos
    assert c.melhor.titulo == "Simples Nacional"


def test_simulacao_expressa_aceita_reducao():
    cheia = comparativo.simulacao_expressa(50_000, 10_000, "servico_fator_r", 5_000, ano=2027)
    reduzida = comparativo.simulacao_expressa(50_000, 10_000, "servico_fator_r", 5_000, ano=2027, reducao_ibs_cbs="0.3")
    assert reduzida.resultados[1].total < cheia.resultados[1].total
