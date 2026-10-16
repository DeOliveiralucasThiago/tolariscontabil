"""LGPD: exportação completa dos dados de um cliente e exclusão definitiva sem sobras."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tolaris_api.db import get_db
from tolaris_api.models import (
    CaixaCliente,
    Cliente,
    DocumentoFiscal,
    Envio,
    FinanceiroMensal,
    ItemFiscal,
    PortalCliente,
    RegistroAuditoria,
    Simulacao,
    Usuario,
)

from .conftest import CNPJ_VALIDO, cadastrar
from .test_importacao import nfe
from .test_recuperacao import COMUM_CHEIO, nfe_itens

SENHA = "senha-segura-123"


def _banco(c):
    return next(c.app.dependency_overrides[get_db]())


def _carteira(c: TestClient) -> int:
    """Cliente com simulação (e envio de relatório), notas com itens, dados contábeis, portal e link de envio."""
    cid = c.post("/api/clientes", json={"razao_social": "Mercadinho Boa Compra", "cnpj": CNPJ_VALIDO, "email": "dono@mercadinho.com.br",
                                        "contato_nome": "Marcos Souza", "telefone": "11999990000", "atividade": "comercio"}).json()["id"]
    sim = c.post(f"/api/clientes/{cid}/simulacoes/completa", json={
        "atividade": "comercio", "receita_bruta_anual": 1200000, "folha_clt_anual": 120000, "pro_labore_anual": 36000,
        "compras_anual": 720000, "despesas_creditaveis_anual": 60000}).json()
    c.post(f"/api/simulacoes/{sim['id']}/enviar", json={"para": ["dono@mercadinho.com.br"]})
    c.post(f"/api/clientes/{cid}/importacoes", files=[("arquivos", ("a.xml", nfe_itens(1, "2026-01-10", [COMUM_CHEIO])))])
    csv = ("Mês;Receita\n2026-01;100000,00\n").encode()
    c.post(f"/api/clientes/{cid}/financeiro/importar", files=[("arquivos", ("d.csv", csv))], data={"mapeamento": json.dumps({"competencia": 0, "receita": 1})})
    c.post(f"/api/clientes/{cid}/portal", json={})
    c.post(f"/api/clientes/{cid}/caixa", json={})
    return cid


def test_exportacao_traz_tudo_do_cliente(logado: TestClient):
    cid = _carteira(logado)
    r = logado.get(f"/api/clientes/{cid}/exportacao")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].startswith(f'attachment; filename="dados-cliente-{cid}-')
    d = json.loads(r.content)
    assert d["formato"] == "tolaris-exportacao-cliente/1" and d["gerado_por"] == "ana@escritorio.com.br"
    assert d["cliente"]["razao_social"] == "Mercadinho Boa Compra" and d["cliente"]["email"] == "dono@mercadinho.com.br"
    assert d["cliente"]["contato_nome"] == "Marcos Souza" and d["cliente"]["telefone"] == "11999990000"
    assert len(d["simulacoes"]) == 1 and d["simulacoes"][0]["resultado"]["melhor"]
    assert d["envios_de_relatorio"][0]["para"] == "dono@mercadinho.com.br"
    assert len(d["documentos_fiscais"]) == 1 and d["documentos_fiscais"][0]["itens"][0]["ncm"] == "19059090"
    assert d["dados_contabeis"][0]["receita_centavos"] == 10000000
    assert d["portal_do_cliente"]["ativo"] is True and d["link_de_envio_de_notas"]["ativo"] is True
    assert {x["acao"] for x in d["registro_de_atividades"]} >= {"cliente_criado"}


def test_exportacao_nao_vaza_segredos_nem_outros_clientes(logado: TestClient):
    cid = _carteira(logado)
    outro = logado.post("/api/clientes", json={"razao_social": "Outro Cliente SA", "cnpj": "11444777000161"}).json()["id"]
    texto = logado.get(f"/api/clientes/{cid}/exportacao").text
    assert "token_hash" not in texto and "scrypt" not in texto
    assert "Outro Cliente SA" not in texto
    db = _banco(logado)
    try:
        for t in db.scalars(select(PortalCliente.token_hash)):
            assert t not in texto
        for t in db.scalars(select(CaixaCliente.token_hash)):
            assert t not in texto
    finally:
        db.close()
    assert outro


def test_exportar_e_excluir_exigem_administrador_do_proprio_escritorio(logado: TestClient):
    cid = _carteira(logado)
    assert TestClient(logado.app).get(f"/api/clientes/{cid}/exportacao").status_code == 401
    db = _banco(logado)
    try:
        u = db.scalar(select(Usuario))
        db.add(Usuario(escritorio_id=u.escritorio_id, nome="Bia", email="bia@escritorio.com.br", senha_hash=u.senha_hash, papel="membro"))
        db.commit()
    finally:
        db.close()
    bia = TestClient(logado.app)
    bia.post("/api/auth/login", json={"email": "bia@escritorio.com.br", "senha": SENHA})
    assert bia.get(f"/api/clientes/{cid}/exportacao").status_code == 403
    assert bia.delete(f"/api/clientes/{cid}").status_code == 403
    assert bia.get(f"/api/clientes/{cid}").status_code == 200  # membro continua trabalhando com o cliente
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get(f"/api/clientes/{cid}/exportacao").status_code == 404
    assert logado.delete(f"/api/clientes/{cid}").status_code == 404


def test_exportar_fica_no_registro_de_atividades(logado: TestClient):
    cid = _carteira(logado)
    logado.get(f"/api/clientes/{cid}/exportacao")
    pag = logado.get("/api/escritorio/auditoria", params={"acao": "cliente_exportado"}).json()
    assert pag["total"] == 1 and pag["itens"][0]["detalhe"] == {"documentos": 1, "simulacoes": 1}


def test_exclusao_definitiva_nao_deixa_nada_para_tras(logado: TestClient):
    cid = _carteira(logado)
    outro = logado.post("/api/clientes", json={"razao_social": "Fica Aqui Ltda", "cnpj": "11444777000161"}).json()["id"]
    logado.post(f"/api/clientes/{outro}/simulacoes/completa", json={"atividade": "comercio", "receita_bruta_anual": 500000})
    assert logado.delete(f"/api/clientes/{cid}").status_code == 204
    db = _banco(logado)
    try:
        for modelo in (Simulacao, DocumentoFiscal, ItemFiscal, FinanceiroMensal, PortalCliente, CaixaCliente):
            assert db.scalar(select(func.count()).select_from(modelo).where(modelo.cliente_id == cid)) == 0, modelo.__name__
        assert db.scalar(select(func.count()).select_from(Envio)) == 0  # os envios eram do relatório do cliente excluído
        assert db.scalar(select(func.count()).select_from(Cliente).where(Cliente.id == cid)) == 0
        # o outro cliente ficou intacto
        assert db.scalar(select(func.count()).select_from(Simulacao).where(Simulacao.cliente_id == outro)) == 1
        # registro: sobra só o fato da exclusão, sem o nome do cliente
        texto = str([(r.acao, r.detalhe) for r in db.scalars(select(RegistroAuditoria).where(RegistroAuditoria.entidade == "cliente", RegistroAuditoria.entidade_id == cid))])
        assert "cliente_excluido" in texto and "Mercadinho" not in texto
    finally:
        db.close()
    assert logado.get(f"/api/clientes/{cid}").status_code == 404
