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
    assert "Anexo VI" in r["aviso"]
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
