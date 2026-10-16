"""Registro de atividades: o que é gravado, quem pode ver e o que nunca aparece."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tolaris_api.acesso import agora
from tolaris_api.auditoria import ROTULOS, auditar
from tolaris_api.db import get_db
from tolaris_api.models import RegistroAuditoria, Usuario

from .conftest import CNPJ_VALIDO, cadastrar
from .test_importacao import nfe

SENHA = "senha-segura-123"


def _banco(c):
    return next(c.app.dependency_overrides[get_db]())


def _registros(c: TestClient, **filtros) -> dict:
    r = c.get("/api/escritorio/auditoria", params={"limite": 200, **filtros})
    assert r.status_code == 200, r.text
    return r.json()


def _acoes(c: TestClient, **filtros) -> list[str]:
    return [i["acao"] for i in _registros(c, **filtros)["itens"]]


def test_so_administrador_ve_o_registro(logado: TestClient):
    assert TestClient(logado.app).get("/api/escritorio/auditoria").status_code == 401
    db = _banco(logado)
    try:
        u = db.scalar(select(Usuario))
        membro = Usuario(escritorio_id=u.escritorio_id, nome="Bia", email="bia@escritorio.com.br", senha_hash=u.senha_hash, papel="membro")
        db.add(membro)
        db.commit()
    finally:
        db.close()
    bia = TestClient(logado.app)
    bia.post("/api/auth/login", json={"email": "bia@escritorio.com.br", "senha": SENHA})
    assert bia.get("/api/escritorio/auditoria").status_code == 403
    assert bia.get("/api/escritorio/auditoria/exportar.csv").status_code == 403


def test_registra_login_cliente_e_importacao_com_usuario_e_ip(logado: TestClient):
    logado.post("/api/auth/logout")
    logado.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": SENHA})
    cid = logado.post("/api/clientes", json={"razao_social": "Padaria Pão Bom", "cnpj": CNPJ_VALIDO}).json()["id"]
    logado.post(f"/api/clientes/{cid}/importacoes", files=[("arquivos", ("n.xml", nfe(1, CNPJ_VALIDO, "45997418000153")))])
    logado.delete(f"/api/clientes/{cid}/documentos")
    logado.delete(f"/api/clientes/{cid}")
    pag = _registros(logado)
    acoes = [i["acao"] for i in pag["itens"]]
    assert acoes[:5] == ["cliente_excluido", "documentos_apagados", "documentos_importados", "cliente_criado", "login"]
    por = {i["acao"]: i for i in pag["itens"]}
    assert por["cliente_criado"]["usuario"] == "Ana Contadora <ana@escritorio.com.br>"
    assert por["cliente_criado"]["detalhe"] == {"razao_social": "Padaria Pão Bom"}
    assert por["documentos_importados"]["detalhe"] == {"importados": 1, "duplicados": 0}
    assert por["cliente_excluido"]["entidade"] == "cliente" and por["cliente_excluido"]["entidade_id"] == cid
    assert por["login"]["ip"] == "testclient"
    assert por["login"]["rotulo"] == ROTULOS["login"]
    assert pag["retencao_meses"] == 24 and {"codigo": "login", "rotulo": ROTULOS["login"]} in pag["acoes"]


def test_login_recusado_so_aparece_para_quem_tem_conta(logado: TestClient):
    c = TestClient(logado.app)
    c.post("/api/auth/login", json={"email": "ana@escritorio.com.br", "senha": "errada"})
    c.post("/api/auth/login", json={"email": "ninguem@escritorio.com.br", "senha": "errada"})
    falhas = _acoes(logado, acao="login_falha")
    assert falhas == ["login_falha"]  # a tentativa com e-mail desconhecido não tem escritório para receber o registro


def test_senha_nunca_vai_para_o_registro(logado: TestClient):
    logado.post("/api/auth/alterar-senha", json={"senha_atual": SENHA, "nova_senha": "outra-senha-456"})
    logado.put("/api/escritorio/caixa-email", json={"host": "imap.exemplo.com.br", "usuario": "a@b.com", "senha": "segredo-da-caixa"}) 
    texto = str(_registros(logado))
    for proibido in (SENHA, "outra-senha-456", "segredo-da-caixa", "scrypt$"):
        assert proibido not in texto
    assert "senha_alterada" in texto


def test_envio_pelo_link_do_cliente_fica_sem_usuario(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Padaria", "cnpj": CNPJ_VALIDO}).json()["id"]
    token = logado.post(f"/api/clientes/{cid}/caixa", json={}).json()["link"].rsplit("/", 1)[1]
    anonimo = TestClient(logado.app)
    anonimo.post(f"/api/caixa/{token}/arquivos", files=[("arquivos", ("n.xml", nfe(1, CNPJ_VALIDO, "45997418000153")))])
    envio = next(i for i in _registros(logado)["itens"] if i["acao"] == "caixa_envio")
    assert envio["usuario"] is None and envio["detalhe"]["importados"] == 1 and envio["entidade_id"] == cid


def test_filtros_paginacao_e_isolamento(logado: TestClient):
    for i in range(5):
        logado.post("/api/clientes", json={"razao_social": f"Cliente {i}"})
    todos = _registros(logado)
    assert todos["total"] >= 5
    so_clientes = _registros(logado, acao="cliente_criado")
    assert so_clientes["total"] == 5 and all(i["acao"] == "cliente_criado" for i in so_clientes["itens"])
    pag1 = _registros(logado, acao="cliente_criado", limite=2, deslocamento=0)
    pag2 = _registros(logado, acao="cliente_criado", limite=2, deslocamento=2)
    assert len(pag1["itens"]) == len(pag2["itens"]) == 2 and not {i["id"] for i in pag1["itens"]} & {i["id"] for i in pag2["itens"]}
    hoje = agora().date().isoformat()
    assert _registros(logado, acao="cliente_criado", desde=hoje, ate=hoje)["total"] == 5
    ontem = (agora() - timedelta(days=2)).date().isoformat()
    assert _registros(logado, acao="cliente_criado", ate=ontem)["total"] == 0
    meu = logado.get("/api/auth/me").json()["usuario"]["id"]
    assert _registros(logado, acao="cliente_criado", usuario_id=meu)["total"] == 5
    assert _registros(logado, acao="cliente_criado", usuario_id=meu + 999)["total"] == 0
    # outro escritório não vê nada deste
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert "cliente_criado" not in _acoes(logado)


def test_exportacao_csv_protege_contra_formula(logado: TestClient):
    db = _banco(logado)
    try:
        u = db.scalar(select(Usuario))
        u.nome = "=HYPERLINK(\"http://x\")"  # nome digitado por um usuário: não pode virar fórmula no Excel
        auditar(db, u.escritorio_id, "cliente_criado", u, detalhe={"razao_social": "+cmd"})
        db.commit()
    finally:
        db.close()
    r = logado.get("/api/escritorio/auditoria/exportar.csv", params={"acao": "cliente_criado"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    import csv
    import io

    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert linhas[0][:3] == ["Data e hora (UTC)", "Usuário", "Ação"]
    assert len(linhas) == 2 and linhas[1][1].startswith("'=HYPERLINK") and linhas[1][2] == "Cadastrou um cliente"
    assert not any(c.startswith(("=", "+", "-", "@")) for c in linhas[1])


def test_registros_antigos_sao_apagados_ao_abrir(logado: TestClient):
    db = _banco(logado)
    try:
        u = db.scalar(select(Usuario))
        db.add(RegistroAuditoria(escritorio_id=u.escritorio_id, acao="login", criado_em=agora() - timedelta(days=30 * 25)))
        db.add(RegistroAuditoria(escritorio_id=u.escritorio_id, acao="login", criado_em=agora() - timedelta(days=30 * 23)))
        db.commit()
    finally:
        db.close()
    antes = _registros(logado, acao="login")["total"]
    db = _banco(logado)
    try:
        assert len(db.scalars(select(RegistroAuditoria).where(RegistroAuditoria.criado_em < agora() - timedelta(days=30 * 24))).all()) == 0
    finally:
        db.close()
    assert antes == 1  # só o de 23 meses ficou


def test_acao_desconhecida_e_erro_de_programacao(logado: TestClient):
    db = _banco(logado)
    try:
        with pytest.raises(ValueError):
            auditar(db, 1, "acao_inventada")
    finally:
        db.close()
