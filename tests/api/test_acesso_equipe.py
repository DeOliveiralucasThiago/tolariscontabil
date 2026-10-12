from __future__ import annotations

import re

from fastapi.testclient import TestClient

from tolaris_api.emails import CAIXA_SAIDA

from .conftest import cadastrar

SENHA = "senha-segura-123"


def _token_do_ultimo_email() -> str:
    return re.search(r"token=([\w-]+)", CAIXA_SAIDA[-1].texto).group(1)


# --- Redefinição de senha ------------------------------------------------------------------
def test_esqueci_senha_nao_revela_email(client: TestClient):
    cadastrar(client)
    r1 = client.post("/api/auth/esqueci-senha", json={"email": "ana@escritorio.com.br"})
    r2 = client.post("/api/auth/esqueci-senha", json={"email": "ninguem@x.com"})
    assert r1.status_code == r2.status_code == 202 and r1.json() == r2.json()
    assert len(CAIXA_SAIDA) == 1 and CAIXA_SAIDA[0].para == ["ana@escritorio.com.br"]
    assert "/redefinir-senha?token=" in CAIXA_SAIDA[0].texto


def test_redefinir_senha_troca_a_senha_e_derruba_sessoes(client: TestClient):
    cadastrar(client)
    sessao_antiga = client.cookies.get("tolaris_sessao")
    client.post("/api/auth/esqueci-senha", json={"email": "ana@escritorio.com.br"})
    token = _token_do_ultimo_email()
    r = client.post("/api/auth/redefinir-senha", json={"token": token, "senha": "nova-senha-456"})
    assert r.status_code == 200
    # O mesmo link não vale duas vezes
    assert client.post("/api/auth/redefinir-senha", json={"token": token, "senha": "outra-senha-789"}).status_code == 400
    # A sessão de antes da troca não vale mais
    client.cookies.clear()
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {sessao_antiga}"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": SENHA}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "nova-senha-456"}).status_code == 200


def test_token_invalido(client: TestClient):
    r = client.post("/api/auth/redefinir-senha", json={"token": "x" * 43, "senha": "12345678"})
    assert r.status_code == 400


def test_limite_de_pedidos_de_redefinicao(client: TestClient):
    cadastrar(client)
    for _ in range(5):
        client.post("/api/auth/esqueci-senha", json={"email": "ana@escritorio.com.br"})
    assert len(CAIXA_SAIDA) == 3


def test_alterar_senha(logado: TestClient):
    assert logado.post("/api/auth/alterar-senha", json={"senha_atual": "errada", "nova_senha": "12345678"}).status_code == 400
    r = logado.post("/api/auth/alterar-senha", json={"senha_atual": SENHA, "nova_senha": "nova-senha-456"})
    assert r.status_code == 200
    assert logado.get("/api/auth/me").status_code == 200  # a sessão atual continua


# --- Limite de tentativas de login --------------------------------------------------------------
def test_bloqueio_apos_falhas(client: TestClient):
    cadastrar(client)
    client.cookies.clear()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "errada"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": SENHA})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_login_certo_zera_falhas(client: TestClient):
    cadastrar(client)
    client.cookies.clear()
    for _ in range(4):
        client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "errada"})
    assert client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": SENHA}).status_code == 200
    for _ in range(4):
        assert client.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "errada"}).status_code == 401


# --- Equipe --------------------------------------------------------------------------------------
def _convidar(c: TestClient, email="bia@escritorio.com.br", papel="membro") -> str:
    r = c.post("/api/equipe/convites", json={"email": email, "nome": "Bia", "papel": papel})
    assert r.status_code == 201, r.text
    return _token_do_ultimo_email()


def test_convite_aceite_e_permissoes(logado: TestClient):
    token = _convidar(logado)
    assert "Escritório Ana" in CAIXA_SAIDA[-1].assunto
    assert logado.get("/api/equipe").json()["convites"][0]["email"] == "bia@escritorio.com.br"
    publico = logado.get(f"/api/convites/{token}").json()
    assert publico == {"escritorio": "Escritório Ana", "email": "bia@escritorio.com.br", "nome": "Bia", "papel": "membro"}

    logado.post("/api/auth/logout")
    r = logado.post("/api/convites/aceitar", json={"token": token, "nome": "Bia Souza", "senha": "senha-bia-123"})
    assert r.status_code == 201 and r.json()["usuario"]["papel"] == "membro"
    assert r.json()["escritorio"]["nome"] == "Escritório Ana"
    # Membro usa o sistema, mas não administra
    assert logado.post("/api/clientes", json={"razao_social": "Cliente da Bia"}).status_code == 201
    assert logado.post("/api/equipe/convites", json={"email": "c@c.com"}).status_code == 403
    assert logado.patch("/api/escritorio", json={"nome": "Outro nome"}).status_code == 403
    assert logado.get("/api/equipe").json()["convites"] == []
    # Link já usado
    assert logado.post("/api/convites/aceitar", json={"token": token, "nome": "X Y", "senha": "12345678"}).status_code == 400


def test_convite_para_email_existente_e_revogacao(logado: TestClient):
    assert logado.post("/api/equipe/convites", json={"email": "ana@escritorio.com.br"}).status_code == 409
    token = _convidar(logado)
    cid = logado.get("/api/equipe").json()["convites"][0]["id"]
    assert logado.delete(f"/api/equipe/convites/{cid}").status_code == 204
    assert logado.get(f"/api/convites/{token}").status_code == 400


def test_novo_convite_substitui_o_anterior(logado: TestClient):
    antigo = _convidar(logado)
    novo = _convidar(logado, papel="admin")
    assert logado.get(f"/api/convites/{antigo}").status_code == 400
    assert logado.get(f"/api/convites/{novo}").json()["papel"] == "admin"
    assert len(logado.get("/api/equipe").json()["convites"]) == 1


def test_desativar_membro_e_ultimo_admin(logado: TestClient):
    eu = logado.get("/api/auth/me").json()["usuario"]["id"]
    assert logado.patch(f"/api/equipe/{eu}", json={"papel": "membro"}).status_code == 400
    assert logado.patch(f"/api/equipe/{eu}", json={"ativo": False}).status_code == 400
    token = _convidar(logado)
    admin_cookies = dict(logado.cookies)
    logado.cookies.clear()
    logado.post("/api/convites/aceitar", json={"token": token, "nome": "Bia Souza", "senha": "senha-bia-123"})
    bia_cookie = logado.cookies.get("tolaris_sessao")
    bia_id = logado.get("/api/auth/me").json()["usuario"]["id"]
    logado.cookies.clear()
    logado.cookies.update(admin_cookies)
    assert logado.patch(f"/api/equipe/{bia_id}", json={"ativo": False}).json()["ativo"] is False
    # Sessão da Bia cai e ela não consegue entrar
    logado.cookies.clear()
    assert logado.get("/api/auth/me", headers={"Authorization": f"Bearer {bia_cookie}"}).status_code == 401
    assert logado.post("/api/auth/login", json={"email": "bia@escritorio.com.br", "senha": "senha-bia-123"}).status_code == 401


def test_equipe_isolada_por_escritorio(client: TestClient):
    cadastrar(client, "a@a.com", "Escritório A")
    a_id = client.get("/api/auth/me").json()["usuario"]["id"]
    client.post("/api/auth/logout")
    cadastrar(client, "b@b.com", "Escritório B")
    assert [m["email"] for m in client.get("/api/equipe").json()["membros"]] == ["b@b.com"]
    assert client.patch(f"/api/equipe/{a_id}", json={"ativo": False}).status_code == 404
