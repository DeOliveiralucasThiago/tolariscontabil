from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from tolaris_api import models  # noqa: F401
from tolaris_api.cnpj import DadosCnpj, CnpjNaoEncontrado
from tolaris_api.db import Base, criar_engine, get_db
from tolaris_api.main import app
from tolaris_api.routers.cnpj import get_consulta_cnpj

CNPJ_VALIDO = "11222333000181"


def consulta_falsa(cnpj: str) -> DadosCnpj:
    if cnpj != CNPJ_VALIDO:
        raise CnpjNaoEncontrado(cnpj)
    return DadosCnpj(
        cnpj=cnpj, razao_social="ACME CONSULTORIA LTDA", nome_fantasia="ACME", situacao="ATIVA",
        cnae_principal="7020400", cnae_descricao="Atividades de consultoria em gestão empresarial",
        municipio="SAO PAULO", uf="SP", email="contato@acme.com.br", telefone="1133334444",
        opcao_simples=True, opcao_mei=False,
        natureza_juridica="Sociedade Empresária Limitada", natureza_juridica_codigo="2062",
    )


@pytest.fixture(autouse=True)
def caixa_limpa():
    from tolaris_api.emails import CAIXA_SAIDA

    CAIXA_SAIDA.clear()
    yield CAIXA_SAIDA


@pytest.fixture()
def client():
    # TOLARIS_TEST_DATABASE_URL permite rodar a mesma suíte contra PostgreSQL.
    engine = criar_engine(os.environ.get("TOLARIS_TEST_DATABASE_URL", "sqlite://"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_teste():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_teste
    app.dependency_overrides[get_consulta_cnpj] = lambda: consulta_falsa
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def cadastrar(c: TestClient, email: str = "ana@escritorio.com.br", escritorio: str = "Escritório Ana") -> dict:
    r = c.post("/api/auth/cadastro", json={
        "escritorio_nome": escritorio, "nome": "Ana Contadora", "email": email, "senha": "senha-segura-123",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def logado(client):
    cadastrar(client)
    return client
