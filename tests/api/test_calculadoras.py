from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import cadastrar

ENTRADAS = {
    "reforma": {"receita_bruta_anual": 1000000, "vende_mercadoria": True, "compras_anual": 600000},
    "simples-reforma": {"atividade": "comercio", "receita_bruta_anual": 2000000, "percentual_b2b": 0.8,
                        "compras_creditaveis_anual": 1200000},
    "autonomo": {"receita_mensal": 15000, "contabilidade_mensal": 400},
    "pro-labore": {"retirada_mensal": 20000, "regime": "presumido"},
    "enquadramento": {"atividade": "servico_fator_r", "receita_bruta_anual": 600000, "pro_labore_anual": 36000,
                      "outras_despesas_anual": 60000},
}


def test_calculadoras_exigem_login(client: TestClient):
    for rota, corpo in ENTRADAS.items():
        assert client.post(f"/api/calculadoras/{rota}", json=corpo).status_code == 401


def test_reforma(logado: TestClient):
    d = logado.post("/api/calculadoras/reforma", json=ENTRADAS["reforma"]).json()
    assert [a["ano"] for a in d["anos"]] == list(range(2025, 2034))
    assert d["anos"][0]["total"] == 108500 and d["anos"][0]["novos"] == 0
    assert d["anos"][-1]["atuais"] == 0 and d["anos"][-1]["novos"] == d["anos"][-1]["total"]
    assert d["base_venda"] == 783500 and d["melhor"].startswith("Carga em 2033")


def test_simples_reforma(logado: TestClient):
    d = logado.post("/api/calculadoras/simples-reforma", json=ENTRADAS["simples-reforma"]).json()
    assert [c["ano"] for c in d["cenarios"]] == [2027, 2033]
    assert d["melhor"].startswith("Recolher")
    assert len(d["curvas"]["2033"]) == 11
    corpo = {**ENTRADAS["simples-reforma"], "receita_bruta_anual": 5000000}
    assert logado.post("/api/calculadoras/simples-reforma", json=corpo).status_code == 422


def test_autonomo_e_pro_labore_e_salario(logado: TestClient):
    d = logado.post("/api/calculadoras/autonomo", json=ENTRADAS["autonomo"]).json()
    assert d["melhor"] == "Simples Nacional" and d["ganho_vs_autonomo_anual"] > 0
    assert {o["nome"] for o in d["opcoes"]} == {"Autônomo (pessoa física)", "MEI", "Simples Nacional", "Lucro Presumido"}
    d = logado.post("/api/calculadoras/pro-labore", json=ENTRADAS["pro-labore"]).json()
    assert d["economia_anual"] > 0 and d["cenarios"][1]["pro_labore"] == 1621
    d = logado.post("/api/calculadoras/salario-liquido", json={"salario_bruto": 5900}).json()
    assert d["liquido"] == 4924.35


@pytest.mark.parametrize("rota", list(ENTRADAS))
def test_salvar_no_cliente_e_gerar_pdf(logado: TestClient, rota: str):
    cid = logado.post("/api/clientes", json={"razao_social": "Cliente Fase 2", "atividade": "comercio"}).json()["id"]
    r = logado.post(f"/api/clientes/{cid}/simulacoes/{rota}", json=ENTRADAS[rota])
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["tipo"] == rota.replace("-", "_") and " — " in sim["titulo"]
    pdf = logado.get(f"/api/simulacoes/{sim['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert logado.get("/api/painel").json()["simulacoes_mes"] == 1


def test_salvar_em_cliente_de_outro_escritorio(client: TestClient):
    cadastrar(client, "a@a.com", "Escritório A")
    cid = client.post("/api/clientes", json={"razao_social": "Cliente do A"}).json()["id"]
    client.post("/api/auth/logout")
    cadastrar(client, "b@b.com", "Escritório B")
    assert client.post(f"/api/clientes/{cid}/simulacoes/autonomo", json=ENTRADAS["autonomo"]).status_code == 404


def test_opcao_nao_aplicavel_sai_como_nao_aplicavel(logado: TestClient):
    d = logado.post("/api/calculadoras/autonomo", json={"receita_mensal": 15000}).json()
    mei = next(o for o in d["opcoes"] if o["nome"] == "MEI")
    assert mei["aplicavel"] is False and "MEI" not in d["ranking"]


def test_texto_do_ponto_de_equilibrio(logado: TestClient):
    d = logado.post("/api/calculadoras/simples-reforma", json=ENTRADAS["simples-reforma"]).json()
    assert d["cenarios"][1]["equilibrio_texto"] == "com qualquer % de vendas B2B"
    d = logado.post("/api/calculadoras/simples-reforma", json={
        "atividade": "servico_anexo_iii", "receita_bruta_anual": 120000, "percentual_b2b": 1,
        "compras_creditaveis_anual": 20000}).json()
    assert d["cenarios"][1]["equilibrio_texto"].startswith("a partir de")


def test_enquadramento_compara_os_caminhos_para_o_anexo_iii(logado: TestClient):
    d = logado.post("/api/calculadoras/enquadramento", json={**ENTRADAS["enquadramento"], "percentual_anexo_iii": 0.3}).json()
    assert d["fator_r_atual"] == 0.06
    assert [c["chave"] for c in d["cenarios"]] == ["atual", "fator_r", "anexo_iii_25", "anexo_iii_30", "anexo_iii_50", "anexo_iii_100"]
    atual, fator_r = d["cenarios"][0], d["cenarios"][1]
    assert atual["anexos_simples"] == ["V"] and fator_r["anexos_simples"] == ["III"] and fator_r["custo_extra_anual"] > 0
    assert fator_r["pro_labore_anual"] == 168000 and fator_r["total_com_custo_extra"] < atual["total_com_custo_extra"]
    assert d["recomendado"] == "anexo_iii_100" and d["economia_vs_pior"] > 0
    assert "exercida de fato" in d["alertas"][0]


def test_enquadramento_fora_do_fator_r_so_traz_o_cenario_atual(logado: TestClient):
    d = logado.post("/api/calculadoras/enquadramento", json={**ENTRADAS["enquadramento"], "atividade": "comercio"}).json()
    assert [c["chave"] for c in d["cenarios"]] == ["atual"] and "serviços do fator R" in d["alertas"][2]
    assert d["economia_vs_pior"] == 0


def test_completa_com_receita_do_anexo_iii_e_validacoes(logado: TestClient):
    base = ENTRADAS["enquadramento"]
    cid = logado.post("/api/clientes", json={"razao_social": "Consultoria Maple Ltda", "atividade": "servico_fator_r"}).json()["id"]
    todos_v = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=base).json()
    separada = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "receita_anexo_iii_anual": 300000}).json()
    simples = lambda s: next(r for r in s["resultado"]["regimes"] if r["titulo"] == "Simples Nacional")["total"]  # noqa: E731
    assert simples(separada) < simples(todos_v)
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "receita_anexo_iii_anual": 700000}).status_code == 422
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "atividade": "comercio", "receita_anexo_iii_anual": 1000}).status_code == 422


def test_folha_do_fator_r_informada_pelo_contador(logado: TestClient):
    calculada = logado.post("/api/calculadoras/enquadramento", json=ENTRADAS["enquadramento"]).json()
    informada = logado.post("/api/calculadoras/enquadramento", json={**ENTRADAS["enquadramento"], "folha_fator_r_anual": 250000}).json()
    assert calculada["fator_r_atual"] == 0.06 and informada["fator_r_atual"] == 0.416667
    assert informada["cenarios"][0]["anexos_simples"] == ["III"] and len(informada["cenarios"]) == 1  # já chega a 28%
    cid = logado.post("/api/clientes", json={"razao_social": "Folha Ltda", "atividade": "servico_fator_r"}).json()["id"]
    sim = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**ENTRADAS["enquadramento"], "folha_fator_r_anual": 250000}).json()
    passo = next(p for r in sim["resultado"]["regimes"] if r["titulo"] == "Simples Nacional" for p in r["memoria"] if p["descricao"].startswith("Fator R"))
    assert "(informada)" in passo["formula"]
