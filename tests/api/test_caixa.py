from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tolaris_api.config import get_settings
from tolaris_api.routers import caixa as modulo_caixa

from .conftest import CNPJ_VALIDO, cadastrar
from .test_importacao import CLIENTE_DO_CLIENTE, FORNECEDOR, nfe


@pytest.fixture(autouse=True)
def _limpar_limite():
    modulo_caixa._envios_recentes.clear()
    yield
    modulo_caixa._envios_recentes.clear()


def _cliente(c: TestClient, cnpj: str | None = CNPJ_VALIDO) -> int:
    return c.post("/api/clientes", json={"razao_social": "Padaria Pão Bom", "cnpj": cnpj}).json()["id"]


def _anonimo(c: TestClient) -> TestClient:
    """Quem abre o link não tem sessão: um cliente HTTP novo, sem o cookie do escritório."""
    return TestClient(c.app)


def _link(c: TestClient, cid: int, **corpo) -> tuple[str, dict]:
    r = c.post(f"/api/clientes/{cid}/caixa", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["link"].rsplit("/", 1)[1], r.json()


def _enviar(c: TestClient, token: str, arquivos: list[tuple[str, bytes]]):
    return c.post(f"/api/caixa/{token}/arquivos", files=[("arquivos", (n, b)) for n, b in arquivos])


def test_exige_login_e_cnpj(logado: TestClient):
    assert _anonimo(logado).post("/api/clientes/1/caixa", json={}).status_code == 401
    sem_cnpj = _cliente(logado, cnpj=None)
    r = logado.post(f"/api/clientes/{sem_cnpj}/caixa", json={})
    assert r.status_code == 400 and "CNPJ" in r.json()["detail"]


def test_cliente_envia_notas_pelo_link_sem_login(logado: TestClient):
    cid = _cliente(logado)
    assert logado.get(f"/api/clientes/{cid}/caixa").json() == {
        "ativo": False, "criado_em": None, "ultimo_envio_em": None, "total_envios": 0, "total_notas": 0}
    token, resposta = _link(logado, cid)
    assert "/enviar/" in resposta["link"] and resposta["enviado_para"] == []

    anonimo = _anonimo(logado)
    info = anonimo.get(f"/api/caixa/{token}").json()
    assert info["cliente"] == "Padaria Pão Bom" and info["escritorio"]["nome"] == "Escritório Ana" and info["limite_mb"] == 25

    r = _enviar(anonimo, token, [
        ("venda1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, valor="1000.00")),
        ("venda2.xml", nfe(2, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, valor="500.00", data="2026-04-02")),
        ("alheia.xml", nfe(3, FORNECEDOR, CLIENTE_DO_CLIENTE)),
        ("planilha.csv", b"a;b"),
    ])
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["importados"] == 2 and corpo["duplicados"] == 0 and corpo["total_ignorados"] == 2
    assert corpo["competencias"] == ["2026-03", "2026-04"]

    # O escritório vê as notas no movimento e o resumo do que o link recebeu
    mov = logado.get(f"/api/clientes/{cid}/movimento").json()
    assert [m["saidas"] for m in mov["meses"]] == [1000.0, 500.0]
    estado = logado.get(f"/api/clientes/{cid}/caixa").json()
    assert estado["ativo"] and estado["total_envios"] == 1 and estado["total_notas"] == 2 and estado["ultimo_envio_em"]

    # Reenviar as mesmas notas não duplica nem soma de novo
    r2 = _enviar(anonimo, token, [("venda1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, valor="1000.00"))]).json()
    assert r2["importados"] == 0 and r2["duplicados"] == 1
    estado = logado.get(f"/api/clientes/{cid}/caixa").json()
    assert estado["total_envios"] == 2 and estado["total_notas"] == 2


def test_link_novo_ou_desativado_derruba_o_anterior(logado: TestClient):
    cid = _cliente(logado)
    antigo, _ = _link(logado, cid)
    novo, _ = _link(logado, cid)
    anonimo = _anonimo(logado)
    assert anonimo.get(f"/api/caixa/{antigo}").status_code == 404
    assert _enviar(anonimo, antigo, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]).status_code == 404
    assert anonimo.get(f"/api/caixa/{novo}").status_code == 200
    assert logado.delete(f"/api/clientes/{cid}/caixa").status_code == 204
    assert anonimo.get(f"/api/caixa/{novo}").status_code == 404
    assert _enviar(anonimo, novo, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]).status_code == 404
    assert anonimo.get("/api/caixa/token-que-nao-existe").status_code == 404
    assert anonimo.get(f"/api/caixa/{novo}/logo").status_code == 404


def test_link_por_e_mail(logado: TestClient, caixa_limpa):
    cid = _cliente(logado)
    token, r = _link(logado, cid, enviar_para=["financeiro@padaria.com.br"])
    assert r["enviado_para"] == ["financeiro@padaria.com.br"]
    msg = next(m for m in caixa_limpa if m.assunto.startswith("Envio das notas fiscais"))
    assert msg.para == ["financeiro@padaria.com.br"] and f"/enviar/{token}" in msg.texto
    assert "Escritório Ana" in msg.assunto and msg.responder_para == "ana@escritorio.com.br"


def test_limite_de_envios_por_hora(logado: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(modulo_caixa, "ENVIOS_POR_HORA", 2)
    cid = _cliente(logado)
    token, _ = _link(logado, cid)
    anonimo = _anonimo(logado)
    for n in (1, 2):
        assert _enviar(anonimo, token, [(f"{n}.xml", nfe(n, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]).status_code == 201
    r = _enviar(anonimo, token, [("3.xml", nfe(3, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_envio_acima_do_limite_de_tamanho(logado: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "importacao_max_mb", 0)
    cid = _cliente(logado)
    token, _ = _link(logado, cid)
    r = _enviar(_anonimo(logado), token, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])
    assert r.status_code == 413


def test_link_nao_serve_para_outro_cliente_nem_escritorio(logado: TestClient):
    a = _cliente(logado)
    token, _ = _link(logado, a)
    # Notas de outro CNPJ enviadas pelo link do cliente A não entram em ninguém
    outro = _cliente(logado, cnpj=FORNECEDOR)
    r = _enviar(_anonimo(logado), token, [("x.xml", nfe(1, FORNECEDOR, CLIENTE_DO_CLIENTE))]).json()
    assert r["importados"] == 0 and "nem destinatário" in r["ignorados"][0]["motivo"]
    assert logado.get(f"/api/clientes/{outro}/movimento").json()["documentos"] == 0
    # Outro escritório não vê nem gera o link do cliente
    logado.post("/api/auth/logout")
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get(f"/api/clientes/{a}/caixa").status_code == 404
    assert logado.post(f"/api/clientes/{a}/caixa", json={}).status_code == 404
    assert logado.delete(f"/api/clientes/{a}/caixa").status_code == 404


def test_excluir_cliente_apaga_a_caixa(logado: TestClient):
    cid = _cliente(logado)
    token, _ = _link(logado, cid)
    assert logado.delete(f"/api/clientes/{cid}").status_code == 204
    assert _anonimo(logado).get(f"/api/caixa/{token}").status_code == 404
