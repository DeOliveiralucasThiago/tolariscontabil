"""CNAEs do cliente: secundários vindos da Receita, classificação orientativa e candidatos ao Anexo III."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tolaris_api import cnpj

BRASILAPI = {
    "cnpj": "11222333000181", "razao_social": "TECH LTDA", "cnae_fiscal": 6201501, "cnae_fiscal_descricao": "Desenvolvimento sob encomenda",
    "cnaes_secundarios": [
        {"codigo": 8599604, "descricao": "Treinamento em desenvolvimento profissional e gerencial"},
        {"codigo": 8599604, "descricao": "repetido"},
        {"codigo": 0, "descricao": "Não informada"},
        {"codigo": "lixo"},
        {"descricao": "sem código"},
        {"codigo": 6911701, "descricao": "Serviços advocatícios"},
    ],
}


def test_interpreta_os_cnaes_secundarios_da_brasilapi():
    d = cnpj.interpretar_brasilapi(BRASILAPI)
    assert [c["codigo"] for c in d.cnaes_secundarios] == ["8599604", "6911701"]
    assert d.cnaes_secundarios[0]["descricao"].startswith("Treinamento")
    assert cnpj.interpretar_brasilapi({**BRASILAPI, "cnaes_secundarios": None}).cnaes_secundarios == []
    assert d.como_dict()["cnaes_secundarios"] == d.cnaes_secundarios


def test_classifica_e_separa_candidatos_ao_anexo_iii():
    r = cnpj.classificar_cnaes("6201501", "Software", [{"codigo": "8599604", "descricao": "Treinamento"},
                                                       {"codigo": "6911701", "descricao": "Advocacia"}], None)
    assert r["atividade_fator_r"] is True
    principal, treino, advocacia = r["cnaes"]
    assert principal["principal"] and principal["atividade"] == "servico_fator_r" and "fator R" in principal["anexo"]
    assert treino["atividade"] == "servico_anexo_iii" and advocacia["atividade"] == "servico_anexo_iv"
    assert [c["codigo"] for c in r["anexo_iii_no_cadastro"]] == ["8599604"]
    assert "art. 25" in r["aviso"]
    # empresa que não é do fator R não tem o que "segregar"
    comercio = cnpj.classificar_cnaes("4711302", "Mercado", [{"codigo": "8599604", "descricao": "x"}], "comercio")
    assert comercio["atividade_fator_r"] is False and comercio["anexo_iii_no_cadastro"] == []
    assert cnpj.classificar_cnaes(None, None, None, None)["cnaes"] == []


def test_cnaes_do_cliente_pela_api(logado: TestClient):
    cid = logado.post("/api/clientes", json={
        "razao_social": "Tech Ltda", "atividade": "servico_fator_r", "cnae_principal": "6201501",
        "cnaes_secundarios": [{"codigo": "8599604", "descricao": "Treinamento"}],
    })
    assert cid.status_code == 201, cid.text
    assert cid.json()["cnaes_secundarios"] == [{"codigo": "8599604", "descricao": "Treinamento"}]
    r = logado.get(f"/api/clientes/{cid.json()['id']}/cnaes").json()
    assert len(r["cnaes"]) == 2 and r["anexo_iii_no_cadastro"][0]["codigo"] == "8599604"
    # cliente sem secundários continua funcionando
    sem = logado.post("/api/clientes", json={"razao_social": "Sem CNAE"}).json()
    assert sem["cnaes_secundarios"] is None
    assert logado.get(f"/api/clientes/{sem['id']}/cnaes").json()["cnaes"] == []
    assert logado.post("/api/clientes", json={"razao_social": "X", "cnaes_secundarios": [{"codigo": "123"}]}).status_code == 422
    assert logado.get("/api/clientes/99999/cnaes").status_code == 404


def test_busca_de_cnaes_pela_api(logado: TestClient):
    anonimo = TestClient(logado.app)
    assert anonimo.get("/api/cnae").status_code == 401 and anonimo.get("/api/cnae/6201501").status_code == 401
    r = logado.get("/api/cnae", params={"q": "treinamento", "anexo": "iii_direto", "limite": 5}).json()
    assert r["total"] >= 2 and len(r["itens"]) <= 5 and all(i["anexo"] == "Anexo III" for i in r["itens"])
    assert r["fontes"]["atualizado_em"] and "Contabilizei" in r["fontes"]["anexos"]
    assert logado.get("/api/cnae", params={"anexo": "qualquer"}).status_code == 422
    assert logado.get("/api/cnae", params={"limite": 999}).status_code == 422
    vedados = logado.get("/api/cnae", params={"q": "bancos", "anexo": "vedado"}).json()["itens"]
    assert vedados and all(v["vedacao"] for v in vedados)
    d = logado.get("/api/cnae/6209100").json()
    assert d["codigo"] == "6209100" and d["fator_r"] is True and d["confianca"] == "tabela"
    assert logado.get("/api/cnae/0000000").status_code == 404
    div = logado.get("/api/cnae/divisoes").json()
    assert len(div["divisoes"]) == 87 and {f["codigo"] for f in div["filtros"]} >= {"iii_direto", "fator_r", "vedado"}


def test_cnaes_do_cliente_marcam_os_vedados(logado: TestClient):
    cid = logado.post("/api/clientes", json={
        "razao_social": "Mista Ltda", "atividade": "servico_fator_r", "cnae_principal": "6201501",
        "cnaes_secundarios": [{"codigo": "6421200", "descricao": "Bancos comerciais"}],
    }).json()["id"]
    r = logado.get(f"/api/clientes/{cid}/cnaes").json()
    assert [v["codigo"] for v in r["vedados"]] == ["6421200"] and r["cnaes"][1]["anexo"] == "Vedado ao Simples"
    assert r["anexo_iii_no_cadastro"] == []


def test_consulta_de_cnpj_ja_traz_os_cnaes_classificados():
    d = cnpj.interpretar_brasilapi(BRASILAPI).como_dict()
    c = d["cnaes_classificados"]
    assert [i["codigo"] for i in c["cnaes"]] == ["6201501", "8599604", "6911701"]
    assert c["atividade_fator_r"] is True and [i["codigo"] for i in c["anexo_iii_no_cadastro"]] == ["8599604"]
    assert c["cnaes"][2]["atividade"] == "servico_anexo_iv"


def test_prospeccao_guarda_os_cnaes_secundarios(logado: TestClient):
    corpo = {
        "cliente": {"razao_social": "Tech Ltda", "cnpj": "11222333000181", "cnae_principal": "6201501",
                    "cnaes_secundarios": [{"codigo": "8599604", "descricao": "Treinamento"}]},
        "simulacao": {"faturamento_mensal": 50000, "folha_mensal": 0, "atividade": "servico_fator_r"},
    }
    r = logado.post("/api/prospeccao", json=corpo).json()
    assert r["cliente"]["cnaes_secundarios"] == [{"codigo": "8599604", "descricao": "Treinamento"}]
    cnaes = logado.get(f"/api/clientes/{r['cliente']['id']}/cnaes").json()
    assert [c["codigo"] for c in cnaes["anexo_iii_no_cadastro"]] == ["8599604"]
    # prospectar de novo o mesmo CNPJ sem secundários não apaga os que já existem
    sem = {**corpo, "cliente": {"razao_social": "Tech Ltda", "cnpj": "11222333000181"}}
    again = logado.post("/api/prospeccao", json=sem).json()
    assert again["cliente"]["id"] == r["cliente"]["id"] and len(again["cliente"]["cnaes_secundarios"]) == 1
