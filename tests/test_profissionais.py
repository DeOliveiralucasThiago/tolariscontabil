"""Sociedades de profissionais (ISS fixo) e serviços hospitalares (presunção reduzida)."""

from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, presumido, real, simples
from tolaris_motor.comparativo import comparar

D = Decimal


def advocacia(**extra) -> PerfilEmpresa:
    base = dict(atividade=Atividade.SERVICO_ANEXO_IV, receita_bruta_anual=600_000, pro_labore_anual=36_000, outras_despesas_anual=60_000)
    return PerfilEmpresa(**{**base, **extra})


FIXO = dict(sociedade_profissionais=True, profissionais=3, iss_fixo_por_profissional_anual=1_800)


def test_iss_fixo_substitui_o_percentual_no_presumido_e_no_real():
    normal, fixo = advocacia(), advocacia(**FIXO)
    for mod in (presumido, real):
        a, b = mod.calcular(normal), mod.calcular(fixo)
        assert a.tributos["ISS"] == D(30_000)          # 5% de R$ 600.000
        assert b.tributos["ISS"] == D(5_400)           # 3 profissionais x R$ 1.800
        passo = next(p for p in b.memoria if p.descricao.startswith("ISS fixo"))
        assert "3 profissional(is) x R$ 1.800,00/ano" in passo.formula and "Decreto-Lei 406/1968" in passo.base_legal
        assert any("Confirme o enquadramento" in x for x in b.alertas)
    assert presumido.calcular(normal).total - presumido.calcular(fixo).total == D(24_600)


def test_iss_fixo_independe_da_receita():
    for receita in (300_000, 600_000, 1_200_000):
        assert presumido.calcular(advocacia(receita_bruta_anual=receita, **FIXO)).tributos["ISS"] == D(5_400)


def test_simples_ignora_o_iss_fixo_e_avisa():
    normal, fixo = simples.calcular(advocacia()), simples.calcular(advocacia(**FIXO))
    assert normal.tributos == fixo.tributos   # o DAS não muda: o ISS fica dentro dele
    assert any("art. 18, § 22-A" in a and "escritório de serviços contábeis" in a for a in fixo.alertas)
    assert not any("22-A" in a for a in normal.alertas)


def test_iss_fixo_pode_mudar_o_melhor_regime():
    # No Presumido com ISS de 5% o Simples (Anexo IV) ganha; o ISS fixo aproxima os dois, mas o Presumido segue acima do Simples aqui
    c_normal, c_fixo = comparar(advocacia()), comparar(advocacia(**FIXO))
    p_normal = next(r for r in c_normal.resultados if r.titulo == "Lucro Presumido").total
    p_fixo = next(r for r in c_fixo.resultados if r.titulo == "Lucro Presumido").total
    assert p_fixo < p_normal
    assert c_fixo.melhor.titulo == "Simples Nacional"


@pytest.mark.parametrize("extra, mensagem", [
    (dict(sociedade_profissionais=True), "quantidade de profissionais"),
    (dict(sociedade_profissionais=True, profissionais=2), "quantidade de profissionais"),
    (dict(sociedade_profissionais=True, iss_fixo_por_profissional_anual=1000), "quantidade de profissionais"),
    (dict(profissionais=-1), "negativos"),
])
def test_validacoes_do_iss_fixo(extra, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        advocacia(**extra)


def test_iss_fixo_e_hospitalar_so_para_servicos():
    with pytest.raises(ValueError, match="só se aplica a serviços"):
        PerfilEmpresa(Atividade.COMERCIO, 600_000, **FIXO)
    with pytest.raises(ValueError, match="só se aplica a serviços"):
        PerfilEmpresa(Atividade.COMERCIO, 600_000, servicos_hospitalares=True)


def test_servicos_hospitalares_usam_presuncao_de_8_e_12():
    geral = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 1_200_000, folha_clt_anual=300_000, pro_labore_anual=60_000)
    hosp = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 1_200_000, folha_clt_anual=300_000, pro_labore_anual=60_000, servicos_hospitalares=True)
    assert geral.presuncao == "servicos_gerais" and hosp.presuncao == "servicos_hospitalares"
    pg, ph = presumido.calcular(geral), presumido.calcular(hosp)
    assert pg.tributos["IRPJ"] > ph.tributos["IRPJ"] and pg.tributos["CSLL"] > ph.tributos["CSLL"]
    assert ph.tributos["IRPJ"] == D(14_400)      # 8% de R$ 1,2 mi x 15% (abaixo do limite do adicional)
    assert ph.tributos["CSLL"] == D(12_960)      # 12% de R$ 1,2 mi x 9%
    assert any("Anvisa" in a and "art. 15, § 1º, III, a" in a for a in ph.alertas)
    assert not any("Anvisa" in a for a in pg.alertas)
    assert any("não muda o cálculo do Simples" in a for a in simples.calcular(hosp).alertas)


def test_presuncao_informada_vence_a_hospitalar():
    p = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, servicos_hospitalares=True, presuncao="servicos_gerais")
    assert p.presuncao == "servicos_gerais"


# --- Escritório de serviços contábeis: ISS fixo também no Simples (LC 123, art. 18, § 22-A; Res. CGSN 140, arts. 25 e 34) ---
def contabil(**extra) -> PerfilEmpresa:
    base = dict(atividade=Atividade.SERVICO_ANEXO_III, receita_bruta_anual=600_000, pro_labore_anual=36_000, outras_despesas_anual=60_000,
                sociedade_profissionais=True, profissionais=2, iss_fixo_por_profissional_anual=1_500)
    return PerfilEmpresa(**{**base, **extra})


def test_iss_fixo_do_contabil_tira_a_parcela_do_iss_do_das():
    com, sem = simples.calcular(contabil(iss_fixo_no_simples=True)), simples.calcular(contabil())
    # Anexo III, 3ª faixa: alíquota efetiva de 10,56% (R$ 63.360) e ISS de 32,5% da partilha (R$ 20.592): DAS sem ISS = R$ 42.768
    assert sem.tributos == {"DAS": D(63_360)}
    assert com.tributos["DAS"] == D(42_768)
    assert com.tributos["ISS fixo (recolhido ao Município, fora do DAS)"] == D(3_000)   # 2 x R$ 1.500
    assert com.total == D(45_768) and com.total < sem.total
    passo = next(p for p in com.memoria if p.descricao == "DAS anual")
    assert "32,50% de ISS da partilha da faixa" in passo.formula and "art. 25, § 1º, VIII" in passo.base_legal
    assert any("art. 34" in a and "art. 25, § 11" in a for a in com.alertas)
    assert not any("recolhe o ISS fixo também no Simples" in a for a in com.alertas)


def test_iss_fixo_do_contabil_com_o_teto_do_iss_na_5a_faixa():
    # RBT12 de R$ 3,0 mi: alíquota efetiva de 16,812%; o ISS efetivo fica em 5% (teto), então o DAS sem ISS é 11,812% da receita
    r = simples.calcular(contabil(receita_bruta_anual=3_000_000, iss_fixo_no_simples=True))
    assert r.tributos["DAS"] == D(354_360)
    assert simples.calcular(contabil(receita_bruta_anual=3_000_000)).tributos["DAS"] == D(504_360)


def test_sem_a_opcao_o_simples_avisa_da_excecao_do_contabil():
    r = simples.calcular(contabil())
    assert any("recolhe o ISS fixo também no Simples" in a and "art. 18, § 22-A" in a for a in r.alertas)


def test_presumido_e_real_do_contabil_usam_o_mesmo_iss_fixo():
    for mod in (presumido, real):
        assert mod.calcular(contabil(iss_fixo_no_simples=True)).tributos["ISS"] == D(3_000)


def test_comparativo_do_contabil_com_iss_fixo():
    c = comparar(contabil(iss_fixo_no_simples=True))
    totais = {r.titulo: r.total for r in c.resultados}
    assert totais["Simples Nacional"] == D(45_768) and c.melhor.titulo == "Simples Nacional"


@pytest.mark.parametrize("extra", [
    dict(iss_fixo_no_simples=True, sociedade_profissionais=False),
    dict(iss_fixo_no_simples=True, atividade=Atividade.SERVICO_ANEXO_IV),
    dict(iss_fixo_no_simples=True, atividade=Atividade.SERVICO_FATOR_R),
])
def test_iss_fixo_no_simples_so_para_o_contabil(extra):
    with pytest.raises(ValueError, match="escritório de serviços contábeis"):
        contabil(**extra)
