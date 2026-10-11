from __future__ import annotations

import io

from fastapi.testclient import TestClient

from tolaris_api.cnpj import cnpj_valido, interpretar_brasilapi, sugerir_atividade
from tolaris_api.seguranca import hash_senha, verificar_senha
from tolaris_motor import Atividade

from .conftest import CNPJ_VALIDO, cadastrar

EXPRESSA = {"faturamento_mensal": 50000, "folha_mensal": 8000, "pro_labore_mensal": 5000, "atividade": "servico_fator_r"}
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cf000000030101005b2a5d4f0000000049454e44ae426082"
)


# --- Unidades ----------------------------------------------------------------------
def test_senha_scrypt():
    h = hash_senha("abc12345")
    assert h.startswith("scrypt$") and verificar_senha("abc12345", h)
    assert not verificar_senha("errada", h)
    assert not verificar_senha("abc12345", "lixo")


def test_validacao_cnpj():
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-82")
    assert not cnpj_valido("11111111111111")
    assert not cnpj_valido("123")


def test_sugestao_de_atividade_por_cnae():
    assert sugerir_atividade("4711302")[0] is Atividade.COMERCIO
    assert sugerir_atividade("6201501")[0] is Atividade.SERVICO_FATOR_R
    assert sugerir_atividade("6911701")[0] is Atividade.SERVICO_ANEXO_IV  # advocacia
    assert sugerir_atividade("6920601")[0] is Atividade.SERVICO_ANEXO_III  # contabilidade
    assert sugerir_atividade("1091101")[0] is Atividade.INDUSTRIA
    assert sugerir_atividade("6422100")[0] is None
    assert "confirme" in sugerir_atividade("4711302")[1]


def test_interpretar_resposta_brasilapi():
    d = interpretar_brasilapi({
        "cnpj": "11222333000181", "razao_social": "X LTDA", "nome_fantasia": "", "cnae_fiscal": 4711302,
        "municipio": "CAMPINAS", "uf": "SP", "email": "A@B.COM", "opcao_pelo_simples": True, "opcao_pelo_mei": False,
    })
    assert d.nome_fantasia is None and d.cnae_principal == "4711302" and d.email == "a@b.com"
    assert d.como_dict()["regime_sugerido"] == "simples"


# --- Autenticação --------------------------------------------------------------------
def test_cadastro_login_logout(client: TestClient):
    sessao = cadastrar(client)
    assert sessao["escritorio"]["nome"] == "Escritório Ana"
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "x"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "ANA@escritorio.com.br", "senha": "senha-segura-123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["usuario"]["email"] == "ana@escritorio.com.br"


def test_cookie_httponly(client: TestClient):
    r = client.post("/api/auth/cadastro", json={
        "escritorio_nome": "Escritório F", "nome": "Fulano", "email": "f@e.com", "senha": "12345678"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_email_duplicado(client: TestClient):
    cadastrar(client)
    r = client.post("/api/auth/cadastro", json={
        "escritorio_nome": "Outro", "nome": "Outra", "email": "ana@escritorio.com.br", "senha": "12345678"})
    assert r.status_code == 409


def test_rotas_protegidas(client: TestClient):
    for rota in ("/api/clientes", "/api/painel", f"/api/cnpj/{CNPJ_VALIDO}"):
        assert client.get(rota).status_code == 401
    assert client.get("/api/clientes", headers={"Authorization": "Bearer invalido"}).status_code == 401


# --- Escritório -----------------------------------------------------------------------
def test_atualizar_escritorio_e_logo(logado: TestClient):
    r = logado.patch("/api/escritorio", json={"cor_primaria": "#0a7f5a", "crc": "SP-123456/O", "cnpj": "11.222.333/0001-81"})
    assert r.status_code == 200 and r.json()["escritorio"]["cnpj"] == CNPJ_VALIDO
    assert logado.patch("/api/escritorio", json={"cor_primaria": "verde"}).status_code == 422
    r = logado.put("/api/escritorio/logo", files={"arquivo": ("logo.png", io.BytesIO(PNG_1PX), "image/png")})
    assert r.status_code == 200 and r.json()["escritorio"]["tem_logo"]
    assert logado.get("/api/escritorio/logo").headers["content-type"] == "image/png"
    r = logado.put("/api/escritorio/logo", files={"arquivo": ("x.png", io.BytesIO(b"<svg/>"), "image/png")})
    assert r.status_code == 415


# --- Clientes e isolamento entre escritórios ---------------------------------------------
def test_crud_clientes(logado: TestClient):
    r = logado.post("/api/clientes", json={"razao_social": "Padaria Pão Bom", "cnpj": "11.222.333/0001-81", "email": ""})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["cnpj"] == CNPJ_VALIDO and r.json()["status"] == "prospect"
    assert logado.post("/api/clientes", json={"razao_social": "Dup", "cnpj": CNPJ_VALIDO}).status_code == 409
    assert logado.post("/api/clientes", json={"razao_social": "Ruim", "cnpj": "123"}).status_code == 422
    r = logado.patch(f"/api/clientes/{cid}", json={"status": "ativo", "regime_atual": "simples"})
    assert r.json()["status"] == "ativo"
    assert [c["id"] for c in logado.get("/api/clientes?busca=pão").json()] == [cid]
    assert logado.get("/api/clientes?status=prospect").json() == []
    assert logado.delete(f"/api/clientes/{cid}").status_code == 204
    assert logado.get(f"/api/clientes/{cid}").status_code == 404


def test_isolamento_entre_escritorios(client: TestClient):
    cadastrar(client, "a@a.com", "Escritório A")
    cid = client.post("/api/clientes", json={"razao_social": "Cliente do A"}).json()["id"]
    sid = client.post(f"/api/clientes/{cid}/simulacoes/expressa", json=EXPRESSA).json()["id"]
    client.post("/api/auth/logout")
    cadastrar(client, "b@b.com", "Escritório B")
    assert client.get("/api/clientes").json() == []
    assert client.get(f"/api/clientes/{cid}").status_code == 404
    assert client.patch(f"/api/clientes/{cid}", json={"razao_social": "hack"}).status_code == 404
    assert client.get(f"/api/simulacoes/{sid}").status_code == 404
    assert client.get(f"/api/simulacoes/{sid}/proposta.pdf").status_code == 404
    # O mesmo CNPJ pode existir em escritórios diferentes
    assert client.post("/api/clientes", json={"razao_social": "Cliente do B", "cnpj": CNPJ_VALIDO}).status_code == 201


# --- CNPJ --------------------------------------------------------------------------------
def test_consulta_cnpj(logado: TestClient):
    r = logado.get("/api/cnpj/11.222.333000181")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["razao_social"] == "ACME CONSULTORIA LTDA"
    assert d["atividade_sugerida"] == "servico_fator_r" and d["regime_sugerido"] == "simples"
    assert logado.get("/api/cnpj/11222333000182").status_code == 422
    assert logado.get("/api/cnpj/11444777000161").status_code == 404


# --- Simulações e prospecção ----------------------------------------------------------------
def test_previa_expressa(logado: TestClient):
    r = logado.post("/api/simulacoes/previa/expressa", json=EXPRESSA)
    assert r.status_code == 200
    d = r.json()
    assert d["melhor"] == "Simples Nacional" and d["receita_anual"] == 600000
    simples = next(x for x in d["regimes"] if x["titulo"] == "Simples Nacional")
    assert simples["total"] == 107100 and simples["memoria"] and simples["alertas"]
    assert logado.post("/api/simulacoes/previa/expressa", json={**EXPRESSA, "faturamento_mensal": 0}).status_code == 422


def test_prospeccao_cria_e_reaproveita_cliente(logado: TestClient):
    corpo = {"cliente": {"razao_social": "ACME", "cnpj": CNPJ_VALIDO}, "simulacao": EXPRESSA}
    r1 = logado.post("/api/prospeccao", json=corpo)
    assert r1.status_code == 201, r1.text
    cid = r1.json()["cliente"]["id"]
    assert r1.json()["cliente"]["atividade"] == "servico_fator_r"
    logado.patch(f"/api/clientes/{cid}", json={"status": "ativo"})
    r2 = logado.post("/api/prospeccao", json=corpo)
    assert r2.json()["cliente"]["id"] == cid
    assert r2.json()["cliente"]["status"] == "ativo"  # não volta para prospect
    assert r2.json()["cliente"]["total_simulacoes"] == 2


def test_simulacao_completa_e_pdf(logado: TestClient):
    logado.put("/api/escritorio/logo", files={"arquivo": ("logo.png", io.BytesIO(PNG_1PX), "image/png")})
    cid = logado.post("/api/clientes", json={"razao_social": "Comércio Bom", "atividade": "comercio"}).json()["id"]
    r = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json={
        "atividade": "comercio", "receita_bruta_anual": 2000000, "folha_clt_anual": 240000,
        "pro_labore_anual": 36000, "compras_anual": 1200000, "despesas_creditaveis_anual": 80000,
    })
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["tipo"] == "completa" and "Simples Nacional" in sim["titulo"]
    assert logado.get(f"/api/clientes/{cid}/simulacoes").json()[0]["id"] == sim["id"]
    pdf = logado.get(f"/api/simulacoes/{sim['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 10_000


def test_painel(logado: TestClient):
    r = logado.post("/api/prospeccao", json={"cliente": {"razao_social": "P1"}, "simulacao": EXPRESSA}).json()
    d = logado.get("/api/painel").json()
    assert d["prospects"] == 1 and d["simulacoes_mes"] == 1
    economia = d["economia_identificada_mes"]
    assert economia == r["simulacao"]["resultado"]["economia_vs_pior"] > 0
    # Nova simulação do mesmo cliente substitui a anterior na economia (não soma duas vezes)
    logado.post(f"/api/clientes/{r['cliente']['id']}/simulacoes/expressa", json=EXPRESSA)
    d = logado.get("/api/painel").json()
    assert d["simulacoes_mes"] == 2 and d["economia_identificada_mes"] == economia
    assert d["ultimas_simulacoes"][0]["cliente"] == "P1"


def test_pdf_nao_busca_urls_externas_e_escapa_rodape():
    import pytest

    from tolaris_api.pdf import _css_string, _fetcher_somente_data

    assert "</style>" not in _css_string('A "B" </style><img src=http://x>')
    fetcher = _fetcher_somente_data()
    for url in ("http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "https://exemplo.com/a.png"):
        with pytest.raises(ValueError):
            fetcher.fetch(url)
    fetcher.fetch("data:text/plain;base64,b2k=")


def test_pdf_com_html_no_nome_do_cliente(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": '<img src="http://exemplo.invalid/x.png"> & "Cia"'}).json()["id"]
    sid = logado.post(f"/api/clientes/{cid}/simulacoes/expressa", json=EXPRESSA).json()["id"]
    pdf = logado.get(f"/api/simulacoes/{sid}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
