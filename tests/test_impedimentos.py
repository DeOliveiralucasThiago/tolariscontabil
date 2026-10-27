"""Impedimentos do Simples Nacional (LC 123/2006, art. 3º, § 4º, e art. 17)."""

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, impedimentos as imp, simples


def test_todas_as_perguntas_tem_titulo_e_base_legal():
    assert len(imp.PERGUNTAS) == 23
    assert {p.chave for p in imp.PERGUNTAS} == set(imp.TITULOS)
    assert all(p.base_legal.startswith("LC 123/2006, art.") for p in imp.PERGUNTAS)
    assert {p.chave for p in imp.PERGUNTAS if p.depende_da_receita_global} == {
        "socio_empresario_ou_socio_de_outra", "socio_mais_de_10_por_cento", "socio_administrador_de_outra"}


def test_resposta_sim_vira_impedimento_e_nao_ou_vazio_nao():
    a = imp.avaliar({"socio_exterior": True, "cisao_5_anos": False, "debito_exigivel": None})
    assert [x.chave for x in a] == ["socio_exterior"] and a[0].status == "impede" and a[0].base_legal == "LC 123/2006, art. 17, II"
    assert imp.avaliar({"chave_inexistente": True}) == []


def test_impedimentos_da_receita_global_so_valem_acima_de_r_4_8_mi():
    r = {"socio_administrador_de_outra": True}
    assert imp.avaliar(r, 1_000_000)[0].status == "depende_da_receita"      # receita das outras empresas não informada
    assert imp.avaliar(r, 1_000_000, 500_000) == []                         # R$ 1,5 mi de receita global: não impede
    assert imp.avaliar(r, 3_000_000, 1_800_000) == []                       # exatamente R$ 4,8 mi: ainda cabe no limite
    assert imp.avaliar(r, 3_000_000, 2_000_000)[0].status == "impede"       # R$ 5 mi de receita global
    assert imp.avaliar({"socio_exterior": True}, 1_000, 0)[0].status == "impede"  # os demais não dependem da receita


def test_pendentes_e_textos_que_impedem():
    r = {"socio_exterior": True, "socio_mais_de_10_por_cento": True}
    assert len(imp.pendentes(r)) == 21 and len(imp.pendentes({p.chave: False for p in imp.PERGUNTAS})) == 0
    assert imp.textos_que_impedem(imp.avaliar(r, 1_000_000)) == ["Titular ou sócio domiciliado no exterior (LC 123/2006, art. 17, II)"]


def test_simples_fica_inaplicavel_com_impedimento_confirmado():
    base = dict(atividade=Atividade.SERVICO_ANEXO_III, receita_bruta_anual=600_000, folha_clt_anual=100_000)
    assert simples.calcular(PerfilEmpresa(**base)).aplicavel
    r = simples.calcular(PerfilEmpresa(**base, impedimentos_simples=["Titular ou sócio domiciliado no exterior (LC 123/2006, art. 17, II)"]))
    assert not r.aplicavel and any("Impedimento ao Simples Nacional confirmado no cadastro" in a and "art. 17, II" in a for a in r.alertas)
