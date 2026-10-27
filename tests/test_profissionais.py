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
