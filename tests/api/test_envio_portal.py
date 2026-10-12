from __future__ import annotations

import re

from fastapi.testclient import TestClient

from tolaris_api import emails
from tolaris_api.emails import CAIXA_SAIDA, ErroEnvio

from .conftest import cadastrar

EXPRESSA = {"faturamento_mensal": 50000, "folha_mensal": 8000, "pro_labore_mensal": 5000, "atividade": "servico_fator_r"}


def _cliente_com_simulacao(c: TestClient) -> tuple[int, int]:
    c.patch("/api/escritorio", json={"email": "contato@escritorio.com.br"})
    cid = c.post("/api/clientes", json={"razao_social": "Padaria Pão Bom", "email": "dono@padaria.com.br"}).json()["id"]
    sid = c.post(f"/api/clientes/{cid}/simulacoes/expressa", json=EXPRESSA).json()["id"]
    return cid, sid


def test_enviar_relatorio_com_pdf(logado: TestClient):
    _, sid = _cliente_com_simulacao(logado)
    r = logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": ["Dono@Padaria.com.br"], "mensagem": "Oi!\nSegue."})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "enviado" and r.json()["para"] == "dono@padaria.com.br"
    msg = CAIXA_SAIDA[-1]
    assert msg.nome_remetente == "Escritório Ana" and msg.responder_para == "contato@escritorio.com.br"
    assert msg.assunto == "Diagnóstico tributário — Padaria Pão Bom"
    assert msg.anexos[0].nome == f"diagnostico-tributario-{sid}.pdf" and msg.anexos[0].conteudo.startswith(b"%PDF")
    assert "Oi!" in msg.html and "<script" not in msg.html
    assert [e["status"] for e in logado.get(f"/api/simulacoes/{sid}/envios").json()] == ["enviado"]


def test_falha_no_envio_fica_registrada(logado: TestClient, monkeypatch):
    _, sid = _cliente_com_simulacao(logado)

    def quebra(_msg):
        raise ErroEnvio("servidor fora do ar")

    monkeypatch.setattr("tolaris_api.routers.compartilhamento.enviar", quebra)
    assert logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": ["x@y.com"]}).status_code == 502
    envio = logado.get(f"/api/simulacoes/{sid}/envios").json()[0]
    assert envio["status"] == "falhou" and "fora do ar" in envio["erro"]


def test_envio_valida_destinatarios(logado: TestClient):
    _, sid = _cliente_com_simulacao(logado)
    assert logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": []}).status_code == 422
    assert logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": ["nao-e-email"]}).status_code == 422
    assert logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": [f"a{i}@b.com" for i in range(6)]}).status_code == 422


def test_portal_mostra_so_publicadas(logado: TestClient):
    cid, sid = _cliente_com_simulacao(logado)
    sid2 = logado.post(f"/api/clientes/{cid}/simulacoes/expressa", json=EXPRESSA).json()["id"]
    assert logado.get(f"/api/clientes/{cid}/portal").json() == {"ativo": False, "criado_em": None,
                                                                 "ultimo_acesso_em": None, "publicadas": 0}
    r = logado.patch(f"/api/simulacoes/{sid}/publicacao", json={"publicada": True})
    assert r.json()["publicada"] is True
    link = logado.post(f"/api/clientes/{cid}/portal", json={}).json()["link"]
    token = link.rsplit("/", 1)[1]
    logado.post("/api/auth/logout")

    portal = logado.get(f"/api/portal/{token}").json()
    assert portal["cliente"] == "Padaria Pão Bom" and portal["escritorio"]["nome"] == "Escritório Ana"
    assert [s["id"] for s in portal["simulacoes"]] == [sid]
    assert logado.get(f"/api/portal/{token}/simulacoes/{sid}.pdf").content.startswith(b"%PDF")
    assert logado.get(f"/api/portal/{token}/simulacoes/{sid2}.pdf").status_code == 404  # não publicada


def test_novo_link_invalida_o_anterior_e_desativar(logado: TestClient):
    cid, _ = _cliente_com_simulacao(logado)
    antigo = logado.post(f"/api/clientes/{cid}/portal", json={}).json()["link"].rsplit("/", 1)[1]
    novo = logado.post(f"/api/clientes/{cid}/portal", json={}).json()["link"].rsplit("/", 1)[1]
    assert logado.get(f"/api/portal/{antigo}").status_code == 404
    assert logado.get(f"/api/portal/{novo}").status_code == 200
    assert logado.get(f"/api/clientes/{cid}/portal").json()["ultimo_acesso_em"] is not None
    assert logado.delete(f"/api/clientes/{cid}/portal").status_code == 204
    assert logado.get(f"/api/portal/{novo}").status_code == 404


def test_link_do_portal_por_email(logado: TestClient):
    cid, _ = _cliente_com_simulacao(logado)
    r = logado.post(f"/api/clientes/{cid}/portal", json={"enviar_para": ["dono@padaria.com.br"]}).json()
    assert r["enviado_para"] == ["dono@padaria.com.br"]
    assert r["link"] in CAIXA_SAIDA[-1].texto
    assert re.search(r"/portal/[\w-]{40,}", CAIXA_SAIDA[-1].html)


def test_portal_isolado_por_escritorio(client: TestClient):
    cadastrar(client, "a@a.com", "Escritório A")
    cid, sid = _cliente_com_simulacao(client)
    client.post("/api/auth/logout")
    cadastrar(client, "b@b.com", "Escritório B")
    assert client.post(f"/api/clientes/{cid}/portal", json={}).status_code == 404
    assert client.patch(f"/api/simulacoes/{sid}/publicacao", json={"publicada": True}).status_code == 404
    assert client.post(f"/api/simulacoes/{sid}/enviar", json={"para": ["x@y.com"]}).status_code == 404
    assert client.get("/api/portal/" + "x" * 43).status_code == 404


def test_backend_desconhecido(monkeypatch):
    from tolaris_api.config import get_settings

    monkeypatch.setattr(get_settings(), "email_backend", "pombo-correio")
    import pytest

    with pytest.raises(ErroEnvio):
        emails.enviar(emails.Mensagem(para=["a@b.com"], assunto="x", texto="x", html="x"))


def test_backend_arquivo(tmp_path, monkeypatch):
    import json

    from tolaris_api.config import get_settings

    monkeypatch.setattr(get_settings(), "email_backend", "arquivo")
    monkeypatch.setattr(get_settings(), "email_pasta", str(tmp_path))
    emails.enviar(emails.Mensagem(para=["a@b.com"], assunto="Olá", texto="t", html="<p>h</p>", nome_remetente="Escritório X",
                                  anexos=[emails.Anexo("../relatorio.pdf", b"%PDF-1")]))
    gravado = json.loads(next(tmp_path.glob("*.json")).read_text())
    from email.header import decode_header, make_header

    assert gravado["assunto"] == "Olá"
    assert "Escritório X via Tolaris" in str(make_header(decode_header(gravado["remetente"])))
    assert (tmp_path / gravado["anexos"][0]).read_bytes() == b"%PDF-1"  # nome do anexo não escapa da pasta
