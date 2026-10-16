"""Verificação em duas etapas: configurar, entrar com o código, recuperação, redefinição pelo administrador."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tolaris_api import totp
from tolaris_api.config import get_settings
from tolaris_api.db import get_db
from tolaris_api.models import RegistroAuditoria, Usuario

from .conftest import cadastrar

SENHA = "senha-segura-123"
EMAIL = "ana@escritorio.com.br"


@pytest.fixture()
def relogio(monkeypatch):
    """Intervalo de 30 s controlado pelo teste."""
    estado = {"passo": 1_000_000}
    monkeypatch.setattr(totp, "passo_atual", lambda agora=None: estado["passo"])
    return estado


def _banco(c):
    return next(c.app.dependency_overrides[get_db]())


def _ativar(c: TestClient, relogio) -> tuple[str, list[str]]:
    r = c.post("/api/auth/2fa/configurar", json={"senha": SENHA})
    assert r.status_code == 200, r.text
    segredo = r.json()["segredo"]
    r = c.post("/api/auth/2fa/ativar", json={"codigo": totp.codigo(segredo, relogio["passo"])})
    assert r.status_code == 200, r.text
    return segredo, r.json()["codigos_recuperacao"]


def _login(c: TestClient):
    return c.post("/api/auth/login", json={"email": EMAIL, "senha": SENHA})


def _auditoria(c: TestClient, acao: str) -> list[RegistroAuditoria]:
    db = _banco(c)
    try:
        return list(db.scalars(select(RegistroAuditoria).where(RegistroAuditoria.acao == acao)))
    finally:
        db.close()


def test_configurar_devolve_segredo_uri_e_qr(logado: TestClient, relogio):
    r = logado.post("/api/auth/2fa/configurar", json={"senha": SENHA})
    assert r.status_code == 200
    j = r.json()
    assert len(j["segredo"]) == 32 and j["uri"].startswith("otpauth://totp/") and j["segredo"] in j["uri"]
    assert j["qr_svg"].startswith("<svg") and "</svg>" in j["qr_svg"]
    assert logado.get("/api/auth/me").json()["usuario"]["totp_ativo"] is False  # ainda não confirmou
    assert logado.post("/api/auth/2fa/configurar", json={"senha": "errada"}).status_code == 400


def test_segredo_fica_cifrado_no_banco(logado: TestClient, relogio):
    segredo = logado.post("/api/auth/2fa/configurar", json={"senha": SENHA}).json()["segredo"]
    db = _banco(logado)
    try:
        u = db.scalar(select(Usuario))
        assert u.totp_segredo_cifrado and segredo not in u.totp_segredo_cifrado
    finally:
        db.close()


def test_ativar_exige_codigo_certo_e_devolve_codigos_de_recuperacao(logado: TestClient, relogio):
    segredo = logado.post("/api/auth/2fa/configurar", json={"senha": SENHA}).json()["segredo"]
    assert logado.post("/api/auth/2fa/ativar", json={"codigo": "000000"}).status_code == 400
    assert logado.get("/api/auth/me").json()["usuario"]["totp_ativo"] is False
    r = logado.post("/api/auth/2fa/ativar", json={"codigo": totp.codigo(segredo, relogio["passo"])})
    assert r.status_code == 200 and len(r.json()["codigos_recuperacao"]) == 8
    me = logado.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["usuario"]["totp_ativo"] is True  # a sessão atual continua
    assert logado.post("/api/auth/2fa/configurar", json={"senha": SENHA}).status_code == 409
    assert len(_auditoria(logado, "2fa_ativado")) == 1


def test_login_em_duas_etapas(logado: TestClient, relogio):
    segredo, _ = _ativar(logado, relogio)
    novo = TestClient(logado.app)
    r = _login(novo)
    assert r.status_code == 200 and r.json()["requer_2fa"] is True and "usuario" not in r.json()
    assert not novo.cookies  # senha certa não abre sessão
    assert novo.get("/api/auth/me").status_code == 401
    token = r.json()["token_2fa"]
    # o token da etapa do código nunca vale como sessão
    assert novo.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    relogio["passo"] += 1
    r = novo.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": totp.codigo(segredo, relogio["passo"])})
    assert r.status_code == 200 and r.json()["usuario"]["email"] == EMAIL
    assert novo.get("/api/auth/me").status_code == 200
    assert len(_auditoria(logado, "login")) == 1 and _auditoria(logado, "login")[0].detalhe == {"segundo_fator": "aplicativo"}


def test_codigo_errado_e_codigo_repetido(logado: TestClient, relogio):
    segredo, _ = _ativar(logado, relogio)
    token = _login(TestClient(logado.app)).json()["token_2fa"]
    c = TestClient(logado.app)
    assert c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": "123456"}).status_code == 401
    assert len(_auditoria(logado, "login_2fa_falha")) == 1
    # o código usado na ativação já foi consumido: não serve para entrar
    assert c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": totp.codigo(segredo, relogio["passo"])}).status_code == 401
    relogio["passo"] += 1
    assert c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": totp.codigo(segredo, relogio["passo"])}).status_code == 200
    # e o mesmo código não abre uma segunda sessão
    outro = TestClient(logado.app)
    token2 = _login(outro).json()["token_2fa"]
    assert outro.post("/api/auth/login/2fa", json={"token_2fa": token2, "codigo": totp.codigo(segredo, relogio["passo"])}).status_code == 401


def test_token_invalido_ou_de_outra_pessoa(logado: TestClient, relogio):
    _ativar(logado, relogio)
    c = TestClient(logado.app)
    assert c.post("/api/auth/login/2fa", json={"token_2fa": "x" * 40, "codigo": "123456"}).status_code == 401
    # token de sessão comum não serve como token da etapa do código
    sessao = logado.cookies.get(get_settings().cookie_nome)
    assert c.post("/api/auth/login/2fa", json={"token_2fa": sessao, "codigo": "123456"}).status_code == 401


def test_tentativas_de_codigo_tem_limite(logado: TestClient, relogio):
    _ativar(logado, relogio)
    c = TestClient(logado.app)
    token = _login(c).json()["token_2fa"]
    cfg = get_settings()
    for _ in range(cfg.login_max_falhas_email):
        assert c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": "000000"}).status_code == 401
    r = c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": "000000"})
    assert r.status_code == 429
    # senha certa não zera o limite de quem está adivinhando o código
    assert _login(c).status_code == 429


def test_codigo_de_recuperacao_entra_uma_vez_so(logado: TestClient, relogio):
    _, recuperacao = _ativar(logado, relogio)
    c = TestClient(logado.app)
    token = _login(c).json()["token_2fa"]
    r = c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": recuperacao[0]})
    assert r.status_code == 200
    assert len(_auditoria(logado, "codigo_recuperacao_usado")) == 1
    outro = TestClient(logado.app)
    token2 = _login(outro).json()["token_2fa"]
    assert outro.post("/api/auth/login/2fa", json={"token_2fa": token2, "codigo": recuperacao[0]}).status_code == 401
    assert outro.post("/api/auth/login/2fa", json={"token_2fa": token2, "codigo": recuperacao[1]}).status_code == 200


def test_esqueci_a_senha_nao_pula_o_segundo_fator(logado: TestClient, relogio, client, caixa_limpa):
    _ativar(logado, relogio)
    anonimo = TestClient(logado.app)
    anonimo.post("/api/auth/esqueci-senha", json={"email": EMAIL})
    texto = caixa_limpa[-1].texto
    token = texto.split("token=")[1].split()[0]
    r = anonimo.post("/api/auth/redefinir-senha", json={"token": token, "senha": "outra-senha-123"})
    assert r.status_code == 200 and r.json()["requer_2fa"] is True and not anonimo.cookies


def test_desativar_pede_senha_e_codigo(logado: TestClient, relogio):
    segredo, recuperacao = _ativar(logado, relogio)
    relogio["passo"] += 1
    codigo = totp.codigo(segredo, relogio["passo"])
    assert logado.post("/api/auth/2fa/desativar", json={"senha": "errada", "codigo": codigo}).status_code == 400
    assert logado.post("/api/auth/2fa/desativar", json={"senha": SENHA, "codigo": "000000"}).status_code == 400
    assert logado.post("/api/auth/2fa/desativar", json={"senha": SENHA, "codigo": recuperacao[0]}).status_code == 204
    me = logado.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["usuario"]["totp_ativo"] is False
    assert "requer_2fa" not in _login(TestClient(logado.app)).json()
    assert len(_auditoria(logado, "2fa_desativado")) == 1
    assert logado.post("/api/auth/2fa/desativar", json={"senha": SENHA, "codigo": codigo}).status_code == 409


def test_novos_codigos_invalidam_os_antigos(logado: TestClient, relogio):
    segredo, antigos = _ativar(logado, relogio)
    relogio["passo"] += 1
    r = logado.post("/api/auth/2fa/novos-codigos", json={"senha": SENHA, "codigo": totp.codigo(segredo, relogio["passo"])})
    assert r.status_code == 200
    novos = r.json()["codigos_recuperacao"]
    assert len(novos) == 8 and not set(novos) & set(antigos)
    c = TestClient(logado.app)
    token = _login(c).json()["token_2fa"]
    assert c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": antigos[0]}).status_code == 401
    assert c.post("/api/auth/login/2fa", json={"token_2fa": token, "codigo": novos[0]}).status_code == 200


def test_ativar_derruba_as_outras_sessoes(logado: TestClient, relogio):
    outra = TestClient(logado.app)
    _login(outra)
    assert outra.get("/api/auth/me").status_code == 200
    _ativar(logado, relogio)
    assert outra.get("/api/auth/me").status_code == 401
    assert logado.get("/api/auth/me").status_code == 200


def test_administrador_redefine_a_verificacao_de_um_membro(logado: TestClient, relogio):
    # segunda pessoa na equipe, com 2FA, que perdeu o celular
    convite = logado.post("/api/equipe/convites", json={"email": "bia@escritorio.com.br", "nome": "Bia", "papel": "membro"})
    assert convite.status_code == 201
    db = _banco(logado)
    try:
        bia = Usuario(escritorio_id=db.scalar(select(Usuario)).escritorio_id, nome="Bia", email="bia@escritorio.com.br",
                      senha_hash=db.scalar(select(Usuario)).senha_hash, papel="membro")
        db.add(bia)
        db.commit()
        bia_id = bia.id
    finally:
        db.close()
    bia_c = TestClient(logado.app)
    bia_c.post("/api/auth/login", json={"email": "bia@escritorio.com.br", "senha": SENHA})
    segredo = bia_c.post("/api/auth/2fa/configurar", json={"senha": SENHA}).json()["segredo"]
    assert bia_c.post("/api/auth/2fa/ativar", json={"codigo": totp.codigo(segredo, relogio["passo"])}).status_code == 200
    equipe = {m["email"]: m for m in logado.get("/api/equipe").json()["membros"]}
    assert equipe["bia@escritorio.com.br"]["totp_ativo"] is True and equipe[EMAIL]["totp_ativo"] is False

    assert bia_c.post(f"/api/equipe/{bia_id}/redefinir-2fa").status_code == 403  # membro não pode
    assert logado.post(f"/api/equipe/{bia_id}/redefinir-2fa").status_code == 204
    assert bia_c.get("/api/auth/me").status_code == 401  # sessão derrubada
    assert "requer_2fa" not in TestClient(logado.app).post("/api/auth/login", json={"email": "bia@escritorio.com.br", "senha": SENHA}).json()
    assert len(_auditoria(logado, "2fa_resetado")) == 1
    assert logado.post(f"/api/equipe/{bia_id}/redefinir-2fa").status_code == 409  # já está sem


def test_administrador_so_redefine_no_proprio_escritorio(logado: TestClient, relogio):
    db = _banco(logado)
    try:
        meu_id = db.scalar(select(Usuario)).id
    finally:
        db.close()
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.post(f"/api/equipe/{meu_id}/redefinir-2fa").status_code == 404
