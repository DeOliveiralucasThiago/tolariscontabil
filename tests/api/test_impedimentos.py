"""Conferência dos impedimentos do Simples no cadastro: perguntas, respostas, simulação e Central de Avisos."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import cadastrar

COMPLETA = {"atividade": "servico_anexo_iii", "receita_bruta_anual": 600000, "folha_clt_anual": 100000}


def _cliente(c: TestClient, **extra) -> int:
    return c.post("/api/clientes", json={"razao_social": "Cliente Impedimentos", "regime_atual": "simples", "status": "ativo", **extra}).json()["id"]


def _simples(resultado: dict) -> dict:
    return next(r for r in resultado["regimes"] if r["titulo"] == "Simples Nacional")


def test_exige_login(client: TestClient):
    assert client.get("/api/clientes/1/impedimentos").status_code == 401
    assert client.put("/api/clientes/1/impedimentos", json={"respostas": {}}).status_code == 401


def test_perguntas_por_grupo_e_cliente_sem_respostas(logado: TestClient):
    cid = _cliente(logado)
    d = logado.get(f"/api/clientes/{cid}/impedimentos").json()
    assert [g["grupo"] for g in d["grupos"]] == ["Sócios e participações", "Atividade", "Regularidade"]
    assert sum(len(g["perguntas"]) for g in d["grupos"]) == 23 == d["total"] and d["pendentes"] == 23
    assert d["simples_possivel"] is None and d["achados"] == [] and d["limite_receita_global"] == 4800000
    assert logado.get("/api/clientes/99999/impedimentos").status_code == 404
    assert logado.get(f"/api/clientes/{cid}").json()["impedimentos"] == {"impedem": 0, "dependem": 0, "pendentes": 23, "total": 23}


def test_salva_respostas_e_calcula_o_resultado(logado: TestClient):
    cid = _cliente(logado)
    respostas = {p["chave"]: False for g in logado.get(f"/api/clientes/{cid}/impedimentos").json()["grupos"] for p in g["perguntas"]}
    ok = logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": respostas}).json()
    assert ok["pendentes"] == 0 and ok["achados"] == [] and ok["simples_possivel"] is True
    respostas["socio_exterior"] = True
    r = logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": respostas}).json()
    assert r["simples_possivel"] is False and [a["chave"] for a in r["achados"]] == ["socio_exterior"] and r["achados"][0]["status"] == "impede"
    assert logado.get(f"/api/clientes/{cid}").json()["impedimentos"]["impedem"] == 1
    assert logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": {"inventada": True}}).status_code == 422
    assert logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": {}, "receita_outras_empresas": -1}).status_code == 422


def test_impedimento_que_depende_da_receita_global(logado: TestClient):
    cid = _cliente(logado)
    corpo = {"respostas": {"socio_administrador_de_outra": True}}
    r = logado.put(f"/api/clientes/{cid}/impedimentos", json=corpo).json()
    assert r["achados"][0]["status"] == "depende_da_receita" and r["simples_possivel"] is None
    # com a receita das outras empresas e a da simulação: R$ 600 mil + R$ 1 mi não passa de R$ 4,8 mi
    pequena = logado.put(f"/api/clientes/{cid}/impedimentos", params={"receita": 600000}, json={**corpo, "receita_outras_empresas": 1000000}).json()
    assert pequena["achados"] == []
    grande = logado.put(f"/api/clientes/{cid}/impedimentos", params={"receita": 600000}, json={**corpo, "receita_outras_empresas": 4500000}).json()
    assert grande["achados"][0]["status"] == "impede"


def test_simulacao_do_cliente_usa_os_impedimentos(logado: TestClient):
    cid = _cliente(logado)
    logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": {"debito_exigivel": True, "socio_mais_de_10_por_cento": True}, "receita_outras_empresas": 100000})
    sim = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=COMPLETA).json()
    s = _simples(sim["resultado"])
    assert s["aplicavel"] is False and any("art. 17, V" in a for a in s["alertas"])
    assert sim["entrada"]["impedimentos_simples"] and sim["resultado"]["melhor"] != "Simples Nacional"
    # receita global de R$ 700 mil: só o débito impede; o sócio com mais de 10% de outra empresa não
    assert len(sim["entrada"]["impedimentos_simples"]) == 1
    # a tela pode simular sem os impedimentos (por exemplo, depois de regularizar o débito)
    logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": {"debito_exigivel": False}})
    livre = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=COMPLETA).json()
    assert _simples(livre["resultado"])["aplicavel"] is True
    previa = logado.post("/api/simulacoes/previa/completa", json={**COMPLETA, "impedimentos_simples": ["Importação de combustíveis (LC 123/2006, art. 17, IX)"]}).json()
    assert _simples(previa)["aplicavel"] is False


def test_central_de_avisos(logado: TestClient):
    bloqueado = _cliente(logado)
    depende = logado.post("/api/clientes", json={"razao_social": "Depende", "regime_atual": "simples", "status": "ativo", "cnpj": "45997418000153"}).json()["id"]
    presumido = logado.post("/api/clientes", json={"razao_social": "Presumido", "regime_atual": "presumido", "status": "ativo", "cnpj": "11444777000161"}).json()["id"]
    logado.put(f"/api/clientes/{bloqueado}/impedimentos", json={"respostas": {"cessao_mao_de_obra": True}})
    logado.put(f"/api/clientes/{depende}/impedimentos", json={"respostas": {"socio_empresario_ou_socio_de_outra": True}})
    logado.put(f"/api/clientes/{presumido}/impedimentos", json={"respostas": {"cessao_mao_de_obra": True}})
    por = {a["cliente_id"]: a for a in logado.get("/api/avisos").json()["avisos"] if a["codigo"].startswith("impedimento")}
    assert por[bloqueado]["codigo"] == "impedimento_simples" and por[bloqueado]["gravidade"] == "critico" and "art. 17, XII" in por[bloqueado]["detalhe"]
    assert por[depende]["codigo"] == "impedimento_simples_receita" and por[depende]["gravidade"] == "atencao"
    assert presumido not in por  # só quem está no Simples


def test_outro_escritorio_nao_acessa(logado: TestClient):
    cid = _cliente(logado)
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get(f"/api/clientes/{cid}/impedimentos").status_code == 404
    assert logado.put(f"/api/clientes/{cid}/impedimentos", json={"respostas": {}}).status_code == 404
