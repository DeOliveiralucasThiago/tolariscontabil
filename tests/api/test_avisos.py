from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tolaris_api.servicos import diferencas
from tolaris_motor import tabelas

from .conftest import cadastrar
from .test_importacao import _enviar
from .test_recuperacao import _cliente, _importar_13_meses, nfe_itens

# Serviços do fator R: folha 96.000 + pró-labore 60.000 + FGTS 7.680 = 27,28% de R$ 600.000
FATOR_R = {"atividade": "servico_fator_r", "receita_bruta_anual": 600000, "folha_clt_anual": 96000, "pro_labore_anual": 60000}
COMERCIO = {"atividade": "comercio", "receita_bruta_anual": 1500000, "folha_clt_anual": 120000, "pro_labore_anual": 36000,
            "compras_anual": 900000, "despesas_creditaveis_anual": 60000}


def _planejar(c: TestClient, cid: int, dados: dict) -> dict:
    r = c.post(f"/api/clientes/{cid}/simulacoes/completa", json=dados)
    assert r.status_code == 201, r.text
    return r.json()


def _avisos(c: TestClient) -> list[dict]:
    r = c.get("/api/avisos")
    assert r.status_code == 200, r.text
    return r.json()["avisos"]


def _por_codigo(c: TestClient) -> dict[str, dict]:
    return {a["codigo"]: a for a in _avisos(c)}


def test_exige_login(client: TestClient):
    assert client.get("/api/avisos").status_code == 401
    assert client.get("/api/mudancas").status_code == 401
    assert client.post("/api/simulacoes/1/recalcular").status_code == 401


def test_carteira_vazia(logado: TestClient):
    r = logado.get("/api/avisos").json()
    assert r["avisos"] == [] and r["resumo"]["total"] == 0 and r["clientes_analisados"] == 0


def test_fator_r_so_para_quem_esta_no_simples(logado: TestClient):
    no_simples = _cliente(logado, atividade="servico_fator_r", regime_atual="simples")
    outro = logado.post("/api/clientes", json={"razao_social": "Consultoria Lucro", "cnpj": "45997418000153",
                                               "atividade": "servico_fator_r", "regime_atual": "presumido"}).json()["id"]
    for cid in (no_simples, outro):
        _planejar(logado, cid, FATOR_R)
    avisos = [a for a in _avisos(logado) if a["codigo"].startswith("fator_r")]
    assert len(avisos) == 1
    a = avisos[0]
    assert a["cliente_id"] == no_simples and a["codigo"] == "fator_r_abaixo" and a["gravidade"] == "oportunidade"
    assert a["valor"] == 43264.8 and "27,28%" in a["titulo"] and a["acao"]["tipo"] == "cliente"
    resumo = logado.get("/api/avisos").json()["resumo"]
    assert resumo["oportunidade"] == 1 and resumo["valor_oportunidades"] == 43264.8


def test_fator_r_a_partir_da_simulacao_expressa(logado: TestClient):
    cid = _cliente(logado, atividade="servico_fator_r", regime_atual="simples")
    logado.post(f"/api/clientes/{cid}/simulacoes/expressa", json={
        "faturamento_mensal": 50000, "folha_mensal": 8000, "pro_labore_mensal": 5000, "atividade": "servico_fator_r"})
    assert _por_codigo(logado)["fator_r_abaixo"]["valor"] == 43264.8   # mesmos números do caso anual


def test_limites_usam_as_notas_importadas(logado: TestClient):
    cid = _cliente(logado, regime_atual="simples")
    item = ("19059090", "5102", "102", "49", "", 350000.0, 0.0, "BISCOITO")   # R$ 350 mil por mês = R$ 4,2 mi em 12 meses
    notas = [(f"n{i}.xml", nfe_itens(i + 1, f"{2025 + i // 12}-{i % 12 + 1:02d}-10", [item])) for i in range(13)]
    assert _enviar(logado, cid, notas).json()["importados"] == 13
    avisos = _por_codigo(logado)
    assert avisos["simples_limite"]["gravidade"] == "atencao" and "88%" in avisos["simples_limite"]["titulo"]
    assert avisos["simples_sublimite"]["titulo"].startswith("Receita acima do sublimite")
    assert "notas importadas de fev/25 a jan/26" in avisos["simples_limite"]["detalhe"]
    assert avisos["simples_limite"]["acao"] == {"tipo": "cliente", "rotulo": "Abrir cliente", "aba": "movimento"}


def test_limite_do_mei_a_partir_do_planejamento(logado: TestClient):
    cid = _cliente(logado, atividade="servico_anexo_iii", regime_atual="mei")
    _planejar(logado, cid, {**FATOR_R, "atividade": "servico_anexo_iii", "receita_bruta_anual": 85000, "folha_clt_anual": 0, "pro_labore_anual": 0})
    a = _por_codigo(logado)["mei_limite"]
    assert a["gravidade"] == "critico" and "acima do limite do MEI" in a["titulo"] and "planejamento de" in a["detalhe"]


def test_oportunidade_de_recuperacao(logado: TestClient):
    cid = _cliente(logado, regime_atual="simples")
    _importar_13_meses(logado, cid)
    a = _por_codigo(logado)["recuperacao"]
    assert a["gravidade"] == "oportunidade" and a["valor"] == 432.43 and a["acao"]["aba"] == "movimento"
    assert "R$ 432,43" in a["titulo"]


def test_cliente_inativo_nao_gera_avisos(logado: TestClient):
    cid = _cliente(logado, atividade="servico_fator_r", regime_atual="simples")
    _planejar(logado, cid, FATOR_R)
    assert len(_avisos(logado)) == 1
    logado.patch(f"/api/clientes/{cid}", json={"status": "inativo"})
    assert _avisos(logado) == []


def test_ordem_dos_avisos_critico_primeiro(logado: TestClient):
    a = _cliente(logado, atividade="servico_fator_r", regime_atual="simples")
    _planejar(logado, a, FATOR_R)
    b = logado.post("/api/clientes", json={"razao_social": "Microempreendedor", "cnpj": "45997418000153",
                                           "atividade": "servico_anexo_iii", "regime_atual": "mei"}).json()["id"]
    _planejar(logado, b, {**FATOR_R, "atividade": "servico_anexo_iii", "receita_bruta_anual": 85000, "folha_clt_anual": 0, "pro_labore_anual": 0})
    assert [x["gravidade"] for x in _avisos(logado)] == ["critico", "oportunidade"]


def test_mudanca_de_lei_marca_simulacao_desatualizada_e_recalcula(logado: TestClient, monkeypatch: pytest.MonkeyPatch):
    cid = _cliente(logado, regime_atual="simples")
    antiga = _planejar(logado, cid, COMERCIO)
    assert not [a for a in _avisos(logado) if a["codigo"] == "simulacao_desatualizada"]

    # "Mudança de lei": a alíquota nominal da 4ª faixa do Anexo I sobe de 10,7% para 20%
    faixa = tabelas.carregar("simples_nacional")["vigencias"][0]["anexos"]["I"]["faixas"][3]
    monkeypatch.setitem(faixa, "aliquota", "0.20")
    a = next(x for x in _avisos(logado) if x["codigo"] == "simulacao_desatualizada")
    assert a["cliente_id"] == cid and a["acao"] == {"tipo": "recalcular", "rotulo": "Recalcular", "simulacao_id": antiga["id"]}
    assert a["gravidade"] in ("atencao", "critico") and "mudou com as regras atuais" in a["titulo"]
    assert "Mudaram os totais" in a["detalhe"] and "Simples Nacional: de R$" in a["detalhe"] and "para R$" in a["detalhe"]
    assert "A recomendação" in a["detalhe"]

    r = logado.post(f"/api/simulacoes/{antiga['id']}/recalcular")
    assert r.status_code == 201, r.text
    nova = r.json()
    assert nova["id"] != antiga["id"] and nova["tipo"] == "completa" and nova["entrada"] == antiga["entrada"]
    assert nova["resultado"]["recalculo"]["de"] == antiga["id"]
    assert nova["resultado"]["recalculo"]["antes"]["melhor"] == antiga["resultado"]["melhor"]
    assert "Simples Nacional: de R$" in nova["resultado"]["recalculo"]["resumo"]
    simples_antes = next(x for x in antiga["resultado"]["regimes"] if x["titulo"] == "Simples Nacional")["total"]
    simples_depois = next(x for x in nova["resultado"]["regimes"] if x["titulo"] == "Simples Nacional")["total"]
    assert simples_depois > simples_antes
    # A original continua no histórico e a nova já está de acordo com as regras: o aviso some
    assert len(logado.get(f"/api/clientes/{cid}/simulacoes").json()) == 2
    assert not [x for x in _avisos(logado) if x["codigo"] == "simulacao_desatualizada"]


def test_recalcular_relatorio_de_recuperacao(logado: TestClient):
    cid = _cliente(logado, regime_atual="simples")
    _importar_13_meses(logado, cid)
    antiga = logado.post(f"/api/clientes/{cid}/recuperacao", json={}).json()
    r = logado.post(f"/api/simulacoes/{antiga['id']}/recalcular")
    assert r.status_code == 201 and r.json()["tipo"] == "recuperacao"
    assert r.json()["resultado"]["recalculo"]["de"] == antiga["id"]
    assert r.json()["resultado"]["totais"]["provavel"] == 432.43


def test_recalcular_nao_vaza_entre_escritorios(logado: TestClient):
    cid = _cliente(logado, regime_atual="simples")
    sim = _planejar(logado, cid, COMERCIO)
    logado.post("/api/auth/logout")
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.post(f"/api/simulacoes/{sim['id']}/recalcular").status_code == 404
    assert logado.get("/api/avisos").json()["avisos"] == []


def test_feed_de_mudancas_na_legislacao(logado: TestClient):
    lista = logado.get("/api/mudancas").json()
    ids = {m["id"]: m for m in lista}
    assert ids["irpf-lei-15270"]["vigente"] is True and ids["reforma-2033"]["vigente"] is False
    assert "Lei 15.270/2025" in ids["irpf-lei-15270"]["base_legal"]
    vigentes = [m["vigente"] for m in lista]
    assert vigentes == sorted(vigentes)          # primeiro as futuras (False), depois as em vigor (True)
    futuras = [m["data"] for m in lista if not m["vigente"]]
    assert futuras == sorted(futuras)            # a mais próxima primeiro


def test_diferencas_ignora_textos_e_campos_novos():
    antigo = {"melhor": "Simples Nacional", "total": 100.0, "alertas": ["a"], "memoria": [{"valor": 1}],
              "regimes": [{"titulo": "Simples", "total": 100.0}]}
    mesmo = {**antigo, "alertas": ["outro texto"], "memoria": [{"valor": 2}], "campo_novo": 7.0}
    assert diferencas(antigo, mesmo) == []
    assert diferencas(antigo, {**antigo, "total": 100.005}) == []                  # menos de 1 centavo
    assert diferencas(antigo, {**antigo, "total": 100.5}) == ["total"]
    assert diferencas(antigo, {**antigo, "melhor": "Lucro Presumido"}) == ["melhor"]
    assert diferencas(antigo, {**antigo, "regimes": [{"titulo": "Simples", "total": 90.0}]}) == ["regimes[0].total"]


def test_aviso_de_notas_paradas_so_para_cliente_ativo(logado: TestClient):
    from datetime import date

    cid = _cliente(logado, regime_atual="simples")
    item = ("19059090", "5102", "102", "49", "", 1000.0, 0.0, "BISCOITO")
    assert _enviar(logado, cid, [("n.xml", nfe_itens(1, "2025-03-10", [item]))]).json()["importados"] == 1
    assert "movimento_desatualizado" not in _por_codigo(logado)  # prospect não é cobrado
    logado.patch(f"/api/clientes/{cid}", json={"status": "ativo"})
    a = _por_codigo(logado)["movimento_desatualizado"]
    assert a["gravidade"] == "info" and a["titulo"] == "Notas paradas desde mar/25"
    assert a["acao"] == {"tipo": "cliente", "rotulo": "Pedir notas", "aba": "movimento"}
    # chegando nota do mês corrente, o aviso some
    hoje = date.today()
    assert _enviar(logado, cid, [("n2.xml", nfe_itens(2, f"{hoje.year}-{hoje.month:02d}-01", [item]))]).json()["importados"] == 1
    assert "movimento_desatualizado" not in _por_codigo(logado)


def test_feed_traz_as_mudancas_publicadas_em_2026(logado: TestClient):
    ids = {m["id"]: m for m in logado.get("/api/mudancas").json()}
    assert {"mei-lc238", "simples-anexos-2027", "simples-regime-regular-ibs-cbs-prazo", "nfse-nacional-simples"} <= set(ids)
    assert "R$ 110" in ids["mei-lc238"]["titulo"] and "LC 238/2026" in ids["mei-lc238"]["base_legal"]
    assert "Ainda não incorporado" in ids["mei-lc238"]["observacao"]
    assert ids["simples-regime-regular-ibs-cbs-prazo"]["data"] == "2026-10-30"
