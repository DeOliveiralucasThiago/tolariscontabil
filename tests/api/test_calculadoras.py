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
    assert [c["ano"] for c in d["cenarios"]] == list(range(2027, 2034))
    assert d["melhor"].startswith("Recolher")
    assert len(d["curvas"]["2033"]) == 11 and len(d["curvas"]["2030"]) == 11
    so_dois = logado.post("/api/calculadoras/simples-reforma", json={**ENTRADAS["simples-reforma"], "anos": [2033, 2027, 2033]}).json()
    assert [c["ano"] for c in so_dois["cenarios"]] == [2027, 2033]
    assert logado.post("/api/calculadoras/simples-reforma", json={**ENTRADAS["simples-reforma"], "anos": [2026]}).status_code == 422
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
    assert d["cenarios"][-1]["equilibrio_texto"] == "com qualquer % de vendas B2B"
    d = logado.post("/api/calculadoras/simples-reforma", json={
        "atividade": "servico_anexo_iii", "receita_bruta_anual": 120000, "percentual_b2b": 1,
        "compras_creditaveis_anual": 20000}).json()
    assert d["cenarios"][-1]["equilibrio_texto"].startswith("a partir de")


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


def test_completa_com_iss_fixo_e_servicos_hospitalares(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Advocacia Exemplo", "atividade": "servico_anexo_iv"}).json()["id"]
    base = {"atividade": "servico_anexo_iv", "receita_bruta_anual": 600000, "pro_labore_anual": 36000, "outras_despesas_anual": 60000}
    normal = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=base).json()
    fixo = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={
        **base, "sociedade_profissionais": True, "profissionais": 3, "iss_fixo_por_profissional_anual": 1800}).json()
    iss = lambda s: next(t["valor"] for r in s["resultado"]["regimes"] if r["titulo"] == "Lucro Presumido" for t in r["tributos"] if t["nome"] == "ISS")  # noqa: E731
    assert iss(normal) == 30000 and iss(fixo) == 5400
    pdf = logado.get(f"/api/simulacoes/{fixo['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # validações
    invalido = {**base, "sociedade_profissionais": True}
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=invalido).status_code == 422
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={
        **base, "atividade": "comercio", "sociedade_profissionais": True, "profissionais": 1, "iss_fixo_por_profissional_anual": 900}).status_code == 422
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "atividade": "comercio", "servicos_hospitalares": True}).status_code == 422
    # serviços hospitalares: presunção de 8% e 12% no Presumido
    h = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={
        "atividade": "servico_fator_r", "receita_bruta_anual": 1200000, "folha_clt_anual": 300000, "pro_labore_anual": 60000,
        "servicos_hospitalares": True}).json()
    p = next(r for r in h["resultado"]["regimes"] if r["titulo"] == "Lucro Presumido")
    assert {t["nome"]: t["valor"] for t in p["tributos"]}["IRPJ"] == 14400
    # o Enquadramento aceita os mesmos campos
    d = logado.post("/api/calculadoras/enquadramento", json={
        "atividade": "servico_fator_r", "receita_bruta_anual": 600000, "pro_labore_anual": 36000, "outras_despesas_anual": 60000,
        "sociedade_profissionais": True, "profissionais": 2, "iss_fixo_por_profissional_anual": 1500}).json()
    assert d["cenarios"][0]["anexos_simples"] == ["V"]


def test_completa_do_escritorio_contabil_com_iss_fixo_no_simples(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Escritório Contábil Exemplo", "atividade": "servico_anexo_iii"}).json()["id"]
    base = {"atividade": "servico_anexo_iii", "receita_bruta_anual": 600000, "pro_labore_anual": 36000, "outras_despesas_anual": 60000,
            "sociedade_profissionais": True, "profissionais": 2, "iss_fixo_por_profissional_anual": 1500}
    sem = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=base).json()
    com = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "iss_fixo_no_simples": True}).json()
    sn = lambda s: next(r for r in s["resultado"]["regimes"] if r["titulo"] == "Simples Nacional")  # noqa: E731
    assert {t["nome"]: t["valor"] for t in sn(sem)["tributos"]} == {"DAS": 63360}
    assert {t["nome"]: t["valor"] for t in sn(com)["tributos"]} == {"DAS": 42768, "ISS fixo (recolhido ao Município, fora do DAS)": 3000}
    pdf = logado.get(f"/api/simulacoes/{com['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # só vale para o escritório de serviços contábeis (Anexo III) com a sociedade de profissionais
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "atividade": "servico_anexo_iv", "iss_fixo_no_simples": True}).status_code == 422
    sem_sociedade = {k: v for k, v in base.items() if k not in ("sociedade_profissionais", "profissionais", "iss_fixo_por_profissional_anual")}
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**sem_sociedade, "iss_fixo_no_simples": True}).status_code == 422


def test_comparativo_a_partir_de_2027_com_cbs_ibs_e_reducao(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Consultoria 2027", "atividade": "servico_fator_r"}).json()["id"]
    base = {"atividade": "servico_fator_r", "receita_bruta_anual": 900000, "folha_clt_anual": 200000, "pro_labore_anual": 60000}
    tributos = lambda s, regime: {t["nome"]: t["valor"] for r in s["resultado"]["regimes"] if r["titulo"] == regime for t in r["tributos"]}  # noqa: E731
    s26 = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=base).json()
    s27 = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "ano": 2027}).json()
    assert "PIS" in tributos(s26, "Lucro Presumido") and "CBS" not in tributos(s26, "Lucro Presumido")
    p27 = tributos(s27, "Lucro Presumido")
    assert "CBS" in p27 and "IBS" in p27 and "PIS" not in p27 and "Cofins" not in p27
    r27 = tributos(s27, "Lucro Real")
    assert "CBS" in r27 and "PIS" not in r27
    reduzida = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "ano": 2027, "reducao_ibs_cbs": 0.3}).json()
    assert tributos(reduzida, "Lucro Presumido")["CBS"] == pytest.approx(p27["CBS"] * 0.7, abs=0.02)
    pdf = logado.get(f"/api/simulacoes/{reduzida['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # validações: ano até 2033 e reduções previstas na lei
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "ano": 2034}).status_code == 422
    assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**base, "ano": 2027, "reducao_ibs_cbs": 0.5}).status_code == 422
    expressa = {"faturamento_mensal": 50000, "folha_mensal": 10000, "atividade": "servico_fator_r"}
    d = logado.post("/api/simulacoes/previa/expressa", json={**expressa, "ano": 2029}).json()
    assert d["ano"] == 2029 and any(t["nome"] == "IBS" for r in d["regimes"] for t in r["tributos"])
    assert logado.post("/api/simulacoes/previa/expressa", json={**expressa, "ano": 2034}).status_code == 422


def test_reforma_de_sociedade_uniprofissional_com_iss_fixo(logado: TestClient):
    corpo = {"receita_bruta_anual": 600000, "vende_mercadoria": False, "reducao_setorial": 0.3, "iss_fixo_anual": 3000}
    d = logado.post("/api/calculadoras/reforma", json=corpo).json()
    iss = {a["ano"]: next((t["valor"] for t in a["tributos"] if t["nome"] == "ISS"), 0) for a in d["anos"]}
    assert iss[2027] == 3000 and iss[2030] == 2400 and iss[2033] == 0
    assert any("não traz regra própria" in x for x in d["alertas"])
    # salva no cliente e gera o PDF com o ISS fixo nas entradas
    cid = logado.post("/api/clientes", json={"razao_social": "Advocacia Reforma", "atividade": "servico_anexo_iv"}).json()["id"]
    sim = logado.post(f"/api/clientes/{cid}/simulacoes/reforma", json=corpo)
    assert sim.status_code == 201, sim.text
    pdf = logado.get(f"/api/simulacoes/{sim.json()['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert logado.post("/api/calculadoras/reforma", json={**corpo, "vende_mercadoria": True}).status_code == 422


def test_completa_e_enquadramento_com_receitas_de_outras_atividades(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Loja e Consultoria", "atividade": "comercio"}).json()["id"]
    corpo = {"atividade": "comercio", "receita_bruta_anual": 1800000, "folha_clt_anual": 240000, "pro_labore_anual": 60000,
             "compras_anual": 700000, "receitas_outras_atividades": {"servico_fator_r": 600000}}
    s = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=corpo)
    assert s.status_code == 201, s.text
    regimes = {r["titulo"]: {t["nome"]: t["valor"] for t in r["tributos"]} for r in s.json()["resultado"]["regimes"]}
    assert round(regimes["Simples Nacional"]["DAS"]) == 230700
    assert {"ICMS", "ISS"} <= set(regimes["Lucro Presumido"])
    pdf = logado.get(f"/api/simulacoes/{s.json()['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    d = logado.post("/api/calculadoras/enquadramento", json=corpo).json()
    assert d["cenarios"][0]["anexos_simples"] == ["I", "V"]
    assert [x["anexo"] for x in d["cenarios"][0]["receitas_por_anexo"]] == ["I", "V"]
    assert d["cenarios"][-1]["anexos_simples"] == ["I", "III"] and d["cenarios"][-1]["receita_anexo_iii"] == 600000
    # validações
    for invalido in ({"comercio": 100}, {"servico_fator_r": 2000000}, {"servico_fator_r": 0}, {"padaria": 100}):
        r = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**corpo, "receitas_outras_atividades": invalido})
        assert r.status_code == 422, invalido
