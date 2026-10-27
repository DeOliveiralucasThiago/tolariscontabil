"""Natureza jurídica no cadastro: CNPJ, cliente, simulação, completar em lote e Central de Avisos."""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from tolaris_api import cnpj
from tolaris_api.routers.cnpj import get_consulta_cnpj

from .test_clientes_lote import CNPJ_VALIDO, MAPA, _csv, _dados, _enviar

COMPLETA = {"atividade": "servico_anexo_iii", "receita_bruta_anual": 600000, "folha_clt_anual": 100000}


def _simples(resultado: dict) -> dict:
    return next(r for r in resultado["regimes"] if r["titulo"] == "Simples Nacional")


def test_interpreta_natureza_da_brasilapi():
    d = cnpj.interpretar_brasilapi({"cnpj": "11222333000181", "razao_social": "X", "codigo_natureza_juridica": 2062, "natureza_juridica": "Sociedade Empresária Limitada"})
    assert d.natureza_juridica == "Sociedade Empresária Limitada" and d.natureza_juridica_codigo == "2062"
    assert d.como_dict()["natureza_info"]["tipo"] == "sociedade_empresaria"
    assert cnpj.interpretar_brasilapi({"codigo_natureza_juridica": 0}).natureza_juridica_codigo is None
    assert cnpj.interpretar_brasilapi({"codigo_natureza_juridica": 999}).natureza_juridica_codigo == "0999"
    assert cnpj.interpretar_brasilapi({}).natureza_juridica is None and cnpj.info_natureza(None) is None


def test_consulta_cnpj_traz_a_natureza(logado: TestClient):
    d = logado.get("/api/cnpj/11222333000181").json()
    assert d["natureza_juridica"] == "Sociedade Empresária Limitada" and d["natureza_juridica_codigo"] == "2062"
    assert d["natureza_info"]["simples"] == "sim" and d["natureza_info"]["mei"] is False


def test_cliente_guarda_e_devolve_a_natureza(logado: TestClient):
    r = logado.post("/api/clientes", json={"razao_social": "Cia Aberta", "natureza_juridica": "Sociedade Anônima Fechada", "natureza_juridica_codigo": "2054"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["natureza_juridica_codigo"] == "2054" and c["natureza_info"]["tipo"] == "sociedade_por_acoes" and c["natureza_info"]["simples"] == "vedado"
    atualizado = logado.patch(f"/api/clientes/{c['id']}", json={"natureza_juridica": "Sociedade Empresária Limitada"}).json()
    assert atualizado["natureza_info"]["simples"] == "sim"
    assert logado.get("/api/clientes").json()[0]["natureza_info"]["tipo"] == "sociedade_empresaria"
    sem = logado.post("/api/clientes", json={"razao_social": "Sem natureza"}).json()
    assert sem["natureza_juridica"] is None and sem["natureza_info"] is None
    assert logado.post("/api/clientes", json={"razao_social": "Código ruim", "natureza_juridica_codigo": "20"}).status_code == 422


def test_simulacao_do_cliente_usa_a_natureza_do_cadastro(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Cia Aberta", "natureza_juridica": "Sociedade Anônima Fechada"}).json()["id"]
    sim = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=COMPLETA).json()
    s = _simples(sim["resultado"])
    assert s["aplicavel"] is False and any("sociedade por ações" in a.lower() for a in s["alertas"])
    assert sim["resultado"]["melhor"] != "Simples Nacional" and sim["entrada"]["natureza_juridica"] == "Sociedade Anônima Fechada"
    # a tela pode informar outra natureza para a simulação (por exemplo, uma mudança de tipo societário em estudo)
    outra = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**COMPLETA, "natureza_juridica": "Sociedade Empresária Limitada"}).json()
    assert _simples(outra["resultado"])["aplicavel"] is True
    # cliente sem natureza: Simples normal
    livre = logado.post("/api/clientes", json={"razao_social": "Livre"}).json()["id"]
    assert logado.post(f"/api/clientes/{livre}/simulacoes/completa", json=COMPLETA).json()["resultado"]["melhor"] == "Simples Nacional"
    previa = logado.post("/api/simulacoes/previa/expressa", json={"faturamento_mensal": 50000, "folha_mensal": 10000, "atividade": "servico_anexo_iii", "natureza_juridica": "Cooperativa"}).json()
    assert next(r for r in previa["regimes"] if r["titulo"] == "Simples Nacional")["aplicavel"] is False


def test_prospeccao_leva_a_natureza_do_cliente(logado: TestClient):
    corpo = {"cliente": {"razao_social": "Cooperativa X", "cnpj": CNPJ_VALIDO, "natureza_juridica": "Cooperativa"},
             "simulacao": {"faturamento_mensal": 50000, "folha_mensal": 10000, "atividade": "servico_anexo_iii"}}
    r = logado.post("/api/prospeccao", json=corpo)
    assert r.status_code == 201, r.text
    regimes = r.json()["simulacao"]["resultado"]["regimes"]
    assert next(x for x in regimes if x["titulo"] == "Simples Nacional")["aplicavel"] is False


def test_completar_pelo_cnpj_preenche_a_natureza(logado: TestClient):
    _enviar(logado, "importar", _csv([f"{CNPJ_VALIDO};;;;;"]), MAPA)
    logado.app.dependency_overrides[get_consulta_cnpj] = lambda: lambda c: replace(_dados(c), natureza_juridica="Sociedade Empresária Limitada", natureza_juridica_codigo="2062")
    assert logado.post("/api/clientes-lote/completar").status_code == 200
    c = logado.get("/api/clientes").json()[0]
    assert c["natureza_juridica"] == "Sociedade Empresária Limitada" and c["natureza_juridica_codigo"] == "2062"


def _avisos_natureza(c: TestClient) -> list[dict]:
    return [a for a in c.get("/api/avisos").json()["avisos"] if a["codigo"].startswith("natureza_")]


def test_central_avisa_s_a_no_simples_e_mei_que_nao_e_empresario_individual(logado: TestClient):
    sa = logado.post("/api/clientes", json={"razao_social": "Cia SA", "regime_atual": "simples", "natureza_juridica": "Sociedade Anônima Fechada", "status": "ativo"}).json()
    mei = logado.post("/api/clientes", json={"razao_social": "Falso MEI", "regime_atual": "mei", "natureza_juridica": "Sociedade Empresária Limitada", "status": "ativo"}).json()
    ok_ei = logado.post("/api/clientes", json={"razao_social": "MEI de verdade", "regime_atual": "mei", "natureza_juridica": "Empresário (Individual)", "status": "ativo"}).json()
    ok_ltda = logado.post("/api/clientes", json={"razao_social": "Ltda", "regime_atual": "simples", "natureza_juridica": "Sociedade Empresária Limitada", "status": "ativo"}).json()
    presumido = logado.post("/api/clientes", json={"razao_social": "SA no Presumido", "regime_atual": "presumido", "natureza_juridica": "Sociedade Anônima Aberta", "status": "ativo"}).json()
    por_cliente = {a["cliente_id"]: a for a in _avisos_natureza(logado)}
    assert set(por_cliente) == {sa["id"], mei["id"]}
    assert por_cliente[sa["id"]]["codigo"] == "natureza_simples" and por_cliente[sa["id"]]["gravidade"] == "critico"
    assert "art. 3º" in por_cliente[sa["id"]]["base_legal"] and por_cliente[sa["id"]]["acao"]["aba"] == "dados"
    assert por_cliente[mei["id"]]["codigo"] == "natureza_mei" and "art. 18-A" in por_cliente[mei["id"]]["base_legal"]
    assert {ok_ei["id"], ok_ltda["id"], presumido["id"]}.isdisjoint(por_cliente)


def test_classificar_natureza_pela_api(logado: TestClient):
    r = logado.get("/api/cnpj/natureza/classificar", params={"descricao": "Sociedade Anônima Aberta"}).json()
    assert r["tipo"] == "sociedade_por_acoes" and r["simples"] == "vedado" and "art. 3º" in r["base_legal"]
    assert logado.get("/api/cnpj/natureza/classificar", params={"codigo": "3999"}).json()["tipo"] == "sem_fins_lucrativos"
    assert logado.get("/api/cnpj/natureza/classificar").json() is None


def test_central_nao_sugere_fator_r_nem_regime_regular_para_quem_nao_pode_ser_do_simples(logado: TestClient):
    corpo = {"atividade": "servico_fator_r", "receita_bruta_anual": 600000, "folha_clt_anual": 96000, "pro_labore_anual": 60000}
    sa = logado.post("/api/clientes", json={"razao_social": "SA", "atividade": "servico_fator_r", "regime_atual": "simples",
                                            "natureza_juridica": "Sociedade Anônima Fechada", "status": "ativo"}).json()["id"]
    ltda = logado.post("/api/clientes", json={"razao_social": "Ltda", "atividade": "servico_fator_r", "regime_atual": "simples",
                                              "natureza_juridica": "Sociedade Empresária Limitada", "status": "ativo", "cnpj": "45997418000153"}).json()["id"]
    for cid in (sa, ltda):
        assert logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=corpo).status_code == 201
    r = logado.get("/api/avisos").json()["avisos"]
    codigos = {c: sorted(a["codigo"] for a in r if a["cliente_id"] == c) for c in (sa, ltda)}
    assert codigos[sa] == ["natureza_simples"]
    assert "fator_r_abaixo" in codigos[ltda]  # a Ltda no Simples continua recebendo os avisos do Simples
