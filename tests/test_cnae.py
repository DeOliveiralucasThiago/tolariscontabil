"""Catálogo de CNAEs (IBGE), vedações da Res. CGSN 140/2018 e Anexo provável de cada código."""

from tolaris_motor import Atividade, cnae


def test_catalogo_completo_do_ibge():
    dados = cnae._dados()
    assert len(dados["subclasses"]) >= 1331 and len(dados["divisoes"]) == 87 and len(dados["secoes"]) == 21
    assert dados["subclasses"]["6201501"] == "Desenvolvimento de programas de computador sob encomenda"
    assert dados["subclasses"]["9900800"].startswith("Organismos internacionais")  # só aparece como classe na planilha do IBGE
    assert set(dados["vedacao"]) <= set(dados["subclasses"])  # toda vedação aponta para um CNAE que existe
    assert set(dados["anexos"]) <= set(dados["subclasses"])
    assert "contabilizei" in dados["fontes"]["anexos"].lower() and dados["atualizado_em"]


def test_normaliza_codigos():
    assert cnae.normalizar("6201-5/01") == "6201501" and cnae.normalizar("6201501") == "6201501"
    assert cnae.normalizar("") is None and cnae.normalizar("12345678") is None
    assert cnae.formatar("6201501") == "6201-5/01"


def test_vedados_e_ambiguos_vem_dos_anexos_vi_e_vii():
    banco = cnae.classificar("6421200")
    assert banco.vedacao == "impeditivo" and banco.atividade is None and banco.confianca == "oficial" and banco.rotulo == "Vedado ao Simples"
    assert "Anexo VI" in banco.motivo
    cerveja = cnae.classificar("1113502")
    assert cerveja.vedacao == "ambiguo" and "Anexo VII" in cerveja.motivo
    # o ambíguo ainda é classificado (pode optar, dependendo do que a empresa faz)
    assert cnae.classificar("4924800").vedacao == "ambiguo"


def test_anexo_pela_tabela():
    assert cnae.classificar("6201501").atividade is Atividade.SERVICO_FATOR_R
    assert cnae.classificar("6201501").anexos == ("III", "V") and cnae.classificar("6201501").confianca == "tabela"
    assert cnae.classificar("8599604").atividade is Atividade.SERVICO_ANEXO_III  # treinamento: Anexo III direto
    assert cnae.classificar("6911701").atividade is Atividade.SERVICO_ANEXO_IV
    assert cnae.classificar("4711302").atividade is Atividade.COMERCIO
    assert cnae.classificar("7319002").atividade is Atividade.SERVICO_ANEXO_III  # a regra por divisão errava este
    assert cnae.classificar("3312102").atividade is Atividade.SERVICO_ANEXO_III  # manutenção, não indústria
    # sem enquadramento automático quando a tabela traz dois Anexos que dependem da atividade
    design = cnae.classificar("7410202")
    assert design.atividade is None and design.anexos == ("IV", "V") and "depende" in design.rotulo


def test_cnae_fora_da_tabela_usa_a_regra_por_divisao():
    c = cnae.classificar("1091101")
    assert c.atividade is Atividade.INDUSTRIA and c.confianca == "divisao" and "aproximada" in c.motivo
    assert cnae.classificar("0111301").atividade is None  # atividade rural
    assert cnae.classificar("9").confianca == "divisao" and cnae.classificar(None).atividade is None


def test_item_do_catalogo():
    i = cnae.item("6209-1/00")
    assert i["codigo"] == "6209100" and i["secao"] == "J" and i["divisao"] == "62" and "INFORMAÇÃO" in i["secao_nome"]
    assert i["anexo"] == "Anexo III ou V (fator R)" and i["fator_r"] is True and i["vedacao"] is None
    assert cnae.item("0000000") is None and cnae.item("") is None


def test_busca_por_palavras_codigo_filtro_e_divisao():
    por_texto = cnae.buscar("treinamento desenvolvimento")
    assert "8599604" in {i["codigo"] for i in por_texto["itens"]}
    assert cnae.buscar("TREINAMENTO")["total"] == cnae.buscar("treinamento")["total"]  # sem diferença de caixa ou acento
    assert cnae.buscar("informática")["total"] == cnae.buscar("informatica")["total"] > 0
    assert [i["codigo"] for i in cnae.buscar("6201-5")["itens"]] == ["6201501", "6201502"]
    assert {i["codigo"] for i in cnae.buscar("", divisao="62")["itens"]} >= {"6201501", "6209100"}
    iii = cnae.buscar("", anexo="iii_direto", so_da_tabela=True, limite=500)
    assert iii["total"] >= 150 and all(i["atividade"] == "servico_anexo_iii" for i in iii["itens"])
    assert all(i["vedacao"] for i in cnae.buscar("", anexo="vedado", limite=500)["itens"])
    assert cnae.buscar("zzzz")["total"] == 0
    assert len(cnae.buscar("", limite=5)["itens"]) == 5 and cnae.buscar("", limite=5)["total"] > 1300


def test_divisoes_e_fontes():
    assert len(cnae.divisoes()) == 87 and cnae.divisoes()[0]["codigo"] == "01"
    assert {"subclasses", "vedacao", "anexos", "atualizado_em"} <= set(cnae.fontes())
