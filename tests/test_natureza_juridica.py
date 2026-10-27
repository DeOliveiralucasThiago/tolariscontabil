"""Natureza jurídica: classificação da descrição do CNPJ e o que ela decide no Simples Nacional (LC 123/2006, art. 3º)."""

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, natureza_juridica as nj, presumido, real, simples


@pytest.mark.parametrize(
    "descricao, tipo, simples_ok",
    [
        ("Sociedade Empresária Limitada", "sociedade_empresaria", "sim"),
        ("Empresário (Individual)", "empresario_individual", "sim"),
        ("Empresa Individual de Responsabilidade Limitada (de Natureza Empresária)", "eireli", "sim"),
        ("Sociedade Simples Pura", "sociedade_simples", "sim"),
        ("Sociedade Simples Limitada", "sociedade_simples", "sim"),
        ("Sociedade Unipessoal de Advogados", "sociedade_simples", "sim"),
        ("Sociedade Limitada Unipessoal", "sociedade_empresaria", "sim"),
        ("Sociedade Anônima Fechada", "sociedade_por_acoes", "vedado"),
        ("Sociedade Anônima Aberta", "sociedade_por_acoes", "vedado"),
        ("Sociedade Empresária em Comandita por Ações", "sociedade_por_acoes", "vedado"),
        ("Cooperativa", "cooperativa", "vedado"),
        ("Cooperativa de Consumo", "cooperativa_consumo", "sim"),
        ("Associação Privada", "sem_fins_lucrativos", "nao_se_aplica"),
        ("Fundação Privada", "sem_fins_lucrativos", "nao_se_aplica"),
        ("Município", "administracao_publica", "nao_se_aplica"),
        ("Autarquia Federal", "administracao_publica", "nao_se_aplica"),
        ("Contribuinte Individual", "pessoa_fisica", "nao_se_aplica"),
        ("Estabelecimento, no Brasil, de Sociedade Estrangeira", "outra", "conferir"),
    ],
)
def test_classifica_pela_descricao(descricao, tipo, simples_ok):
    n = nj.classificar(descricao)
    assert n.tipo == tipo and n.simples == simples_ok


def test_so_o_empresario_individual_pode_ser_mei():
    assert [t for t, n in nj.NATUREZAS.items() if n.mei] == ["empresario_individual"]


def test_sem_descricao_usa_o_primeiro_digito_do_codigo():
    assert nj.classificar(None, "3999").tipo == "sem_fins_lucrativos"
    assert nj.classificar("", "1015").tipo == "administracao_publica"
    assert nj.classificar(None, "2062").tipo == "outra"  # empresarial, mas o código sozinho não diz qual: confira
    assert nj.classificar(None, None) is None and nj.classificar("  ", "") is None


def test_impede_simples():
    assert nj.impede_simples(nj.classificar("Sociedade Anônima Fechada"))
    assert nj.impede_simples(nj.classificar("Associação Privada"))
    assert not nj.impede_simples(nj.classificar("Sociedade Empresária Limitada"))
    assert not nj.impede_simples(nj.classificar("Estabelecimento de Sociedade Estrangeira"))
    assert not nj.impede_simples(None)


def perfil(natureza):
    return PerfilEmpresa(Atividade.SERVICO_ANEXO_III, 600_000, folha_clt_anual=100_000, natureza_juridica=natureza)


def test_sociedade_por_acoes_nao_pode_optar_pelo_simples_mas_tem_presumido_e_real():
    r = simples.calcular(perfil("Sociedade Anônima Fechada"))
    assert not r.aplicavel and any("art. 3º, caput e § 4º, VI e X" in a for a in r.alertas)
    assert presumido.calcular(perfil("Sociedade Anônima Fechada")).aplicavel
    assert real.calcular(perfil("Sociedade Anônima Fechada")).aplicavel


def test_limitada_e_sem_natureza_seguem_normalmente():
    for natureza in ("Sociedade Empresária Limitada", None, "Cooperativa de Consumo"):
        assert simples.calcular(perfil(natureza)).aplicavel
    assert not simples.calcular(perfil("Cooperativa")).aplicavel


def test_entidade_sem_fins_lucrativos_avisa_no_presumido_e_no_real():
    for calc in (presumido.calcular, real.calcular):
        r = calc(perfil("Associação Privada"))
        assert any("sem fins lucrativos" in a.lower() or "fins lucrativos" in a for a in r.alertas)
    assert not any("fins lucrativos" in a for a in presumido.calcular(perfil("Sociedade Empresária Limitada")).alertas)
