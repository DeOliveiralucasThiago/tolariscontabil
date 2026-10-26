"""Enquadramento: receita separada no Anexo III (Simples) e comparação dos caminhos para sair do Anexo V."""

from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, enquadramento, simples
from tolaris_motor.comparativo import comparar

D = Decimal
HOJE = date(2026, 1, 1)


def perfil(**extra) -> PerfilEmpresa:
    # folha de 36.000 em 600.000 = fator R de 6%: Anexo V
    base = dict(atividade=Atividade.SERVICO_FATOR_R, receita_bruta_anual=600_000, pro_labore_anual=36_000,
                outras_despesas_anual=60_000)
    return PerfilEmpresa(**{**base, **extra})


def test_validacoes_da_receita_do_anexo_iii():
    with pytest.raises(ValueError, match="passar da receita"):
        perfil(receita_anexo_iii_anual=700_000)
    with pytest.raises(ValueError, match="negativo"):
        perfil(receita_anexo_iii_anual=-1)
    with pytest.raises(ValueError, match="fator R"):
        perfil(atividade=Atividade.SERVICO_ANEXO_IV, receita_anexo_iii_anual=1_000)


def test_sem_receita_separada_nada_muda():
    assert simples.calcular(perfil()).tributos["DAS"] == simples.calcular(perfil(receita_anexo_iii_anual=0)).tributos["DAS"]


def test_das_soma_cada_parte_com_a_aliquota_do_seu_anexo_sobre_o_rbt12_total():
    p = perfil(receita_anexo_iii_anual=200_000)
    das = simples.calcular(p).tributos["DAS"]
    a_v = simples.aliquota_efetiva("V", 600_000, HOJE)
    a_iii = simples.aliquota_efetiva("III", 600_000, HOJE)
    assert das == 400_000 * a_v + 200_000 * a_iii
    # fica entre o tudo-no-V e o tudo-no-III
    assert simples.calcular(perfil(receita_anexo_iii_anual=600_000)).tributos["DAS"] < das < simples.calcular(perfil()).tributos["DAS"]


def test_tudo_no_anexo_iii_igual_a_atividade_do_anexo_iii():
    tudo = simples.calcular(perfil(receita_anexo_iii_anual=600_000)).tributos["DAS"]
    puro = simples.calcular(perfil(atividade=Atividade.SERVICO_ANEXO_III)).tributos["DAS"]
    assert tudo == puro


def test_com_fator_r_acima_de_28_a_separacao_nao_muda_nada():
    alto = perfil(pro_labore_anual=200_000)
    assert simples.calcular(alto).tributos["DAS"] == simples.calcular(perfil(pro_labore_anual=200_000, receita_anexo_iii_anual=100_000)).tributos["DAS"]


def test_exportacao_proporcional_entre_as_partes():
    p = perfil(receita_anexo_iii_anual=300_000, receita_exterior_anual=600_000)
    r = simples.calcular(p)
    interno_e_exterior = [x.descricao for x in r.memoria]
    assert any(d.startswith("DAS - exportação (Anexo V") for d in interno_e_exterior)
    assert any(d.startswith("DAS - exportação (Anexo III") for d in interno_e_exterior)
    assert r.tributos["DAS"] < simples.calcular(perfil(receita_exterior_anual=600_000)).tributos["DAS"]
    assert any("exerce de fato" in a for a in r.alertas)


def test_cenarios_do_enquadramento():
    c = enquadramento.analisar(perfil())
    assert [x.chave for x in c] == ["atual", "fator_r", "anexo_iii_25", "anexo_iii_50", "anexo_iii_100"]
    assert c[0].anexos_simples == ["V"] and c[1].anexos_simples == ["III"] and c[2].anexos_simples == ["V", "III"]
    # pró-labore sobe até 28% da receita: 168.000 no total
    assert c[1].perfil.pro_labore_anual == D(168_000)
    assert simples.fator_r(simples.folha_fator_r(c[1].perfil), 600_000) == D("0.28")
    # o custo do INSS do sócio (11% até o teto) aparece à parte
    assert c[1].custo_extra_anual > 0 and c[1].melhor_total == c[1].comparativo.melhor.total + c[1].custo_extra_anual
    assert enquadramento.recomendado(c).chave == "anexo_iii_100"


def test_cenario_proprio_e_empresa_que_ja_esta_no_anexo_iii():
    c = enquadramento.analisar(perfil(), percentual_personalizado="0.3")
    assert "anexo_iii_30" in [x.chave for x in c]
    ja = enquadramento.analisar(perfil(pro_labore_anual=200_000))
    assert len(ja) == 1 and "já chega a 28%" in ja[0].observacao
    outra = enquadramento.analisar(perfil(atividade=Atividade.COMERCIO))
    assert len(outra) == 1


def test_fator_r_informado_tambem_sobe():
    c = enquadramento.analisar(perfil(folha_fator_r_anual=36_000))
    assert simples.fator_r(simples.folha_fator_r(c[1].perfil), 600_000) == D("0.28")


def test_comparativo_continua_aceitando_o_perfil_separado():
    cmp = comparar(perfil(receita_anexo_iii_anual=300_000))
    assert len(cmp.resultados) == 3
