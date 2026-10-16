"""Dados contábeis por planilha: prévia, importação com mapeamento, reimportação, planejamento e isolamento."""

from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient
from openpyxl import Workbook

from tolaris_api import planilha as pl

from .conftest import cadastrar


def _cliente(c: TestClient) -> int:
    return c.post("/api/clientes", json={"razao_social": "Oficina Boa Roda"}).json()["id"]


def _csv(linhas: list[str], cab: str = "Mês;Faturamento;Custo das mercadorias;Folha de pagamento;Pró-labore") -> bytes:
    return ("﻿" + "\n".join([cab, *linhas])).encode("utf-8")


def _previa(c, cid, nome, conteudo):
    return c.post(f"/api/clientes/{cid}/financeiro/previa", files=[("arquivos", (nome, conteudo))])


def _importar(c, cid, nome, conteudo, mapeamento):
    return c.post(f"/api/clientes/{cid}/financeiro/importar", files=[("arquivos", (nome, conteudo))],
                  data={"mapeamento": json.dumps(mapeamento)})


MAPA = {"competencia": 0, "receita": 1, "compras": 2, "folha": 3, "pro_labore": 4}
DOZE = [f"2025-{m:02d};10000,00;6000,00;1500,00;500,00" for m in range(1, 13)]


def test_exige_login_e_modelo_baixa(logado: TestClient):
    r = logado.get("/api/financeiro/modelo.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")
    anonimo = TestClient(logado.app)
    assert anonimo.get("/api/financeiro/modelo.csv").status_code == 401
    assert anonimo.get("/api/clientes/1/financeiro").status_code == 401


def test_previa_sugere_as_colunas(logado: TestClient):
    cid = _cliente(logado)
    r = _previa(logado, cid, "dados.csv", _csv(DOZE))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total_linhas"] == 12 and len(j["amostra"]) == 5
    assert j["sugestao"] == {"competencia": 0, "receita": 1, "compras": 2, "folha": 3, "pro_labore": 4,
                             "despesas_creditaveis": None, "outras_despesas": None}
    assert j["rotulos"]["receita"].startswith("Receita")


def test_importa_12_meses_e_sugere_o_planejamento(logado: TestClient):
    cid = _cliente(logado)
    r = _importar(logado, cid, "dados.csv", _csv(DOZE), MAPA)
    assert r.status_code == 201, r.text
    assert r.json()["meses_novos"] == 12 and r.json()["meses_atualizados"] == 0
    estado = logado.get(f"/api/clientes/{cid}/financeiro").json()
    assert len(estado["meses"]) == 12 and estado["meses"][0]["receita"] == 10000.0
    assert estado["meses"][0]["outras_despesas"] is None
    p = estado["planejamento"]
    assert p["meses"] == 12 and not p["anualizado"] and p["periodo_inicio"] == "2025-01" and p["periodo_fim"] == "2025-12"
    assert (p["receita_bruta_anual"], p["compras_anual"], p["folha_clt_anual"], p["pro_labore_anual"]) == (120000, 72000, 18000, 6000)


def test_menos_de_12_meses_anualiza_e_avisa(logado: TestClient):
    cid = _cliente(logado)
    _importar(logado, cid, "d.csv", _csv(DOZE[:3]), MAPA)
    p = logado.get(f"/api/clientes/{cid}/financeiro").json()["planejamento"]
    assert p["meses"] == 3 and p["anualizado"] and p["receita_bruta_anual"] == 120000


def test_usa_so_os_ultimos_12_meses(logado: TestClient):
    cid = _cliente(logado)
    antigos = [f"2024-{m:02d};1,00;;;" for m in range(10, 13)]
    _importar(logado, cid, "d.csv", _csv([*antigos, *DOZE]), MAPA)
    p = logado.get(f"/api/clientes/{cid}/financeiro").json()["planejamento"]
    assert p["meses"] == 12 and p["periodo_inicio"] == "2025-01" and p["receita_bruta_anual"] == 120000


def test_reimportar_troca_so_o_que_veio_na_planilha(logado: TestClient):
    cid = _cliente(logado)
    _importar(logado, cid, "d.csv", _csv(["2026-01;10000,00;6000,00;1500,00;500,00"]), MAPA)
    r = _importar(logado, cid, "d.csv", _csv(["2026-01;12000,00;;;", "2026-02;9000,00;;;"]), MAPA)
    assert r.json()["meses_novos"] == 1 and r.json()["meses_atualizados"] == 1
    meses = logado.get(f"/api/clientes/{cid}/financeiro").json()["meses"]
    assert meses[0] == {"competencia": "2026-01", "receita": 12000.0, "compras": 6000.0, "folha": 1500.0, "pro_labore": 500.0,
                        "despesas_creditaveis": None, "outras_despesas": None}
    assert meses[1]["receita"] == 9000.0 and meses[1]["compras"] is None


def test_xlsx_e_linhas_ignoradas(logado: TestClient):
    cid = _cliente(logado)
    wb = Workbook()
    ws = wb.active
    ws.append(["Competência", "Receita"])
    ws.append(["01/2026", 5000.25])
    ws.append(["fevereiro", 100])
    ws.append(["03/2026", "R$ 1.000,00"])
    buf = io.BytesIO()
    wb.save(buf)
    r = _importar(logado, cid, "d.xlsx", buf.getvalue(), {"competencia": 0, "receita": 1})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["competencias"] == ["2026-01", "2026-03"] and j["total_ignoradas"] == 1
    assert j["ignoradas"][0]["linha"] == 3 and "competência" in j["ignoradas"][0]["motivo"]
    assert logado.get(f"/api/clientes/{cid}/financeiro").json()["meses"][0]["receita"] == 5000.25


def test_erros_claros(logado: TestClient):
    cid = _cliente(logado)
    ok = _csv(DOZE[:1])
    assert _importar(logado, cid, "d.csv", ok, {"receita": 1}).status_code == 400  # sem competência
    assert _importar(logado, cid, "d.csv", ok, {"competencia": 0, "receita": 9}).status_code == 400
    r = logado.post(f"/api/clientes/{cid}/financeiro/importar", files=[("arquivos", ("d.csv", ok))], data={"mapeamento": "isso não é json"})
    assert r.status_code == 400 and "Mapeamento" in r.json()["detail"]
    r = _importar(logado, cid, "d.csv", _csv(["abc;1;;;"]), MAPA)
    assert r.status_code == 400 and "Nenhuma linha" in r.json()["detail"]
    assert _importar(logado, cid, "d.pdf", b"%PDF", MAPA).status_code == 400
    assert _previa(logado, cid, "d.csv", b"x" * (pl.LIMITE_BYTES + 1)).status_code in (400, 413)
    duas = logado.post(f"/api/clientes/{cid}/financeiro/previa", files=[("arquivos", ("a.csv", ok)), ("arquivos", ("b.csv", ok))])
    assert duas.status_code == 400
    assert logado.get(f"/api/clientes/{cid}/financeiro").json() == {"meses": [], "planejamento": None}


def test_apagar_e_isolamento_entre_escritorios(logado: TestClient):
    cid = _cliente(logado)
    _importar(logado, cid, "d.csv", _csv(DOZE), MAPA)
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get(f"/api/clientes/{cid}/financeiro").status_code == 404
    assert _importar(logado, cid, "d.csv", _csv(DOZE), MAPA).status_code == 404
    assert logado.delete(f"/api/clientes/{cid}/financeiro").status_code == 404
    logado.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "senha-segura-123"})
    assert logado.delete(f"/api/clientes/{cid}/financeiro").status_code == 204
    assert logado.get(f"/api/clientes/{cid}/financeiro").json()["meses"] == []


def test_excluir_cliente_leva_os_dados_contabeis(logado: TestClient):
    cid = _cliente(logado)
    _importar(logado, cid, "d.csv", _csv(DOZE), MAPA)
    assert logado.delete(f"/api/clientes/{cid}").status_code == 204
    from sqlalchemy import func, select
    from tolaris_api.db import get_db
    from tolaris_api.models import FinanceiroMensal

    db = next(logado.app.dependency_overrides[get_db]())
    try:
        assert db.scalar(select(func.count()).select_from(FinanceiroMensal)) == 0
    finally:
        db.close()
