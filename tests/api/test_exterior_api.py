"""Receita do exterior pela API: simulação completa, expressa, PDF e acompanhamento."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .test_acompanhamento import _notas, _planejar
from .test_recuperacao import _cliente

SERVICO = {"atividade": "servico_fator_r", "receita_bruta_anual": 600000, "pro_labore_anual": 240000,
           "outras_despesas_anual": 60000}


def _cid(c: TestClient) -> int:
    return c.post("/api/clientes", json={"razao_social": "Consultoria Maple Ltda", "atividade": "servico_fator_r"}).json()["id"]


def _totais(sim: dict) -> dict[str, float]:
    return {r["titulo"]: r["total"] for r in sim["resultado"]["regimes"]}


def test_completa_com_receita_do_exterior_paga_menos(logado: TestClient):
    cid = _cid(logado)
    interna = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=SERVICO).json()
    exportada = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**SERVICO, "receita_exterior_anual": 600000}).json()
    for regime in ("Simples Nacional", "Lucro Presumido", "Lucro Real"):
        assert _totais(exportada)[regime] < _totais(interna)[regime], regime
    r = exportada["resultado"]
    assert r["receita_exterior_anual"] == 600000.0 and r["variacao_cambial_anual"] == 0.0
    presumido = next(x for x in r["regimes"] if x["titulo"] == "Lucro Presumido")
    por_nome = {t["nome"]: t["valor"] for t in presumido["tributos"]}
    assert por_nome["PIS"] == por_nome["Cofins"] == por_nome["ISS"] == 0
    assert any("ingresso de divisas" in a for a in presumido["alertas"])
    assert exportada["entrada"]["receita_exterior_anual"] in (600000, "600000", 600000.0)


def test_variacao_cambial_ativa_aumenta_o_presumido(logado: TestClient):
    cid = _cid(logado)
    base = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**SERVICO, "receita_exterior_anual": 600000}).json()
    com = logado.post(f"/api/clientes/{cid}/simulacoes/completa",
                      json={**SERVICO, "receita_exterior_anual": 600000, "variacao_cambial_anual": 40000}).json()
    assert _totais(com)["Lucro Presumido"] > _totais(base)["Lucro Presumido"]
    assert _totais(com)["Simples Nacional"] == _totais(base)["Simples Nacional"]
    perda = logado.post(f"/api/clientes/{cid}/simulacoes/completa",
                        json={**SERVICO, "receita_exterior_anual": 600000, "variacao_cambial_anual": -40000}).json()
    assert _totais(perda)["Lucro Real"] < _totais(base)["Lucro Real"]  # a perda abate o lucro real


def test_exterior_maior_que_a_receita_e_recusado(logado: TestClient):
    cid = _cid(logado)
    r = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**SERVICO, "receita_exterior_anual": 700000})
    assert r.status_code == 422 and "não pode passar" in r.text
    r = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={**SERVICO, "receita_exterior_anual": -1})
    assert r.status_code == 422
    r = logado.post(f"/api/clientes/{cid}/simulacoes/expressa", json={
        "faturamento_mensal": 10000, "folha_mensal": 0, "atividade": "servico_fator_r", "receita_exterior_mensal": 20000})
    assert r.status_code == 422


def test_expressa_com_exterior_e_pdf(logado: TestClient):
    cid = _cid(logado)
    dados = {"faturamento_mensal": 50000, "folha_mensal": 0, "pro_labore_mensal": 20000, "atividade": "servico_fator_r"}
    sem = logado.post(f"/api/clientes/{cid}/simulacoes/expressa", json=dados).json()
    com = logado.post(f"/api/clientes/{cid}/simulacoes/expressa", json={**dados, "receita_exterior_mensal": 50000}).json()
    assert _totais(com)["Lucro Presumido"] < _totais(sem)["Lucro Presumido"]
    assert com["resultado"]["receita_exterior_anual"] == 600000.0
    pdf = logado.get(f"/api/simulacoes/{com['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_prospeccao_aceita_exterior(logado: TestClient):
    r = logado.post("/api/prospeccao", json={"cliente": {"razao_social": "Prospect Maple"}, "simulacao": {
        "faturamento_mensal": 50000, "folha_mensal": 0, "pro_labore_mensal": 20000, "atividade": "servico_fator_r",
        "receita_exterior_mensal": 30000}})
    assert r.status_code == 201, r.text
    assert r.json()["simulacao"]["resultado"]["receita_exterior_anual"] == 360000.0


def test_acompanhamento_mantem_a_proporcao_do_exterior(logado: TestClient):
    cid = _cliente(logado, atividade="comercio")
    _planejar(logado, cid, {"atividade": "comercio", "receita_bruta_anual": 1200000, "receita_exterior_anual": 600000,
                            "folha_clt_anual": 120000, "pro_labore_anual": 36000, "compras_anual": 720000})
    # notas reais bem abaixo do planejado: antes da correção, exterior (600 mil) passava da receita real e a reavaliação sumia
    _notas(logado, cid, [30000.0] * 12)
    ac = logado.get(f"/api/clientes/{cid}/acompanhamento").json()
    assert ac["reavaliacao"] is not None
    assert ac["desvio_receita"] is not None and ac["desvio_receita"] < 0
